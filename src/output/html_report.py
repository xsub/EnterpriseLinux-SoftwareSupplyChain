"""Static HTML report exporter for EDGP JSON analysis documents."""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path
from typing import Any


def write_report_file(input_path: Path, output_path: Path) -> Path:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.write_text(render_report(payload), encoding="utf-8")
    return output_path


def write_snapshot_report_file(snapshot_path: Path, output_path: Path) -> Path:
    return write_report_file(snapshot_path, output_path)


def render_report(payload: dict[str, Any]) -> str:
    schema = payload.get("schema")
    if schema == "edgp.graph.snapshot.v1":
        return render_snapshot_report(payload)
    if schema == "edgp.impact.report.v1":
        return render_impact_report(payload)
    if schema == "edgp.advisory.report.v1":
        return render_advisory_report(payload)
    if schema == "edgp.npm.diagnostics.v1":
        return render_npm_diagnostics_report(payload)
    raise ValueError(f"Unsupported HTML report schema: {schema}")


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


def render_impact_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.impact.report.v1":
        raise ValueError("HTML impact report input must be an EDGP impact report")

    summary = report.get("summary", {})
    title = f"EDGP Impact Report - {report.get('node') or 'package'}"
    return _document(
        title,
        [
            _generic_hero(
                eyebrow=str(report.get("ecosystem", "generic")),
                heading=str(report.get("node") or "Dependency impact"),
                schema=str(report.get("schema")),
                metrics=[
                    ("Direct Dependents", summary.get("directDependents", 0)),
                    ("Affected Dependents", summary.get("affectedDependents", 0)),
                    ("Rendered Chains", summary.get("renderedChains", 0)),
                ],
            ),
            _package_list_panel(
                "Direct Dependents",
                report.get("directDependents", []),
                test_id="direct-dependents-panel",
            ),
            _impact_chains_panel(report.get("dependencyChainsToNode", [])),
        ],
    )


def render_advisory_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.advisory.report.v1":
        raise ValueError("HTML advisory report input must be an EDGP advisory report")

    summary = report.get("summary", {})
    title = f"EDGP Advisory Report - {report.get('root') or 'graph'}"
    return _document(
        title,
        [
            _generic_hero(
                eyebrow=str(report.get("ecosystem", "generic")),
                heading=str(report.get("root") or "Advisory overlay"),
                schema=str(report.get("schema")),
                metrics=[
                    ("Advisories", summary.get("advisories", 0)),
                    ("Findings", summary.get("findings", 0)),
                    ("Affected", summary.get("affectedDependents", 0)),
                ],
            ),
            _advisory_findings_panel(report.get("findings", [])),
        ],
    )


def render_npm_diagnostics_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.npm.diagnostics.v1":
        raise ValueError("HTML npm diagnostics input must be an EDGP npm report")

    summary = report.get("summary", {})
    title = f"EDGP npm Diagnostics - {report.get('root') or 'package-lock'}"
    return _document(
        title,
        [
            _generic_hero(
                eyebrow=str(report.get("ecosystem", "npm")),
                heading=str(report.get("root") or "npm diagnostics"),
                schema=str(report.get("schema")),
                metrics=[
                    ("Packages", summary.get("packages", 0)),
                    ("Nested Conflicts", summary.get("nestedResolutionConflicts", 0)),
                    ("Unresolved", summary.get("unresolvedDependencies", 0)),
                ],
            ),
            _npm_conflicts_panel(report.get("nestedResolutionConflicts", [])),
            _npm_duplicates_panel(report.get("duplicatePackageNames", [])),
            _npm_unresolved_panel(report.get("unresolvedDependencies", [])),
        ],
    )


def _document(title: str, sections: list[str]) -> str:
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
            *sections,
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


def _generic_hero(
    *,
    eyebrow: str,
    heading: str,
    schema: str,
    metrics: list[tuple[str, object]],
) -> str:
    metric_markup = "\n".join(
        "<div>"
        f"<dt>{escape(label)}</dt>"
        f"<dd>{escape(str(value))}</dd>"
        "</div>"
        for label, value in [*metrics, ("Schema", schema)]
    )
    return f"""
<section class="hero" data-testid="report-hero">
  <div>
    <p class="eyebrow">{escape(eyebrow)}</p>
    <h1>{escape(heading)}</h1>
  </div>
  <dl class="metrics">{metric_markup}</dl>
</section>""".strip()


def _package_list_panel(title: str, packages: object, *, test_id: str) -> str:
    if isinstance(packages, list):
        rows = "".join(f"<li>{escape(str(package))}</li>" for package in packages)
    else:
        rows = ""
    body = f'<ul class="plain-list">{rows}</ul>' if rows else '<p class="empty">No packages.</p>'
    return f"""
<section class="panel" data-testid="{escape(test_id)}">
  <div class="section-head">
    <h2>{escape(title)}</h2>
    <span>{len(packages) if isinstance(packages, list) else 0} total</span>
  </div>
  {body}
</section>""".strip()


def _impact_chains_panel(chains: object) -> str:
    rows = []
    if isinstance(chains, list):
        for chain in chains:
            if not isinstance(chain, dict):
                continue
            path = chain.get("path", [])
            if isinstance(path, list):
                rendered_path = " -> ".join(str(item) for item in path)
            else:
                rendered_path = ""
            rows.append(
                "<tr>"
                f"<td>{escape(str(chain.get('package', '')))}</td>"
                f"<td>{escape(str(chain.get('distance', '')))}</td>"
                f"<td>{escape(rendered_path)}</td>"
                "</tr>"
            )
    body = "".join(rows) or '<tr><td colspan="3">No dependency chains.</td></tr>'
    return f"""
<section class="panel" data-testid="impact-chains-panel">
  <div class="section-head">
    <h2>Dependency Chains To Node</h2>
    <span>{len(rows)} shown</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Package</th><th>Distance</th><th>Path</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </div>
</section>""".strip()


def _advisory_findings_panel(findings: object) -> str:
    rows = []
    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            advisory = finding.get("advisory", {})
            if not isinstance(advisory, dict):
                advisory = {}
            impact = finding.get("impact", {})
            impact_summary = impact.get("summary", {}) if isinstance(impact, dict) else {}
            rows.append(
                "<tr>"
                f"<td>{escape(str(advisory.get('id', '')))}</td>"
                f"<td>{escape(str(advisory.get('severity', '')))}</td>"
                f"<td>{escape(str(finding.get('package', '')))}</td>"
                f"<td>{escape(str(impact_summary.get('affectedDependents', 0)))}</td>"
                f"<td>{escape(str(advisory.get('summary', '')))}</td>"
                "</tr>"
            )
    body = "".join(rows) or '<tr><td colspan="5">No advisory findings.</td></tr>'
    return f"""
<section class="panel" data-testid="advisory-findings-panel">
  <div class="section-head">
    <h2>Advisory Findings</h2>
    <span>{len(rows)} findings</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>Advisory</th><th>Severity</th><th>Package</th><th>Affected</th><th>Summary</th></tr>
      </thead>
      <tbody>{body}</tbody>
    </table>
  </div>
</section>""".strip()


def _npm_conflicts_panel(conflicts: object) -> str:
    rows = []
    if isinstance(conflicts, list):
        for conflict in conflicts:
            if not isinstance(conflict, dict):
                continue
            versions = conflict.get("versions", [])
            version_text = (
                ", ".join(str(version) for version in versions)
                if isinstance(versions, list)
                else ""
            )
            consumers = conflict.get("consumers", [])
            if isinstance(consumers, list):
                consumer_text = "; ".join(
                    f"{consumer.get('source', '')} -> {consumer.get('resolved', '')}"
                    for consumer in consumers
                    if isinstance(consumer, dict)
                )
            else:
                consumer_text = ""
            rows.append(
                "<tr>"
                f"<td>{escape(str(conflict.get('dependency', '')))}</td>"
                f"<td>{escape(version_text)}</td>"
                f"<td>{escape(consumer_text)}</td>"
                "</tr>"
            )
    body = "".join(rows) or '<tr><td colspan="3">No nested resolution conflicts.</td></tr>'
    return f"""
<section class="panel" data-testid="npm-conflicts-panel">
  <div class="section-head">
    <h2>Nested Resolution Conflicts</h2>
    <span>{len(rows)} conflicts</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Dependency</th><th>Versions</th><th>Consumers</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </div>
</section>""".strip()


def _npm_duplicates_panel(duplicates: object) -> str:
    rows = []
    if isinstance(duplicates, list):
        for duplicate in duplicates:
            if not isinstance(duplicate, dict):
                continue
            versions = duplicate.get("versions", [])
            version_text = []
            if isinstance(versions, list):
                for version in versions:
                    if not isinstance(version, dict):
                        continue
                    paths = version.get("paths", [])
                    path_text = (
                        ", ".join(str(path) for path in paths)
                        if isinstance(paths, list)
                        else ""
                    )
                    version_text.append(f"{version.get('version', '')}: {path_text}")
            rows.append(
                "<tr>"
                f"<td>{escape(str(duplicate.get('package', '')))}</td>"
                f"<td>{escape('; '.join(version_text))}</td>"
                "</tr>"
            )
    body = "".join(rows) or '<tr><td colspan="2">No duplicate package names.</td></tr>'
    return f"""
<section class="panel" data-testid="npm-duplicates-panel">
  <div class="section-head">
    <h2>Duplicate Package Names</h2>
    <span>{len(rows)} packages</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead><tr><th>Package</th><th>Versions And Paths</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
  </div>
</section>""".strip()


def _npm_unresolved_panel(unresolved: object) -> str:
    rows = []
    if isinstance(unresolved, list):
        for item in unresolved:
            if not isinstance(item, dict):
                continue
            searched_paths = item.get("searchedPaths", [])
            searched_text = (
                ", ".join(str(path) for path in searched_paths)
                if isinstance(searched_paths, list)
                else ""
            )
            rows.append(
                "<tr>"
                f"<td>{escape(str(item.get('source', '')))}</td>"
                f"<td>{escape(str(item.get('dependency', '')))}</td>"
                f"<td>{escape(str(item.get('requested', '')))}</td>"
                f"<td>{escape(searched_text)}</td>"
                "</tr>"
            )
    body = "".join(rows) or '<tr><td colspan="4">No unresolved dependencies.</td></tr>'
    return f"""
<section class="panel" data-testid="npm-unresolved-panel">
  <div class="section-head">
    <h2>Unresolved Dependencies</h2>
    <span>{len(rows)} declarations</span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr><th>Source</th><th>Dependency</th><th>Requested</th><th>Searched Paths</th></tr>
      </thead>
      <tbody>{body}</tbody>
    </table>
  </div>
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
.plain-list {
  display: grid;
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.plain-list li {
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  overflow-wrap: anywhere;
}
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
