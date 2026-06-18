"""Generate a self-checking browser smoke bundle for report index navigation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.output.report_bundle import write_report_bundle

SMOKE_OUTPUT_DIR = Path("/tmp/edgp-report-bundle-navigation-smoke")
SMOKE_INPUTS = (
    REPO_ROOT / "tests" / "fixtures" / "snapshot-right.json",
    REPO_ROOT / "tests" / "fixtures" / "npm-diagnostics-report.json",
    REPO_ROOT / "tests" / "fixtures" / "impact-report.json",
)


def write_bundle_navigation_smoke(output_dir: Path = SMOKE_OUTPUT_DIR) -> Path:
    index_path = write_report_bundle(
        SMOKE_INPUTS,
        output_dir,
        bundle_metadata={
            "sourceKind": "edgp-json",
            "command": "scripts/browser_smoke_report_bundle_navigation.py",
        },
    )
    html = index_path.read_text(encoding="utf-8")
    html = html.replace("</style>", f"{_browser_smoke_styles()}</style>")
    html = html.replace("</main>", f"{_browser_smoke_panel()}\n</main>")
    html = html.replace("</body>", f"<script>{_browser_smoke_script()}</script>\n</body>")
    index_path.write_text(html, encoding="utf-8")
    return index_path


def _browser_smoke_panel() -> str:
    return """
<section class="browser-smoke" data-testid="browser-smoke-panel">
  <div class="browser-smoke-header">
    <h2>Browser Smoke</h2>
    <span data-testid="browser-smoke-status">pending</span>
  </div>
  <pre data-testid="browser-smoke-result">pending</pre>
  <iframe
    data-testid="browser-smoke-frame"
    title="Report bundle navigation smoke frame"
  ></iframe>
</section>""".strip()


def _browser_smoke_styles() -> str:
    return """
.browser-smoke {
  margin-top: 18px;
  padding: 18px;
  background: #ffffff;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.browser-smoke-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.browser-smoke h2 {
  margin: 0;
  font-size: 18px;
}
.browser-smoke span {
  color: var(--green);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
.browser-smoke pre {
  margin: 12px 0 0;
  overflow: auto;
  padding: 12px;
  background: #f5f7f4;
  border: 1px solid var(--line);
  border-radius: 8px;
  white-space: pre-wrap;
}
.browser-smoke iframe {
  width: 100%;
  min-height: 260px;
  margin-top: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
}
""".strip()


def _browser_smoke_script() -> str:
    return r"""
(() => {
  const result = document.querySelector('[data-testid="browser-smoke-result"]');
  const status = document.querySelector('[data-testid="browser-smoke-status"]');
  const frame = document.querySelector('[data-testid="browser-smoke-frame"]');
  const params = new URLSearchParams(window.location.search);
  if (params.get('smokeBundleReady') !== '1') {
    params.set('smokeBundleReady', '1');
    params.set('bundleQuery', 'conflict');
    params.set('bundleSchema', 'edgp.npm.diagnostics.v1');
    window.location.search = params.toString();
    return;
  }
  const expectedHrefs = [
    '001-snapshot-right.html',
    '002-npm-diagnostics-report.html',
    '003-impact-report.html',
  ];
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
  const readBundleParams = () => {
    const current = new URLSearchParams(window.location.search);
    return {
      query: current.get('bundleQuery') || '',
      schema: current.get('bundleSchema') || '',
    };
  };
  const applySearch = (search, value) => {
    search.value = value;
    search.dispatchEvent(new Event('input', { bubbles: true }));
  };
  const assertFilters = () => {
    const panel = document.querySelector('[data-report-bundle-filter-panel]');
    const search = panel?.querySelector('[data-report-bundle-search]');
    const schema = panel?.querySelector('[data-report-bundle-schema]');
    const reset = panel?.querySelector('[data-report-bundle-reset]');
    const count = panel?.querySelector('[data-report-bundle-filter-count]');
    const cards = () => Array.from(document.querySelectorAll('[data-report-bundle-card]'));
    const visibleCards = () => cards().filter((card) => !card.hidden);
    if (!panel || !search || !schema || !reset || !count) {
      throw new Error('Missing report bundle filter controls');
    }
    expect('initial filter query', search.value, 'conflict');
    expect('initial filter schema', schema.value, 'edgp.npm.diagnostics.v1');
    expect('initial filtered count', count.textContent, '1 of 3 reports');
    expect('initial visible cards', visibleCards().length, 1);
    expectList(
      'initial visible card schema',
      visibleCards().map((card) => card.dataset.reportSchema),
      ['edgp.npm.diagnostics.v1'],
    );
    expect('initial URL query', readBundleParams().query, 'conflict');
    expect('initial URL schema', readBundleParams().schema, 'edgp.npm.diagnostics.v1');
    applySearch(search, 'snapshot');
    expect('updated filter query', search.value, 'snapshot');
    expect('updated URL query', readBundleParams().query, 'snapshot');
    expect('updated filtered count', count.textContent, '0 of 3 reports');
    reset.click();
    expect('reset filter query', search.value, '');
    expect('reset filter schema', schema.value, '');
    expect('reset filtered count', count.textContent, '3 of 3 reports');
    expect('reset visible cards', visibleCards().length, 3);
    expect('reset URL query', readBundleParams().query, '');
    expect('reset URL schema', readBundleParams().schema, '');
  };
  const loadFrame = (href) => new Promise((resolve, reject) => {
    frame.onload = () => {
      try {
        const doc = frame.contentDocument;
        if (!doc) throw new Error(`No contentDocument for ${href}`);
        if (!doc.querySelector('[data-testid="report-hero"]')) {
          throw new Error(`Missing report hero for ${href}`);
        }
        if (!doc.title.startsWith('EDGP ')) {
          throw new Error(`Unexpected title for ${href}: ${doc.title}`);
        }
        resolve({ href, title: doc.title });
      } catch (error) {
        reject(error);
      }
    };
    frame.onerror = () => reject(new Error(`Failed to load ${href}`));
    frame.src = href;
  });
  const run = async () => {
    try {
      assertFilters();
      const cards = Array.from(
        document.querySelectorAll('[data-testid="report-bundle-entry"]'),
      );
      const links = cards.map((card) => card.querySelector('a[href]'));
      expect('bundle card count', cards.length, 3);
      expect('bundle link count', links.filter(Boolean).length, 3);
      expectList(
        'bundle link order',
        links.map((link) => link.getAttribute('href')),
        expectedHrefs,
      );
      const verification = document.querySelector(
        '[data-testid="report-bundle-verification"]',
      );
      if (!verification || !verification.textContent.includes('3')) {
        throw new Error('Missing bundle verification report count');
      }
      const loaded = [];
      for (const href of expectedHrefs) {
        loaded.push(await loadFrame(href));
      }
      const payload = {
        ok: true,
        checks: 18 + loaded.length,
        hrefs: expectedHrefs,
        titles: loaded.map((entry) => entry.title),
      };
      document.documentElement.dataset.browserSmokeStatus = 'pass';
      status.textContent = 'PASS';
      result.textContent = JSON.stringify(payload, null, 2);
    } catch (error) {
      const payload = { ok: false, message: String(error && error.message || error) };
      document.documentElement.dataset.browserSmokeStatus = 'fail';
      status.textContent = 'FAIL';
      result.textContent = JSON.stringify(payload, null, 2);
    }
  };
  run();
})();
""".strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=SMOKE_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    index_path = write_bundle_navigation_smoke(args.output_dir)
    print(index_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
