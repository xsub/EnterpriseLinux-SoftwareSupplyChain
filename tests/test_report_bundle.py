"""Report bundle tests for static EDGP HTML indexes and manifests."""

import hashlib
import json
from pathlib import Path

from src.output.report_bundle import write_report_bundle


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
