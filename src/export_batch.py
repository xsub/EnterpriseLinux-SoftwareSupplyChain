"""Batch export EDGP graph snapshots into local egress artifacts."""

from __future__ import annotations

import hashlib
import json
import tarfile
import tempfile
from gzip import GzipFile
from pathlib import Path
from typing import Any, BinaryIO, Sequence

from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.output.cypher_export import CypherExporter
from src.output.json_export import GraphJsonExporter
from src.output.sbom_security import CycloneDXExporter

EXPORT_BATCH_SCHEMA = "edgp.export.batch.v1"
EXPORT_BATCH_ARCHIVE_SCHEMA = "edgp.export.batch.archive.v1"
EXPORT_BATCH_VERIFICATION_SCHEMA = "edgp.export.batch.verification.v1"
DETERMINISTIC_CYCLONEDX_TIMESTAMP = "1970-01-01T00:00:00+00:00"

_EXPORT_FILES = {
    "cypher": ("graph.cypher", "text/vnd.neo4j.cypher"),
    "cyclonedx": ("graph.cyclonedx.json", "application/vnd.cyclonedx+json"),
    "json": ("graph.snapshot.json", "application/vnd.edgp.graph.snapshot+json"),
}


def write_graph_export_batch(
    snapshot_path: Path,
    output_dir: Path,
    *,
    formats: Sequence[str],
    manifest_name: str = "manifest.json",
    command: str | None = None,
) -> dict[str, Any]:
    """Write selected egress formats and return the batch export manifest."""

    normalized_formats = _normalize_formats(formats)
    snapshot = _load_graph_snapshot(snapshot_path)
    root = snapshot.get("root") if isinstance(snapshot.get("root"), str) else None
    ecosystem = str(snapshot.get("ecosystem") or "generic")
    graph = graph_from_snapshot(snapshot)

    output_dir.mkdir(parents=True, exist_ok=True)
    exports = [
        _write_export(
            output_dir,
            export_format,
            graph,
            root=root,
            ecosystem=ecosystem,
            snapshot=snapshot,
        )
        for export_format in normalized_formats
    ]
    manifest = {
        "schema": EXPORT_BATCH_SCHEMA,
        "source": {
            "path": str(snapshot_path.resolve()),
            "root": root,
            "ecosystem": ecosystem,
            "stats": _snapshot_stats(snapshot),
        },
        "summary": {
            "exports": len(exports),
            "formats": normalized_formats,
            "bytes": sum(int(export["bytes"]) for export in exports),
        },
        "exports": exports,
    }
    if command:
        manifest["command"] = command
    (output_dir / manifest_name).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_graph_export_batch(
    batch_dir: Path,
    *,
    manifest_name: str = "manifest.json",
) -> dict[str, Any]:
    """Verify an export batch manifest and the recorded artifact fingerprints."""

    batch_dir = batch_dir.resolve()
    manifest_path = batch_dir / manifest_name
    failures: list[dict[str, str]] = []
    manifest: dict[str, Any] = {}
    manifest_sha256: str | None = None

    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
        payload = json.loads(manifest_bytes.decode("utf-8"))
        if isinstance(payload, dict):
            manifest = payload
        else:
            _add_failure(
                failures,
                "manifestInvalid",
                "Manifest must be a JSON object",
                manifest_path,
            )
    except FileNotFoundError:
        _add_failure(failures, "manifestMissing", f"Missing {manifest_name}", manifest_path)
    except json.JSONDecodeError as error:
        _add_failure(failures, "manifestInvalidJson", str(error), manifest_path)

    if manifest:
        _verify_manifest_shape(manifest, failures, manifest_path)
        _verify_manifest_artifacts(manifest, failures, batch_dir)

    exports = manifest.get("exports", []) if isinstance(manifest, dict) else []
    summary = manifest.get("summary", {}) if isinstance(manifest, dict) else {}
    return {
        "schema": EXPORT_BATCH_VERIFICATION_SCHEMA,
        "batchDir": str(batch_dir),
        "manifest": manifest_name,
        "ok": not failures,
        "manifestSha256": manifest_sha256,
        "summary": {
            "exports": len(exports) if isinstance(exports, list) else 0,
            "bytes": _summary_bytes(summary),
            "failures": len(failures),
        },
        "failures": failures,
    }


def write_graph_export_batch_archive(
    batch_dir: Path,
    output_path: Path,
    *,
    manifest_name: str = "manifest.json",
) -> dict[str, Any]:
    """Verify and package a graph export batch as a deterministic tar.gz archive."""

    verification = verify_graph_export_batch(batch_dir, manifest_name=manifest_name)
    if not verification["ok"]:
        return {
            "schema": EXPORT_BATCH_ARCHIVE_SCHEMA,
            "batchDir": str(batch_dir.resolve()),
            "archive": str(output_path),
            "ok": False,
            "manifestSha256": verification.get("manifestSha256"),
            "archiveSha256": None,
            "summary": {
                "files": 0,
                "bytes": 0,
                "verificationFailures": verification["summary"]["failures"],
            },
            "verification": verification,
        }

    members = _archive_members(batch_dir, exclude=output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as raw_output:
        _write_deterministic_tar_gz(batch_dir, members, raw_output)
    archive_bytes = output_path.read_bytes()
    return _archive_report(
        archive_path=output_path,
        archive_sha256=hashlib.sha256(archive_bytes).hexdigest(),
        archive_bytes=len(archive_bytes),
        files=len(members),
        verification=verification,
    )


def verify_graph_export_batch_archive(
    archive_path: Path,
    *,
    manifest_name: str = "manifest.json",
) -> dict[str, Any]:
    """Verify a deterministic tar.gz graph export batch archive."""

    archive_path = archive_path.resolve()
    try:
        archive_bytes = archive_path.read_bytes()
    except FileNotFoundError:
        verification = _archive_verification_report(
            archive_path.parent,
            manifest_name=manifest_name,
            failures=[
                {
                    "code": "archiveMissing",
                    "message": "Archive file is missing",
                    "path": str(archive_path),
                }
            ],
        )
        return _archive_report(
            archive_path=archive_path,
            archive_sha256=None,
            archive_bytes=0,
            files=0,
            verification=verification,
        )

    archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    with tempfile.TemporaryDirectory() as temp_dir:
        batch_dir = Path(temp_dir) / "export-batch"
        batch_dir.mkdir()
        failures: list[dict[str, str]] = []
        member_count = 0
        try:
            with tarfile.open(archive_path, "r:gz") as archive:
                members = archive.getmembers()
                member_count = len(members)
                _validate_archive_members(members, archive_path, failures)
                if not failures:
                    _extract_archive_members(archive, members, batch_dir, failures)
        except (OSError, tarfile.TarError) as error:
            _add_failure(
                failures,
                "archiveInvalid",
                f"Could not read gzip tar archive: {error}",
                archive_path,
            )

        if failures:
            verification = _archive_verification_report(
                batch_dir,
                manifest_name=manifest_name,
                failures=failures,
            )
        else:
            verification = verify_graph_export_batch(batch_dir, manifest_name=manifest_name)
        return _archive_report(
            archive_path=archive_path,
            archive_sha256=archive_sha256,
            archive_bytes=len(archive_bytes),
            files=member_count,
            verification=verification,
        )


def _archive_report(
    *,
    archive_path: Path,
    archive_sha256: str | None,
    archive_bytes: int,
    files: int,
    verification: dict[str, Any],
) -> dict[str, Any]:
    summary = verification.get("summary", {})
    verification_failures = (
        summary.get("failures", 0) if isinstance(summary, dict) else 0
    )
    return {
        "schema": EXPORT_BATCH_ARCHIVE_SCHEMA,
        "batchDir": str(verification.get("batchDir", "")),
        "archive": str(archive_path),
        "ok": bool(verification.get("ok")),
        "manifestSha256": verification.get("manifestSha256"),
        "archiveSha256": archive_sha256,
        "summary": {
            "files": files,
            "bytes": archive_bytes,
            "verificationFailures": verification_failures,
        },
        "verification": verification,
    }


def _archive_verification_report(
    batch_dir: Path,
    *,
    manifest_name: str,
    failures: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "schema": EXPORT_BATCH_VERIFICATION_SCHEMA,
        "batchDir": str(batch_dir.resolve()),
        "manifest": manifest_name,
        "ok": False,
        "manifestSha256": None,
        "summary": {
            "exports": 0,
            "bytes": 0,
            "failures": len(failures),
        },
        "failures": failures,
    }


def graph_from_snapshot(snapshot: dict[str, Any]) -> CSRDependencyGraph:
    """Rebuild a CSR graph from an `edgp.graph.snapshot.v1` payload."""

    if snapshot.get("schema") != "edgp.graph.snapshot.v1":
        raise ValueError("Export batch input must be an edgp.graph.snapshot.v1 document")
    graph = CSRDependencyGraph()
    nodes = snapshot.get("nodes", [])
    if not isinstance(nodes, list):
        raise ValueError("Graph snapshot nodes must be a list")
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            raise ValueError("Graph snapshot node entries must include string ids")
        metadata = node.get("metadata") if isinstance(node.get("metadata"), dict) else {}
        graph.add_vertex(str(node["id"]), metadata=metadata)

    edges = snapshot.get("edges", [])
    if not isinstance(edges, list):
        raise ValueError("Graph snapshot edges must be a list")
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("Graph snapshot edge entries must be objects")
        source = edge.get("source")
        target = edge.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValueError("Graph snapshot edges must include source and target")
        relationship_type = int(edge.get("relationshipType", 1) or 1)
        graph.add_dependency_edge(source, target, relationship_type=relationship_type)
    return graph


def _normalize_formats(formats: Sequence[str]) -> list[str]:
    values = list(formats) or ["cypher", "cyclonedx"]
    normalized: list[str] = []
    for value in values:
        if value not in _EXPORT_FILES:
            raise ValueError(f"Unsupported export batch format: {value}")
        if value not in normalized:
            normalized.append(value)
    return normalized


def _load_graph_snapshot(snapshot_path: Path) -> dict[str, Any]:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Export batch input must be a JSON object")
    return payload


def _verify_manifest_shape(
    manifest: dict[str, Any],
    failures: list[dict[str, str]],
    manifest_path: Path,
) -> None:
    if manifest.get("schema") != EXPORT_BATCH_SCHEMA:
        _add_failure(
            failures,
            "manifestSchemaMismatch",
            f"Expected {EXPORT_BATCH_SCHEMA}",
            manifest_path,
        )
    exports = manifest.get("exports")
    if not isinstance(exports, list):
        _add_failure(failures, "manifestExportsInvalid", "exports must be a list", manifest_path)
        return
    for index, entry in enumerate(exports):
        if not isinstance(entry, dict):
            _add_failure(
                failures,
                "exportEntryInvalid",
                "Export entries must be objects",
                manifest_path,
            )
            continue
        entry_path = entry.get("path")
        if not isinstance(entry_path, str) or not entry_path:
            _add_failure(
                failures,
                "exportPathInvalid",
                f"Export entry {index} must include a relative path",
                manifest_path,
            )
        elif not _is_safe_manifest_path(entry_path):
            _add_failure(
                failures,
                "exportPathUnsafe",
                f"Export path {entry_path!r} must stay inside the batch directory",
                manifest_path,
            )
        if not isinstance(entry.get("bytes"), int):
            _add_failure(
                failures,
                "exportBytesInvalid",
                f"Export entry {index} must include integer bytes",
                manifest_path,
            )
        sha256 = entry.get("sha256")
        if (
            not isinstance(sha256, str)
            or len(sha256) != 64
            or any(character not in "0123456789abcdef" for character in sha256)
        ):
            _add_failure(
                failures,
                "exportDigestInvalid",
                f"Export entry {index} must include a SHA-256 digest",
                manifest_path,
            )


def _summary_bytes(summary: Any) -> int:
    if isinstance(summary, dict) and isinstance(summary.get("bytes"), int):
        return int(summary["bytes"])
    return 0


def _verify_manifest_artifacts(
    manifest: dict[str, Any],
    failures: list[dict[str, str]],
    batch_dir: Path,
) -> None:
    exports = manifest.get("exports")
    if not isinstance(exports, list):
        return
    for entry in exports:
        if not isinstance(entry, dict):
            continue
        entry_path = entry.get("path")
        if not isinstance(entry_path, str) or not _is_safe_manifest_path(entry_path):
            continue
        output_path = batch_dir / entry_path
        try:
            data = output_path.read_bytes()
        except FileNotFoundError:
            _add_failure(failures, "exportMissing", f"Missing export {entry_path}", output_path)
            continue
        expected_bytes = entry.get("bytes")
        if isinstance(expected_bytes, int) and expected_bytes != len(data):
            _add_failure(
                failures,
                "exportBytesMismatch",
                f"Export {entry_path} byte count changed",
                output_path,
            )
        expected_sha256 = entry.get("sha256")
        if (
            isinstance(expected_sha256, str)
            and expected_sha256 != hashlib.sha256(data).hexdigest()
        ):
            _add_failure(
                failures,
                "exportDigestMismatch",
                f"Export {entry_path} SHA-256 changed",
                output_path,
            )


def _is_safe_manifest_path(path: str) -> bool:
    member_path = Path(path)
    return bool(path) and not member_path.is_absolute() and ".." not in member_path.parts


def _validate_archive_members(
    members: Sequence[tarfile.TarInfo],
    archive_path: Path,
    failures: list[dict[str, str]],
) -> None:
    seen_names: set[str] = set()
    for member in members:
        failure_path = Path(f"{archive_path}:{member.name}")
        if not _is_safe_manifest_path(member.name):
            _add_failure(
                failures,
                "archiveMemberPathInvalid",
                "Archive member path must be export-batch-local",
                failure_path,
            )
        elif member.name in seen_names:
            _add_failure(
                failures,
                "archiveMemberDuplicate",
                "Archive member path must be unique",
                failure_path,
            )
        seen_names.add(member.name)
        if not member.isfile():
            _add_failure(
                failures,
                "archiveMemberTypeInvalid",
                "Archive member must be a regular file",
                failure_path,
            )
        if (
            member.uid != 0
            or member.gid != 0
            or member.uname
            or member.gname
            or member.mtime != 0
            or member.mode != 0o644
        ):
            _add_failure(
                failures,
                "archiveMemberMetadataInvalid",
                "Archive member metadata is not deterministic",
                failure_path,
            )


def _extract_archive_members(
    archive: tarfile.TarFile,
    members: Sequence[tarfile.TarInfo],
    batch_dir: Path,
    failures: list[dict[str, str]],
) -> None:
    for member in members:
        if not _is_safe_manifest_path(member.name):
            continue
        target = batch_dir / member.name
        source = archive.extractfile(member)
        if source is None:
            _add_failure(
                failures,
                "archiveMemberUnreadable",
                "Archive member could not be read",
                target,
            )
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read())


def _archive_members(batch_dir: Path, *, exclude: Path | None = None) -> list[Path]:
    batch_dir = batch_dir.resolve()
    excluded = exclude.resolve() if exclude is not None else None
    return sorted(
        [
            path
            for path in batch_dir.rglob("*")
            if path.is_file() and path.resolve() != excluded
        ],
        key=lambda path: path.relative_to(batch_dir).as_posix(),
    )


def _write_deterministic_tar_gz(
    batch_dir: Path,
    members: Sequence[Path],
    output: BinaryIO,
) -> None:
    batch_dir = batch_dir.resolve()
    with GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as gzip_file:
        with tarfile.open(fileobj=gzip_file, mode="w") as archive:
            for member in members:
                relative = member.relative_to(batch_dir).as_posix()
                info = archive.gettarinfo(str(member), arcname=relative)
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                info.mode = 0o644
                with member.open("rb") as member_file:
                    archive.addfile(info, member_file)


def _snapshot_stats(snapshot: dict[str, Any]) -> dict[str, int]:
    stats = snapshot.get("stats")
    if (
        isinstance(stats, dict)
        and isinstance(stats.get("nodes"), int)
        and isinstance(stats.get("edges"), int)
    ):
        return {"nodes": int(stats["nodes"]), "edges": int(stats["edges"])}
    nodes = snapshot.get("nodes")
    edges = snapshot.get("edges")
    return {
        "nodes": len(nodes) if isinstance(nodes, list) else 0,
        "edges": len(edges) if isinstance(edges, list) else 0,
    }


def _write_export(
    output_dir: Path,
    export_format: str,
    graph: CSRDependencyGraph,
    *,
    root: str | None,
    ecosystem: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    filename, media_type = _EXPORT_FILES[export_format]
    output_path = output_dir / filename
    content = _export_content(
        export_format,
        graph,
        root=root,
        ecosystem=ecosystem,
        snapshot=snapshot,
    )
    output_path.write_text(content, encoding="utf-8")
    data = output_path.read_bytes()
    return {
        "format": export_format,
        "path": filename,
        "mediaType": media_type,
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
    }


def _export_content(
    export_format: str,
    graph: CSRDependencyGraph,
    *,
    root: str | None,
    ecosystem: str,
    snapshot: dict[str, Any],
) -> str:
    if export_format == "cypher":
        return CypherExporter.export_to_cypher(graph) + "\n"
    if export_format == "cyclonedx":
        return (
            CycloneDXExporter.export_to_json(
                graph,
                root=root,
                ecosystem=ecosystem,
                timestamp=DETERMINISTIC_CYCLONEDX_TIMESTAMP,
            )
            + "\n"
        )
    if export_format == "json":
        return (
            GraphJsonExporter.export_to_json(graph, root=root, ecosystem=ecosystem)
            + "\n"
        )
    raise ValueError(f"Unsupported export batch format: {export_format}")


def _add_failure(
    failures: list[dict[str, str]],
    code: str,
    message: str,
    path: Path,
) -> None:
    failures.append({"code": code, "message": message, "path": str(path)})
