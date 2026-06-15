"""Report bundle tests for static EDGP HTML indexes and manifests."""

import hashlib
import io
import json
import tarfile
from pathlib import Path

from src.cli import main
from src.output.report_bundle import (
    build_report_bundle_submission_plan,
    verify_report_bundle,
    verify_report_bundle_archive,
    write_report_bundle,
    write_report_bundle_archive,
)


def test_write_report_bundle_renders_index_and_member_reports(tmp_path) -> None:
    index_path = write_report_bundle(
        [
            Path("tests/fixtures/snapshot-right.json"),
            Path("tests/fixtures/impact-report.json"),
            Path("tests/fixtures/advisory-report.json"),
            Path("tests/fixtures/npm-diagnostics-report.json"),
        ],
        tmp_path,
    )

    assert index_path == tmp_path / "index.html"
    index_html = index_path.read_text(encoding="utf-8")
    assert index_html.startswith("<!doctype html>")
    assert 'data-testid="report-bundle-index"' in index_html
    assert 'data-testid="report-bundle-verification"' in index_html
    assert "001-snapshot-right.html" in index_html
    assert "004-npm-diagnostics-report.html" in index_html
    assert "edgp.npm.diagnostics.v1" in index_html
    assert "conflict-app==1.0.0" in index_html

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "edgp.report.bundle.v1"
    assert manifest["bundleSha256"] == _manifest_sha256(manifest)
    assert manifest["index"] == "index.html"
    assert manifest["reportCount"] == 4
    assert manifest["bundleSha256"][:12] in index_html
    assert manifest["reports"][3]["href"] == "004-npm-diagnostics-report.html"
    assert manifest["reports"][3]["summary"]["unresolvedDependencies"] == 1
    assert manifest["reports"][3]["htmlSha256"] == hashlib.sha256(
        (tmp_path / "004-npm-diagnostics-report.html").read_bytes()
    ).hexdigest()
    assert manifest["reports"][3]["sourceSha256"] == hashlib.sha256(
        Path("tests/fixtures/npm-diagnostics-report.json").read_bytes()
    ).hexdigest()

    npm_html = (tmp_path / "004-npm-diagnostics-report.html").read_text(
        encoding="utf-8"
    )
    assert 'data-testid="npm-conflicts-panel"' in npm_html
    assert "missing" in npm_html


def test_write_report_bundle_can_include_triage_summary(tmp_path) -> None:
    index_path = write_report_bundle(
        [
            Path("tests/fixtures/advisory-report.json"),
            Path("tests/fixtures/npm-diagnostics-report.json"),
        ],
        tmp_path,
        include_triage_summary=True,
    )

    index_html = index_path.read_text(encoding="utf-8")
    assert 'data-testid="report-bundle-triage-summary"' in index_html
    assert "triage-summary.html" in index_html

    triage_json_path = tmp_path / "triage-summary.json"
    triage_html_path = tmp_path / "triage-summary.html"
    triage = json.loads(triage_json_path.read_text(encoding="utf-8"))
    assert triage["schema"] == "edgp.triage.summary.v1"
    assert triage["status"] == "fail"
    assert triage["summary"]["reports"] == 2
    assert triage["summary"]["failedChecks"] == 1
    assert 'data-testid="triage-checks-panel"' in triage_html_path.read_text(
        encoding="utf-8"
    )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundleSha256"] == _manifest_sha256(manifest)
    assert manifest["reportCount"] == 2
    assert manifest["triageSummary"]["href"] == "triage-summary.html"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    assert manifest["triageSummary"]["schema"] == "edgp.triage.summary.v1"
    assert manifest["triageSummary"]["sourceSha256"] == hashlib.sha256(
        triage_json_path.read_bytes()
    ).hexdigest()
    assert manifest["triageSummary"]["htmlSha256"] == hashlib.sha256(
        triage_html_path.read_bytes()
    ).hexdigest()
    assert verify_report_bundle(tmp_path)["ok"] is True


def test_verify_report_bundle_reports_tampered_member_html(tmp_path) -> None:
    write_report_bundle(
        [
            Path("tests/fixtures/snapshot-right.json"),
            Path("tests/fixtures/npm-diagnostics-report.json"),
        ],
        tmp_path,
    )

    assert verify_report_bundle(tmp_path)["ok"] is True

    (tmp_path / "002-npm-diagnostics-report.html").write_text(
        "<!doctype html><title>tampered</title>",
        encoding="utf-8",
    )

    report = verify_report_bundle(tmp_path)
    assert report["ok"] is False
    assert report["summary"]["failures"] == 1
    assert report["failures"][0]["code"] == "htmlDigestMismatch"


def test_verify_report_bundle_reports_tampered_triage_summary_html(tmp_path) -> None:
    write_report_bundle(
        [
            Path("tests/fixtures/advisory-report.json"),
            Path("tests/fixtures/npm-diagnostics-report.json"),
        ],
        tmp_path,
        include_triage_summary=True,
    )

    assert verify_report_bundle(tmp_path)["ok"] is True

    (tmp_path / "triage-summary.html").write_text(
        "<!doctype html><title>tampered triage</title>",
        encoding="utf-8",
    )

    report = verify_report_bundle(tmp_path)
    assert report["ok"] is False
    assert report["summary"]["failures"] == 1
    assert report["failures"][0]["code"] == "triageSummaryHtmlDigestMismatch"


def test_write_report_bundle_archive_is_deterministic_and_verification_gated(
    tmp_path,
) -> None:
    write_report_bundle(
        [
            Path("tests/fixtures/snapshot-right.json"),
            Path("tests/fixtures/npm-diagnostics-report.json"),
        ],
        tmp_path,
        include_triage_summary=True,
    )

    archive_path = tmp_path / "bundle.tar.gz"
    report = write_report_bundle_archive(tmp_path, archive_path)

    assert report["schema"] == "edgp.report.bundle.archive.v1"
    assert report["ok"] is True
    assert report["archive"] == str(archive_path)
    assert report["bundleSha256"] == json.loads(
        (tmp_path / "manifest.json").read_text(encoding="utf-8")
    )["bundleSha256"]
    assert report["archiveSha256"] == hashlib.sha256(
        archive_path.read_bytes()
    ).hexdigest()
    assert report["summary"]["files"] == 6
    assert report["summary"]["verificationFailures"] == 0
    assert report["verification"]["ok"] is True

    with tarfile.open(archive_path, "r:gz") as archive:
        names = archive.getnames()
        infos = {member.name: member for member in archive.getmembers()}

    assert names == [
        "001-snapshot-right.html",
        "002-npm-diagnostics-report.html",
        "index.html",
        "manifest.json",
        "triage-summary.html",
        "triage-summary.json",
    ]
    assert "bundle.tar.gz" not in names
    assert {member.mtime for member in infos.values()} == {0}
    assert {member.uid for member in infos.values()} == {0}
    assert {member.gid for member in infos.values()} == {0}
    assert {member.mode for member in infos.values()} == {0o644}

    second_report = write_report_bundle_archive(tmp_path, archive_path)
    assert second_report["archiveSha256"] == report["archiveSha256"]

    verification_report = verify_report_bundle_archive(archive_path)
    assert verification_report["schema"] == "edgp.report.bundle.archive.v1"
    assert verification_report["ok"] is True
    assert verification_report["archive"] == str(archive_path.resolve())
    assert verification_report["archiveSha256"] == report["archiveSha256"]
    assert verification_report["bundleSha256"] == report["bundleSha256"]
    assert verification_report["summary"]["files"] == 6
    assert verification_report["summary"]["verificationFailures"] == 0
    assert verification_report["verification"]["ok"] is True

    (tmp_path / "001-snapshot-right.html").write_text(
        "<!doctype html><title>tampered</title>",
        encoding="utf-8",
    )
    failed_report = write_report_bundle_archive(tmp_path, tmp_path / "failed.tar.gz")
    assert failed_report["ok"] is False
    assert failed_report["archiveSha256"] is None
    assert failed_report["summary"]["verificationFailures"] == 1
    assert failed_report["verification"]["failures"][0]["code"] == "htmlDigestMismatch"


def test_verify_report_bundle_archive_rejects_unsafe_members(tmp_path) -> None:
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

    report = verify_report_bundle_archive(archive_path)

    assert report["schema"] == "edgp.report.bundle.archive.v1"
    assert report["ok"] is False
    assert report["archiveSha256"] == hashlib.sha256(
        archive_path.read_bytes()
    ).hexdigest()
    assert report["summary"]["files"] == 1
    assert report["summary"]["verificationFailures"] == 1
    assert report["verification"]["failures"][0]["code"] == "archiveMemberPathInvalid"


def test_verify_report_bundle_archive_matches_missing_archive_fixture() -> None:
    report = verify_report_bundle_archive(
        Path("tests/fixtures/missing-report-bundle.tar.gz")
    )
    expected = json.loads(
        Path(
            "tests/fixtures/report-bundle-archive-verification-missing-archive.json"
        ).read_text(encoding="utf-8")
    )

    assert _normalize_archive_verification_report(report) == expected


def test_build_report_bundle_submission_plan_for_directory(tmp_path) -> None:
    source_path = tmp_path / "snapshot-right.json"
    source_path.write_text(
        Path("tests/fixtures/snapshot-right.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    write_report_bundle([source_path], tmp_path, include_triage_summary=True)

    plan = build_report_bundle_submission_plan(
        tmp_path,
        target="workbench",
        endpoint="https://workbench.example/api/bundles",
    )

    assert plan["schema"] == "edgp.report.bundle.submission_plan.v1"
    assert plan["mode"] == "dry-run"
    assert plan["ok"] is True
    assert plan["target"] == {
        "kind": "workbench",
        "endpoint": "https://workbench.example/api/bundles",
    }
    assert plan["source"]["inputType"] == "directory"
    assert plan["source"]["archiveSha256"] is None
    assert plan["summary"]["reports"] == 1
    assert plan["summary"]["failures"] == 0
    assert [artifact["role"] for artifact in plan["artifacts"]] == [
        "manifest",
        "index",
        "report-html",
        "report-source",
        "triage-html",
        "triage-source",
    ]
    assert {artifact["action"] for artifact in plan["artifacts"]} == {
        "report-bundle-import"
    }
    assert {artifact["method"] for artifact in plan["artifacts"]} == {"POST"}
    assert plan["summary"]["bytes"] == sum(
        artifact["bytes"] for artifact in plan["artifacts"]
    )


def test_build_report_bundle_submission_plan_for_archive_rag_target(tmp_path) -> None:
    source_path = tmp_path / "snapshot-right.json"
    source_path.write_text(
        Path("tests/fixtures/snapshot-right.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    write_report_bundle([source_path], tmp_path, include_triage_summary=True)
    archive_path = tmp_path / "bundle.tar.gz"
    archive_report = write_report_bundle_archive(tmp_path, archive_path)

    plan = build_report_bundle_submission_plan(
        archive_path,
        target="rag",
        endpoint="https://rag.example/api/context",
    )

    assert plan["ok"] is True
    assert plan["source"]["inputType"] == "archive"
    assert plan["source"]["archiveSha256"] == archive_report["archiveSha256"]
    assert [artifact["role"] for artifact in plan["artifacts"]] == [
        "manifest",
        "report-source",
        "triage-source",
    ]
    assert {artifact["mediaType"] for artifact in plan["artifacts"]} == {
        "application/json"
    }
    assert {artifact["action"] for artifact in plan["artifacts"]} == {
        "rag-context-import"
    }


def test_cli_report_bundle_submission_plan_writes_output_and_text(
    tmp_path,
    capsys,
) -> None:
    source_path = tmp_path / "snapshot-right.json"
    source_path.write_text(
        Path("tests/fixtures/snapshot-right.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    write_report_bundle([source_path], tmp_path)
    plan_path = tmp_path / "bundle-submission-plan.json"

    assert (
        main(
            [
                "plan-bundle-submission",
                "--path",
                str(tmp_path),
                "--target",
                "generic",
                "--endpoint",
                "https://collector.example/upload",
                "--output",
                str(plan_path),
                "--format",
                "text",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out.startswith(
        "OK target=generic reports=1 artifacts=4"
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["schema"] == "edgp.report.bundle.submission_plan.v1"
    assert plan["ok"] is True
    assert [artifact["role"] for artifact in plan["artifacts"]] == [
        "manifest",
        "index",
        "report-html",
        "report-source",
    ]


def test_report_bundle_submission_plan_reports_verification_failure(tmp_path) -> None:
    write_report_bundle([Path("tests/fixtures/snapshot-right.json")], tmp_path)
    (tmp_path / "001-snapshot-right.html").write_text(
        "<!doctype html><title>tampered</title>",
        encoding="utf-8",
    )

    plan = build_report_bundle_submission_plan(
        tmp_path,
        target="workbench",
        endpoint="https://workbench.example/api/bundles",
    )

    assert plan["ok"] is False
    assert plan["summary"]["artifacts"] == 0
    assert plan["summary"]["failures"] == 1
    assert plan["failures"][0]["code"] == "htmlDigestMismatch"


def test_verify_report_bundle_matches_committed_failure_fixtures() -> None:
    cases = [
        (
            Path("tests/fixtures/tampered-report-bundle-manifest"),
            Path("tests/fixtures/report-bundle-verification-tampered-manifest.json"),
        ),
        (
            Path("tests/fixtures/tampered-report-bundle-member"),
            Path("tests/fixtures/report-bundle-verification-tampered-member.json"),
        ),
        (
            Path("tests/fixtures/missing-html-report-bundle"),
            Path("tests/fixtures/report-bundle-verification-missing-html.json"),
        ),
        (
            Path("tests/fixtures/missing-source-report-bundle"),
            Path("tests/fixtures/report-bundle-verification-missing-source.json"),
        ),
        (
            Path("tests/fixtures/invalid-manifest-missing-report-count-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-manifest-missing-report-count.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-report-missing-title-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-missing-title.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-manifest-unknown-field-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-manifest-unknown-field.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-report-unknown-field-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-unknown-field.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-bundle-source-kind-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-bundle-source-kind.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-report-digest-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-digest.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-bundle-metadata-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-bundle-metadata.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-index-path-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-index-path.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-manifest-schema-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-manifest-schema.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-bundle-digest-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-bundle-digest.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-reports-list-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-reports-list.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-report-entry-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-entry.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-report-field-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-field.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-report-summary-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-summary.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-report-count-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-count.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-report-href-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-href.json"
            ),
        ),
        (
            Path("tests/fixtures/missing-index-report-bundle"),
            Path("tests/fixtures/report-bundle-verification-missing-index.json"),
        ),
        (
            Path("tests/fixtures/source-digest-mismatch-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-source-digest-mismatch.json"
            ),
        ),
        (
            Path("tests/fixtures/missing-manifest-report-bundle"),
            Path("tests/fixtures/report-bundle-verification-missing-manifest.json"),
        ),
        (
            Path("tests/fixtures/invalid-json-manifest-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-json-manifest.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-manifest-type-bundle"),
            Path("tests/fixtures/report-bundle-verification-invalid-manifest-type.json"),
        ),
    ]

    for bundle_dir, fixture_path in cases:
        report = verify_report_bundle(bundle_dir)
        expected = json.loads(fixture_path.read_text(encoding="utf-8"))

        assert _normalize_verification_report(report) == expected


def _manifest_sha256(manifest: dict[str, object]) -> str:
    digest_payload = {
        key: value for key, value in manifest.items() if key != "bundleSha256"
    }
    canonical = json.dumps(
        digest_payload,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _normalize_verification_report(report: dict[str, object]) -> dict[str, object]:
    normalized = dict(report)
    bundle_dir = str(normalized.get("bundleDir", ""))
    normalized["bundleDir"] = "<bundle-dir>"
    if normalized.get("bundleSha256") is not None:
        normalized["bundleSha256"] = "<bundleSha256>"
    normalized["failures"] = _normalize_failure_paths(
        normalized.get("failures", []),
        bundle_dir,
    )
    return normalized


def _normalize_archive_verification_report(report: dict[str, object]) -> dict[str, object]:
    normalized = dict(report)
    archive_path = str(normalized.get("archive", ""))
    bundle_dir = str(normalized.get("bundleDir", ""))
    normalized["archive"] = "<archive>"
    normalized["bundleDir"] = "<bundle-dir>"
    if normalized.get("archiveSha256") is not None:
        normalized["archiveSha256"] = "<archiveSha256>"
    if normalized.get("bundleSha256") is not None:
        normalized["bundleSha256"] = "<bundleSha256>"
    verification = normalized.get("verification")
    if isinstance(verification, dict):
        nested = dict(verification)
        nested_bundle_dir = str(nested.get("bundleDir", bundle_dir))
        nested["bundleDir"] = "<bundle-dir>"
        if nested.get("bundleSha256") is not None:
            nested["bundleSha256"] = "<bundleSha256>"
        nested["failures"] = _normalize_failure_paths(
            nested.get("failures", []),
            nested_bundle_dir,
            archive_path=archive_path,
        )
        normalized["verification"] = nested
    return normalized


def _normalize_failure_paths(
    failures: object,
    bundle_dir: str,
    *,
    archive_path: str = "",
) -> list[dict[str, object]]:
    normalized = []
    if not isinstance(failures, list):
        return normalized
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        item = dict(failure)
        path = item.get("path")
        if isinstance(path, str):
            if archive_path:
                path = path.replace(archive_path, "<archive>", 1)
            if bundle_dir:
                path = path.replace(bundle_dir, "<bundle-dir>", 1)
            item["path"] = path
        normalized.append(item)
    return normalized
