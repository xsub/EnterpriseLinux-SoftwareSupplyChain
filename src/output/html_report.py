"""Static HTML report exporter for EDGP JSON graph snapshots."""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path
from typing import Any


def write_snapshot_report_file(snapshot_path: Path, output_path: Path) -> Path:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    output_path.write_text(render_snapshot_report(payload), encoding="utf-8")
    return output_path


def render_snapshot_report(snapshot: dict[str, Any]) -> str:
    if snapshot.get("schema") != "edgp.graph.snapshot.v1":
        raise ValueError("HTML report input must be an EDGP graph snapshot")

    nodes = _nodes(snapshot)
    edges = _edges(snapshot)
    stats = snapshot.get("stats", {})
    rankings = snapshot.get("rankings", {}).get("mostDependedUpon", [])
    title = f"EDGP Snapshot Report - {snapshot.get('root') or 'graph'}"

    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{escape(title)}</title>",
            f"<style>{_styles()}</style>",
            "</head>",
            "<body>",
            '<main class="report-shell">',
            _hero(snapshot, stats),
            _graph_panel(nodes, edges),
            _ranking_panel(rankings),
            _node_table(nodes),
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _hero(snapshot: dict[str, Any], stats: dict[str, Any]) -> str:
    return f"""
<section class="hero" data-testid="report-hero">
  <div>
    <p class="eyebrow">{escape(str(snapshot.get("ecosystem", "generic")))}</p>
    <h1>{escape(str(snapshot.get("root") or "Dependency graph"))}</h1>
  </div>
  <dl class="metrics">
    <div><dt>Nodes</dt><dd>{escape(str(stats.get("nodes", 0)))}</dd></div>
    <div><dt>Edges</dt><dd>{escape(str(stats.get("edges", 0)))}</dd></div>
    <div><dt>Schema</dt><dd>{escape(str(snapshot.get("schema")))}</dd></div>
  </dl>
</section>""".strip()


def _graph_panel(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    return f"""
<section class="panel" data-testid="graph-panel">
  <div class="section-head">
    <h2>Graph Preview</h2>
    <span>{len(nodes)} nodes / {len(edges)} edges</span>
  </div>
  {_svg_preview(nodes, edges)}
</section>""".strip()


def _ranking_panel(rankings: list[dict[str, Any]]) -> str:
    rows = []
    max_count = max((int(item.get("dependents", 0)) for item in rankings), default=1)
    for item in rankings[:10]:
        count = int(item.get("dependents", 0))
        width = max(8, round((count / max_count) * 100))
        rows.append(
            "<li>"
            f"<span>{escape(str(item.get('package', '')))}</span>"
            f"<b>{count}</b>"
            f'<i style="width:{width}%"></i>'
            "</li>"
        )
    body = "\n".join(rows) or '<p class="empty">No dependent rankings in snapshot.</p>'
    return f"""
<section class="panel" data-testid="ranking-panel">
  <div class="section-head">
    <h2>Most Depended Upon</h2>
    <span>Top 10</span>
  </div>
  <ol class="ranking">{body}</ol>
</section>""".strip()


def _node_table(nodes: list[dict[str, Any]]) -> str:
    rows = []
    for node in nodes:
        metadata = node.get("metadata", {})
        metadata_text = ", ".join(
            f"{key}={value}" for key, value in sorted(metadata.items())
        )
        rows.append(
            "<tr>"
            f"<td>{escape(str(node.get('id', '')))}</td>"
            f"<td>{len(node.get('dependencies', []))}</td>"
            f"<td>{len(node.get('dependents', []))}</td>"
            f"<td>{escape(metadata_text)}</td>"
            "</tr>"
        )
    return f"""
<section class="panel" data-testid="node-table-panel">
  <div class="section-head">
    <h2>Nodes</h2>
    <span>{len(nodes)} total</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>Package</th><th>Deps</th><th>Dependents</th><th>Metadata</th></tr>
      </thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>
</section>""".strip()


def _svg_preview(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    visible_nodes = nodes[:32]
    visible_ids = [str(node.get("id", "")) for node in visible_nodes]
    positions = _node_positions(visible_ids)
    edge_markup = []
    for edge in edges[:64]:
        source = str(edge.get("source", ""))
        target = str(edge.get("target", ""))
        if source not in positions or target not in positions:
            continue
        x1, y1 = positions[source]
        x2, y2 = positions[target]
        edge_markup.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="edge" />'
        )

    node_markup = []
    for node_id in visible_ids:
        x, y = positions[node_id]
        label = node_id if len(node_id) <= 22 else f"{node_id[:19]}..."
        node_markup.append(
            f'<g><circle cx="{x}" cy="{y}" r="12" />'
            f'<text x="{x}" y="{y + 27}">{escape(label)}</text></g>'
        )

    return f"""
<svg viewBox="0 0 720 360" role="img" aria-label="Dependency graph preview">
  <rect x="1" y="1" width="718" height="358" rx="8" class="svg-bg" />
  {"".join(edge_markup)}
  {"".join(node_markup)}
</svg>""".strip()


def _node_positions(node_ids: list[str]) -> dict[str, tuple[int, int]]:
    if not node_ids:
        return {}
    center_x = 360
    center_y = 180
    radius = 116 if len(node_ids) > 2 else 76
    positions = {}
    for index, node_id in enumerate(node_ids):
        angle = (2 * math.pi * index / len(node_ids)) - (math.pi / 2)
        positions[node_id] = (
            round(center_x + radius * math.cos(angle)),
            round(center_y + radius * math.sin(angle)),
        )
    return positions


def _nodes(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = snapshot.get("nodes", [])
    if not isinstance(nodes, list):
        raise ValueError("Snapshot nodes must be a list")
    return [node for node in nodes if isinstance(node, dict)]


def _edges(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    edges = snapshot.get("edges", [])
    if not isinstance(edges, list):
        raise ValueError("Snapshot edges must be a list")
    return [edge for edge in edges if isinstance(edge, dict)]


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
  --amber: #a2671a;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--wash);
  color: var(--ink);
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.report-shell {
  width: min(1120px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 28px 0 40px;
}
.hero, .panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 24px;
  align-items: end;
  padding: 28px;
  border-top: 5px solid var(--green);
}
.eyebrow {
  margin: 0 0 8px;
  color: var(--green);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}
h1, h2 { margin: 0; letter-spacing: 0; }
h1 { font-size: 30px; line-height: 1.15; overflow-wrap: anywhere; }
h2 { font-size: 18px; }
.metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(96px, 1fr));
  gap: 12px;
  margin: 0;
}
.metrics div {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
dt { color: var(--muted); font-size: 12px; }
dd { margin: 2px 0 0; font-size: 20px; font-weight: 700; overflow-wrap: anywhere; }
.panel { margin-top: 18px; padding: 18px; }
.section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 14px;
}
.section-head span { color: var(--muted); font-size: 13px; }
svg { width: 100%; height: auto; display: block; }
.svg-bg { fill: #f8faf9; stroke: var(--line); }
.edge { stroke: var(--blue); stroke-width: 2; opacity: .55; }
circle { fill: var(--green); stroke: #ffffff; stroke-width: 3; }
text {
  fill: var(--ink);
  font-size: 12px;
  text-anchor: middle;
  paint-order: stroke;
  stroke: #ffffff;
  stroke-width: 3px;
}
.ranking {
  list-style: none;
  display: grid;
  gap: 10px;
  margin: 0;
  padding: 0;
}
.ranking li {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  padding: 11px 12px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.ranking span, .ranking b { position: relative; z-index: 1; overflow-wrap: anywhere; }
.ranking i {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 3px;
  background: var(--amber);
}
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; }
table { width: 100%; border-collapse: collapse; min-width: 720px; }
th, td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}
th { color: var(--muted); font-size: 12px; text-transform: uppercase; }
td { overflow-wrap: anywhere; }
tr:last-child td { border-bottom: 0; }
.empty { color: var(--muted); margin: 0; }
@media (max-width: 760px) {
  .report-shell { width: min(100vw - 20px, 1120px); padding-top: 10px; }
  .hero { grid-template-columns: 1fr; padding: 18px; }
  .metrics { grid-template-columns: 1fr; }
  h1 { font-size: 24px; }
}
""".strip()
