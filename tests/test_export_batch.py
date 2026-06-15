"""Batch export tests for local graph egress artifacts."""

import hashlib
import io
import json
import tarfile
from pathlib import Path

from src.cli import main
from src.export_batch import (
    DETERMINISTIC_CYCLONEDX_TIMESTAMP,
    graph_from_snapshot,
    verify_graph_export_batch,
    verify_graph_export_batch_archive,
    write_graph_export_batch,
    write_graph_export_batch_archive,
)
from src.schema_validation import validate_target


def test_graph_from_snapshot_reconstructs_edges_and_metadata() -> None:
    snapshot = json.loads(Path("tests/fixtures/snapshot-right.json").read_text())

    graph = graph_from_snapshot(snapshot)

    assert graph.get_dependencies("app==1.0.0") == ["lib==2.0.0"]
    assert graph.get_dependencies("lib==2.0.0") == ["core==1.0.0"]
    assert graph.get_vertex_metadata("lib==2.0.0")["license"] == "MIT"


def test_write_graph_export_batch_writes_manifest_and_artifacts(tmp_path) -> None:
    manifest = write_graph_export_batch(
        Path("tests/fixtures/snapshot-right.json"),
        tmp_path,
        formats=["cypher", "cyclonedx", "json", "cypher"],
        command="edgp export-batch --snapshot tests/fixtures/snapshot-right.json",
    )

    assert manifest["schema"] == "edgp.export.batch.v1"
    assert manifest["source"]["root"] == "app==1.0.0"
    assert manifest["source"]["ecosystem"] == "npm"
    assert manifest["source"]["stats"] == {"edges": 2, "nodes": 3}
    assert manifest["summary"]["formats"] == ["cypher", "cyclonedx", "json"]
    assert manifest["summary"]["exports"] == 3

    manifest_path = tmp_path / "manifest.json"
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    exports = {entry["format"]: entry for entry in manifest["exports"]}
    cypher = (tmp_path / exports["cypher"]["path"]).read_text(encoding="utf-8")
    assert "CREATE CONSTRAINT package_id_unique" in cypher
    assert 'MERGE (:Package {id: "app==1.0.0"});' in cypher

    cyclonedx = json.loads(
        (tmp_path / exports["cyclonedx"]["path"]).read_text(encoding="utf-8")
    )
    assert cyclonedx["bomFormat"] == "CycloneDX"
    assert cyclonedx["metadata"]["timestamp"] == DETERMINISTIC_CYCLONEDX_TIMESTAMP

    for entry in manifest["exports"]:
        data = (tmp_path / entry["path"]).read_bytes()
        assert entry["bytes"] == len(data)
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()


def test_cli_export_batch_writes_selected_formats(tmp_path, capsys) -> None:
    assert (
        main(
            [
                "export-batch",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(tmp_path),
                "--format",
                "cypher",
                "--format",
                "cyclonedx",
            ]
        )
        == 0
    )

    manifest = json.loads(capsys.readouterr().out)

    assert manifest["schema"] == "edgp.export.batch.v1"
    assert manifest["summary"]["formats"] == ["cypher", "cyclonedx"]
    assert (tmp_path / "graph.cypher").exists()
    assert (tmp_path / "graph.cyclonedx.json").exists()
    assert not (tmp_path / "graph.snapshot.json").exists()
    assert json.loads((tmp_path / "manifest.json").read_text()) == manifest


def test_verify_graph_export_batch_checks_artifact_fingerprints(tmp_path) -> None:
    write_graph_export_batch(
        Path("tests/fixtures/snapshot-right.json"),
        tmp_path,
        formats=["cypher", "cyclonedx"],
    )

    report = verify_graph_export_batch(tmp_path)

    assert report["schema"] == "edgp.export.batch.verification.v1"
    assert report["ok"] is True
    assert report["summary"]["exports"] == 2
    assert report["summary"]["failures"] == 0
    assert report["manifestSha256"]

    (tmp_path / "graph.cypher").write_text("tampered\n", encoding="utf-8")

    tampered = verify_graph_export_batch(tmp_path)

    assert tampered["ok"] is False
    assert {
        failure["code"] for failure in tampered["failures"]
    } == {"exportBytesMismatch", "exportDigestMismatch"}


def test_cli_verify_export_batch_and_validate_directory(tmp_path, capsys) -> None:
    write_graph_export_batch(
        Path("tests/fixtures/snapshot-right.json"),
        tmp_path,
        formats=["cypher", "cyclonedx"],
    )

    assert (
        main(["verify-export-batch", "--path", str(tmp_path), "--format", "text"])
        == 0
    )
    assert capsys.readouterr().out.startswith("OK exports=2")

    validation = validate_target(tmp_path)

    assert validation["ok"] is True
    assert validation["targetType"] == "export-batch"
    assert validation["contract"] == "edgp.export.batch.v1"
    assert validation["exportBatchVerification"]["ok"] is True


def test_write_export_batch_archive_is_deterministic_and_verifiable(tmp_path) -> None:
    write_graph_export_batch(
        Path("tests/fixtures/snapshot-right.json"),
        tmp_path,
        formats=["cypher", "cyclonedx"],
    )

    archive_path = tmp_path / "export-batch.tar.gz"
    report = write_graph_export_batch_archive(tmp_path, archive_path)

    assert report["schema"] == "edgp.export.batch.archive.v1"
    assert report["ok"] is True
    assert report["archiveSha256"] == hashlib.sha256(
        archive_path.read_bytes()
    ).hexdigest()
    assert report["summary"]["files"] == 3
    assert report["summary"]["verificationFailures"] == 0
    assert report["verification"]["ok"] is True

    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
        infos = {member.name: member for member in archive.getmembers()}

    assert names == ["graph.cyclonedx.json", "graph.cypher", "manifest.json"]
    assert "export-batch.tar.gz" not in names
    assert {member.mtime for member in infos.values()} == {0}
    assert {member.uid for member in infos.values()} == {0}
    assert {member.gid for member in infos.values()} == {0}
    assert {member.mode for member in infos.values()} == {0o644}

    second_report = write_graph_export_batch_archive(tmp_path, archive_path)
    assert second_report["archiveSha256"] == report["archiveSha256"]

    verification = verify_graph_export_batch_archive(archive_path)
    assert verification["schema"] == "edgp.export.batch.archive.v1"
    assert verification["ok"] is True
    assert verification["archiveSha256"] == report["archiveSha256"]
    assert verification["manifestSha256"] == report["manifestSha256"]
    assert verification["verification"]["ok"] is True

    validation = validate_target(archive_path)
    assert validation["ok"] is True
    assert validation["targetType"] == "export-batch-archive"
    assert validation["contract"] == "edgp.export.batch.archive.v1"

    (tmp_path / "graph.cypher").write_text("tampered\n", encoding="utf-8")
    failed_report = write_graph_export_batch_archive(tmp_path, tmp_path / "failed.tar.gz")
    assert failed_report["ok"] is False
    assert failed_report["archiveSha256"] is None
    assert failed_report["summary"]["verificationFailures"] == 2


def test_cli_archive_export_batch_and_verify_archive(tmp_path, capsys) -> None:
    write_graph_export_batch(
        Path("tests/fixtures/snapshot-right.json"),
        tmp_path,
        formats=["cypher", "cyclonedx"],
    )
    archive_path = tmp_path / "batch.tgz"

    assert (
        main(
            [
                "archive-export-batch",
                "--path",
                str(tmp_path),
                "--output",
                str(archive_path),
                "--format",
                "text",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.startswith("OK files=3")

    assert (
        main(
            [
                "verify-export-batch-archive",
                "--path",
                str(archive_path),
                "--format",
                "text",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.startswith("OK files=3")


def test_verify_export_batch_archive_rejects_unsafe_members(tmp_path, capsys) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    payload = b"unsafe"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("../evil.txt")
        info.size = len(payload)
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.mtime = 0
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(payload))

    report = verify_graph_export_batch_archive(archive_path)

    assert report["schema"] == "edgp.export.batch.archive.v1"
    assert report["ok"] is False
    assert report["archiveSha256"] == hashlib.sha256(
        archive_path.read_bytes()
    ).hexdigest()
    assert report["summary"]["files"] == 1
    assert report["summary"]["verificationFailures"] == 1
    assert report["verification"]["failures"][0]["code"] == "archiveMemberPathInvalid"

    assert (
        main(
            [
                "verify-export-batch-archive",
                "--path",
                str(archive_path),
                "--format",
                "text",
            ]
        )
        == 1
    )
    assert capsys.readouterr().out.startswith("FAIL files=1")
