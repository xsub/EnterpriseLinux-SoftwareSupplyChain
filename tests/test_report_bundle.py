"""Report bundle tests for static EDGP HTML indexes and manifests."""

import hashlib
import json
from pathlib import Path

from src.output.report_bundle import verify_report_bundle, write_report_bundle


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


def _normalize_failure_paths(
    failures: object,
    bundle_dir: str,
) -> list[dict[str, object]]:
    normalized = []
    if not isinstance(failures, list):
        return normalized
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        item = dict(failure)
        if bundle_dir and isinstance(item.get("path"), str):
            item["path"] = item["path"].replace(bundle_dir, "<bundle-dir>", 1)
        normalized.append(item)
    return normalized
