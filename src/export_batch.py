"""Batch export EDGP graph snapshots into local egress artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.output.cypher_export import CypherExporter
from src.output.json_export import GraphJsonExporter
from src.output.sbom_security import CycloneDXExporter

EXPORT_BATCH_SCHEMA = "edgp.export.batch.v1"
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
