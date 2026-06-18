"""Generate a self-checking browser smoke page for bundle catalog filters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.output.html_report import render_report

SMOKE_OUTPUT_PATH = Path("/tmp/edgp-bundle-catalog-filters-smoke.html")
SMOKE_INPUT_PATH = REPO_ROOT / "tests" / "fixtures" / "bundle-catalog.json"


def render_bundle_catalog_filter_smoke_page() -> str:
    report = json.loads(SMOKE_INPUT_PATH.read_text(encoding="utf-8"))
    html = render_report(report)
    panel = """
<section class="panel browser-smoke" data-testid="browser-smoke-panel">
  <div class="section-head">
    <h2>Browser Smoke</h2>
    <span data-testid="browser-smoke-status">pending</span>
  </div>
  <pre data-testid="browser-smoke-result">pending</pre>
</section>""".strip()
    script = f"<script>{_browser_smoke_script()}</script>"
    html = html.replace("</main>", f"{panel}\n</main>")
    return html.replace("</body>", f"{script}\n</body>")


def write_bundle_catalog_filter_smoke_page(
    output_path: Path = SMOKE_OUTPUT_PATH,
) -> Path:
    output_path.write_text(
        render_bundle_catalog_filter_smoke_page(),
        encoding="utf-8",
    )
    return output_path


def _browser_smoke_script() -> str:
    return r"""
(() => {
  const result = document.querySelector('[data-testid="browser-smoke-result"]');
  const status = document.querySelector('[data-testid="browser-smoke-status"]');
  const params = new URLSearchParams(window.location.search);
  if (params.get('smokeCatalogReady') !== '1') {
    params.set('smokeCatalogReady', '1');
    params.set('catalogSource', 'npm-diagnostics');
    params.set('catalogStatus', 'warn');
    params.set('catalogProblems', '1');
    params.set('catalogQuery', 'diagnostics');
    window.location.search = params.toString();
    return;
  }
  const panel = document.querySelector('[data-bundle-catalog-filter-panel]');
  const search = panel?.querySelector('[data-bundle-catalog-search]');
  const source = panel?.querySelector('[data-bundle-catalog-source]');
  const triage = panel?.querySelector('[data-bundle-catalog-status]');
  const problems = panel?.querySelector('[data-bundle-catalog-problems]');
  const reset = panel?.querySelector('[data-bundle-catalog-reset]');
  const count = panel?.querySelector('[data-bundle-catalog-filter-count]');
  const rows = () => Array.from(document.querySelectorAll('[data-bundle-catalog-row]'));
  const visibleRows = () => rows().filter((row) => !row.hidden);
  const expect = (label, actual, expected) => {
    if (actual !== expected) {
      throw new Error(`${label}: expected ${expected}, got ${actual}`);
    }
  };
  const expectList = (label, actual, expected) => {
    const actualText = actual.join('|');
    const expectedText = expected.join('|');
    if (actualText !== expectedText) {
      throw new Error(`${label}: expected ${expectedText}, got ${actualText}`);
    }
  };
  const readCatalogParams = () => {
    const current = new URLSearchParams(window.location.search);
    return {
      query: current.get('catalogQuery') || '',
      source: current.get('catalogSource') || '',
      status: current.get('catalogStatus') || '',
      problems: current.get('catalogProblems') || '',
    };
  };
  const applySearch = (value) => {
    search.value = value;
    search.dispatchEvent(new Event('input', { bubbles: true }));
  };
  try {
    if (!panel || !search || !source || !triage || !problems || !reset || !count) {
      throw new Error('Missing bundle catalog filter controls');
    }
    expect('initial query', search.value, 'diagnostics');
    expect('initial source kind', source.value, 'npm-diagnostics');
    expect('initial triage status', triage.value, 'warn');
    expect('initial problem-only toggle', String(problems.checked), 'true');
    expect('initial filtered count', count.textContent, '1 of 2 rows');
    expect('initial visible rows', visibleRows().length, 1);
    expectList(
      'initial visible source kind',
      visibleRows().map((row) => row.dataset.sourceKind),
      ['npm-diagnostics'],
    );
    const initialParams = readCatalogParams();
    expect('initial URL query', initialParams.query, 'diagnostics');
    expect('initial URL source kind', initialParams.source, 'npm-diagnostics');
    expect('initial URL status', initialParams.status, 'warn');
    expect('initial URL problems', initialParams.problems, '1');
    applySearch('bundle');
    expect('updated query', search.value, 'bundle');
    expect('updated URL query', readCatalogParams().query, 'bundle');
    expect('updated filtered count', count.textContent, '0 of 2 rows');
    reset.click();
    expect('reset query', search.value, '');
    expect('reset source kind', source.value, '');
    expect('reset triage status', triage.value, '');
    expect('reset problem-only toggle', String(problems.checked), 'false');
    expect('reset filtered count', count.textContent, '2 of 2 rows');
    expect('reset visible rows', visibleRows().length, 2);
    const resetParams = readCatalogParams();
    expect('reset URL query', resetParams.query, '');
    expect('reset URL source kind', resetParams.source, '');
    expect('reset URL status', resetParams.status, '');
    expect('reset URL problems', resetParams.problems, '');
    const payload = { ok: true, checks: 24 };
    document.documentElement.dataset.browserSmokeStatus = 'pass';
    status.textContent = 'PASS';
    result.textContent = JSON.stringify(payload, null, 2);
  } catch (error) {
    const payload = { ok: false, message: String(error && error.message || error) };
    document.documentElement.dataset.browserSmokeStatus = 'fail';
    status.textContent = 'FAIL';
    result.textContent = JSON.stringify(payload, null, 2);
  }
})();
""".strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=SMOKE_OUTPUT_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_path = write_bundle_catalog_filter_smoke_page(args.output)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
