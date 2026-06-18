"""Browser smoke page tests for graph diff-tree filter behavior."""

from scripts.browser_smoke_graph_diff_tree_filters import (
    render_graph_diff_tree_filter_smoke_page,
)


def test_graph_diff_tree_filter_smoke_page_embeds_browser_checks() -> None:
    html = render_graph_diff_tree_filter_smoke_page()

    assert "EDGP Graph Diff Tree" in html
    assert 'data-testid="graph-diff-tree-filter-panel"' in html
    assert 'data-testid="graph-diff-tree-classification-panel"' in html
    assert 'data-testid="browser-smoke-panel"' in html
    assert 'data-testid="browser-smoke-result"' in html
    assert "smokeGraphDiffTreeReady" in html
    assert "graphDiffTreeKind" in html
    assert "graphDiffTreeQuery" in html
    assert "initial filtered count" in html
    assert "updated URL query" in html
    assert "reset filtered count" in html
    assert "document.documentElement.dataset.browserSmokeStatus = 'pass'" in html
    assert "upgrade" in html
    assert "core==1.0.0" in html
