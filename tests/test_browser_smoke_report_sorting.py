"""Browser smoke page tests for static graph report sorting."""

from scripts.browser_smoke_report_sorting import render_sorting_smoke_page


def test_sorting_smoke_page_embeds_report_and_browser_checks() -> None:
    html = render_sorting_smoke_page()

    assert "EDGP Snapshot Report - sorting-smoke==1.0.0" in html
    assert 'data-testid="browser-smoke-panel"' in html
    assert 'data-testid="browser-smoke-result"' in html
    assert "initial edge target order" in html
    assert "edge target descending" in html
    assert "node package ascending" in html
    assert "document.documentElement.dataset.browserSmokeStatus = 'pass'" in html
    assert "alpha==1.0.0" in html
    assert "zeta==1.0.0" in html
