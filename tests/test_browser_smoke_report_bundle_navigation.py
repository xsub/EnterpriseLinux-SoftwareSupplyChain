"""Browser smoke bundle tests for static report index navigation."""

from scripts.browser_smoke_report_bundle_navigation import write_bundle_navigation_smoke


def test_bundle_navigation_smoke_writes_index_members_and_browser_checks(
    tmp_path,
) -> None:
    index_path = write_bundle_navigation_smoke(tmp_path)

    assert index_path == tmp_path / "index.html"
    assert (tmp_path / "001-snapshot-right.html").exists()
    assert (tmp_path / "002-npm-diagnostics-report.html").exists()
    assert (tmp_path / "003-impact-report.html").exists()
    assert (tmp_path / "manifest.json").exists()

    html = index_path.read_text(encoding="utf-8")
    assert 'data-testid="report-bundle-index"' in html
    assert 'data-testid="browser-smoke-panel"' in html
    assert 'data-testid="browser-smoke-frame"' in html
    assert 'data-testid="browser-smoke-result"' in html
    assert "bundle link order" in html
    assert "001-snapshot-right.html" in html
    assert "002-npm-diagnostics-report.html" in html
    assert "003-impact-report.html" in html
    assert "document.documentElement.dataset.browserSmokeStatus = 'pass'" in html
