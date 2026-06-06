"""Generate a self-checking browser smoke page for graph report sorting."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.output.html_report import render_snapshot_report

SMOKE_OUTPUT_PATH = Path("/tmp/edgp-report-sorting-smoke.html")


def render_sorting_smoke_page() -> str:
    html = render_snapshot_report(_sorting_snapshot())
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


def write_sorting_smoke_page(output_path: Path = SMOKE_OUTPUT_PATH) -> Path:
    output_path.write_text(render_sorting_smoke_page(), encoding="utf-8")
    return output_path


def _sorting_snapshot() -> dict[str, object]:
    return {
        "schema": "edgp.graph.snapshot.v1",
        "ecosystem": "generic",
        "root": "sorting-smoke==1.0.0",
        "stats": {"nodes": 3, "edges": 2},
        "nodes": [
            {
                "id": "zeta==1.0.0",
                "name": "zeta",
                "version": "1.0.0",
                "dependencies": ["middle==1.0.0"],
                "dependents": [],
                "metadata": {"tier": "leaf"},
            },
            {
                "id": "alpha==1.0.0",
                "name": "alpha",
                "version": "1.0.0",
                "dependencies": ["zeta==1.0.0"],
                "dependents": ["middle==1.0.0"],
                "metadata": {"tier": "root"},
            },
            {
                "id": "middle==1.0.0",
                "name": "middle",
                "version": "1.0.0",
                "dependencies": [],
                "dependents": ["zeta==1.0.0"],
                "metadata": {"tier": "bridge"},
            },
        ],
        "edges": [
            {
                "source": "zeta==1.0.0",
                "target": "middle==1.0.0",
                "relationshipType": 1,
            },
            {
                "source": "alpha==1.0.0",
                "target": "zeta==1.0.0",
                "relationshipType": 1,
            },
        ],
        "rankings": {"mostDependedUpon": []},
    }


def _browser_smoke_script() -> str:
    return r"""
(() => {
  const result = document.querySelector('[data-testid="browser-smoke-result"]');
  const status = document.querySelector('[data-testid="browser-smoke-status"]');
  const readCells = (selector, index) => Array.from(document.querySelectorAll(selector))
    .map((row) => (row.cells[index]?.textContent || '').trim());
  const click = (selector) => {
    const element = document.querySelector(selector);
    if (!element) throw new Error(`Missing ${selector}`);
    element.click();
  };
  const expect = (label, actual, expected) => {
    const actualText = actual.join('|');
    const expectedText = expected.join('|');
    if (actualText !== expectedText) {
      throw new Error(`${label}: expected ${expectedText}, got ${actualText}`);
    }
  };
  try {
    expect(
      'initial edge target order',
      readCells('[data-edge-row]', 1),
      ['middle==1.0.0', 'zeta==1.0.0'],
    );
    click('[data-testid="edge-filter-panel"] [data-sort-index="1"]');
    expect(
      'edge target ascending',
      readCells('[data-edge-row]', 1),
      ['middle==1.0.0', 'zeta==1.0.0'],
    );
    click('[data-testid="edge-filter-panel"] [data-sort-index="1"]');
    expect(
      'edge target descending',
      readCells('[data-edge-row]', 1),
      ['zeta==1.0.0', 'middle==1.0.0'],
    );
    click('[data-testid="node-table-panel"] [data-sort-index="0"]');
    expect(
      'node package ascending',
      readCells('[data-testid="node-table-panel"] tbody tr', 0),
      ['alpha==1.0.0', 'middle==1.0.0', 'zeta==1.0.0'],
    );
    const payload = { ok: true, checks: 4 };
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
    output_path = write_sorting_smoke_page(args.output)
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
