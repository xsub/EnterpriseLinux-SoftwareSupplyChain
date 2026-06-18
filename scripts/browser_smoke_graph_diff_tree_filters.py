"""Generate a self-checking browser smoke page for graph diff-tree filters."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.output.html_report import render_report

SMOKE_OUTPUT_PATH = Path("/tmp/edgp-graph-diff-tree-filters-smoke.html")
SMOKE_INPUT_PATH = REPO_ROOT / "tests" / "fixtures" / "graph-diff-tree.json"


def render_graph_diff_tree_filter_smoke_page() -> str:
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


def write_graph_diff_tree_filter_smoke_page(
    output_path: Path = SMOKE_OUTPUT_PATH,
) -> Path:
    output_path.write_text(
        render_graph_diff_tree_filter_smoke_page(),
        encoding="utf-8",
    )
    return output_path


def _browser_smoke_script() -> str:
    return r"""
(() => {
  const result = document.querySelector('[data-testid="browser-smoke-result"]');
  const status = document.querySelector('[data-testid="browser-smoke-status"]');
  const params = new URLSearchParams(window.location.search);
  if (params.get('smokeGraphDiffTreeReady') !== '1') {
    params.set('smokeGraphDiffTreeReady', '1');
    params.set('graphDiffTreeKind', 'upgrade');
    params.set('graphDiffTreeQuery', 'lib');
    window.location.search = params.toString();
    return;
  }
  const panel = document.querySelector('[data-graph-diff-tree-filter-panel]');
  const search = panel?.querySelector('[data-graph-diff-tree-search]');
  const kind = panel?.querySelector('[data-graph-diff-tree-kind]');
  const reset = panel?.querySelector('[data-graph-diff-tree-reset]');
  const count = panel?.querySelector('[data-graph-diff-tree-filter-count]');
  const rows = () => Array.from(document.querySelectorAll('[data-graph-diff-tree-row]'));
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
  const readDiffTreeParams = () => {
    const current = new URLSearchParams(window.location.search);
    return {
      query: current.get('graphDiffTreeQuery') || '',
      kind: current.get('graphDiffTreeKind') || '',
    };
  };
  const applySearch = (value) => {
    search.value = value;
    search.dispatchEvent(new Event('input', { bubbles: true }));
  };
  try {
    if (!panel || !search || !kind || !reset || !count) {
      throw new Error('Missing graph diff-tree filter controls');
    }
    expect('initial query', search.value, 'lib');
    expect('initial kind', kind.value, 'upgrade');
    expect('initial filtered count', count.textContent, '1 of 2 rows');
    expect('initial visible rows', visibleRows().length, 1);
    expectList(
      'initial visible change kind',
      visibleRows().map((row) => row.dataset.changeKind),
      ['upgrade'],
    );
    const initialParams = readDiffTreeParams();
    expect('initial URL query', initialParams.query, 'lib');
    expect('initial URL kind', initialParams.kind, 'upgrade');
    applySearch('core');
    expect('updated query', search.value, 'core');
    expect('updated URL query', readDiffTreeParams().query, 'core');
    expect('updated filtered count', count.textContent, '0 of 2 rows');
    reset.click();
    expect('reset query', search.value, '');
    expect('reset kind', kind.value, '');
    expect('reset filtered count', count.textContent, '2 of 2 rows');
    expect('reset visible rows', visibleRows().length, 2);
    const resetParams = readDiffTreeParams();
    expect('reset URL query', resetParams.query, '');
    expect('reset URL kind', resetParams.kind, '');
    const payload = { ok: true, checks: 16 };
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
    output_path = write_graph_diff_tree_filter_smoke_page(args.output)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
