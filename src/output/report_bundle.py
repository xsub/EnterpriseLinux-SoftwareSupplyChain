"""Deterministic static HTML bundles for EDGP JSON reports."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Sequence

from src.output.html_report import render_report


@dataclass(frozen=True)
class BundleEntry:
    source_path: Path
    output_path: Path
    schema: str
    title: str
    summary: dict[str, Any]


def write_report_bundle(
    input_paths: Sequence[Path],
    output_dir: Path,
    *,
    index_name: str = "index.html",
) -> Path:
    if not input_paths:
        raise ValueError("At least one --input is required for a report bundle")

    output_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    for index, input_path in enumerate(input_paths, start=1):
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        html = render_report(payload)
        output_path = output_dir / f"{index:03d}-{_safe_stem(input_path)}.html"
        output_path.write_text(html, encoding="utf-8")
        entries.append(
            BundleEntry(
                source_path=input_path,
                output_path=output_path,
                schema=str(payload.get("schema", "")),
                title=_report_title(payload),
                summary=_report_summary(payload),
            )
        )

    index_path = output_dir / index_name
    index_path.write_text(render_bundle_index(entries), encoding="utf-8")
    return index_path


def render_bundle_index(entries: Sequence[BundleEntry]) -> str:
    cards = "\n".join(_entry_card(entry) for entry in entries)
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>EDGP Report Bundle</title>",
            f"<style>{_styles()}</style>",
            "</head>",
            "<body>",
            '<main class="bundle-shell">',
            '<section class="hero" data-testid="report-bundle-index">',
            "<div>",
            '<p class="eyebrow">EDGP</p>',
            "<h1>Report Bundle</h1>",
            "</div>",
            f"<p>{len(entries)} reports rendered for local dependency triage.</p>",
            "</section>",
            '<section class="reports">',
            cards,
            "</section>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip(".-_")
    return stem or "report"


def _report_title(payload: dict[str, Any]) -> str:
    schema = payload.get("schema")
    if schema == "edgp.graph.snapshot.v1":
        return f"Graph Snapshot - {payload.get('root') or 'graph'}"
    if schema == "edgp.impact.report.v1":
        return f"Impact Report - {payload.get('node') or 'package'}"
    if schema == "edgp.advisory.report.v1":
        return f"Advisory Report - {payload.get('root') or 'graph'}"
    if schema == "edgp.npm.diagnostics.v1":
        return f"npm Diagnostics - {payload.get('root') or 'package-lock'}"
    return str(schema or "EDGP Report")


def _report_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return summary
    stats = payload.get("stats")
    if isinstance(stats, dict):
        return stats
    return {}


def _entry_card(entry: BundleEntry) -> str:
    metrics = "".join(
        "<li>"
        f"<span>{escape(_humanize_key(key))}</span>"
        f"<strong>{escape(str(value))}</strong>"
        "</li>"
        for key, value in sorted(entry.summary.items())
    )
    metrics = metrics or "<li><span>Summary</span><strong>n/a</strong></li>"
    href = escape(entry.output_path.name)
    return f"""
<article class="report-card" data-testid="report-bundle-entry">
  <div>
    <p class="schema">{escape(entry.schema)}</p>
    <h2><a href="{href}">{escape(entry.title)}</a></h2>
    <p class="source">{escape(str(entry.source_path))}</p>
  </div>
  <ul>{metrics}</ul>
</article>""".strip()


def _humanize_key(key: str) -> str:
    words = re.sub(r"(?<!^)([A-Z])", r" \1", key).replace("_", " ")
    return words.title()


def _styles() -> str:
    return """
:root {
  color-scheme: light;
  --ink: #172026;
  --muted: #5f6f7a;
  --line: #d8e1e5;
  --panel: #ffffff;
  --wash: #f5f7f4;
  --green: #2e7d5b;
  --blue: #2f6f9f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--wash);
  color: var(--ink);
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.bundle-shell {
  width: min(1120px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 28px 0 40px;
}
.hero, .report-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: end;
  padding: 28px;
  border-top: 5px solid var(--green);
}
.eyebrow, .schema {
  margin: 0 0 8px;
  color: var(--green);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}
h1, h2, p { margin-top: 0; letter-spacing: 0; }
h1 { margin-bottom: 0; font-size: 30px; line-height: 1.15; overflow-wrap: anywhere; }
h2 { margin-bottom: 8px; font-size: 18px; line-height: 1.25; overflow-wrap: anywhere; }
a { color: var(--blue); text-decoration-thickness: 2px; text-underline-offset: 3px; }
.reports { display: grid; gap: 14px; margin-top: 18px; }
.report-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, auto);
  gap: 20px;
  padding: 18px;
}
.source { color: var(--muted); margin-bottom: 0; overflow-wrap: anywhere; }
ul {
  display: grid;
  grid-template-columns: repeat(2, minmax(96px, 1fr));
  gap: 10px;
  list-style: none;
  margin: 0;
  padding: 0;
}
li {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
li span { display: block; color: var(--muted); font-size: 12px; }
li strong { display: block; margin-top: 2px; font-size: 18px; overflow-wrap: anywhere; }
@media (max-width: 760px) {
  .bundle-shell { width: min(100vw - 20px, 1120px); padding-top: 10px; }
  .hero, .report-card { grid-template-columns: 1fr; display: grid; }
  ul { grid-template-columns: 1fr; }
}
""".strip()
