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
    assert "001-snapshot-right.html" in index_html
    assert "004-npm-diagnostics-report.html" in index_html
    assert "edgp.npm.diagnostics.v1" in index_html
    assert "conflict-app==1.0.0" in index_html

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "edgp.report.bundle.v1"
    assert manifest["bundleSha256"] == _manifest_sha256(manifest)
    assert manifest["index"] == "index.html"
    assert manifest["reportCount"] == 4
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
