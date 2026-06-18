"""Browser smoke page tests for graph-diff filter behavior."""

from scripts.browser_smoke_graph_diff_filters import render_graph_diff_filter_smoke_page


def test_graph_diff_filter_smoke_page_embeds_browser_checks() -> None:
    html = render_graph_diff_filter_smoke_page()

    assert "EDGP Graph Diff" in html
    assert 'data-testid="graph-diff-filter-panel"' in html
    assert 'data-testid="graph-diff-classification-panel"' in html
    assert 'data-testid="browser-smoke-panel"' in html
    assert 'data-testid="browser-smoke-result"' in html
    assert "smokeGraphDiffReady" in html
    assert "graphDiffKind" in html
    assert "graphDiffQuery" in html
    assert "initial filtered count" in html
    assert "updated URL query" in html
    assert "reset filtered count" in html
    assert "document.documentElement.dataset.browserSmokeStatus = 'pass'" in html
    assert "upgrade" in html
    assert "core==1.0.0" in html
