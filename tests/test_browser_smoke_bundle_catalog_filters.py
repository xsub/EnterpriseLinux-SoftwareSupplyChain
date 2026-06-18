"""Browser smoke page tests for bundle catalog filter behavior."""

from scripts.browser_smoke_bundle_catalog_filters import (
    render_bundle_catalog_filter_smoke_page,
)


def test_bundle_catalog_filter_smoke_page_embeds_browser_checks() -> None:
    html = render_bundle_catalog_filter_smoke_page()

    assert "EDGP Bundle Catalog" in html
    assert 'data-testid="bundle-catalog-filter-panel"' in html
    assert 'data-testid="browser-smoke-panel"' in html
    assert 'data-testid="browser-smoke-result"' in html
    assert "smokeCatalogReady" in html
    assert "catalogSource" in html
    assert "catalogStatus" in html
    assert "catalogProblems" in html
    assert "catalogQuery" in html
    assert "initial filtered count" in html
    assert "updated URL query" in html
    assert "reset filtered count" in html
    assert "document.documentElement.dataset.browserSmokeStatus = 'pass'" in html
    assert "npm-diagnostics" in html
    assert "htmlDigestMismatch" in html
