"""Static HTML report exporter for EDGP JSON analysis documents."""

from __future__ import annotations

import json
import math
from html import escape
from pathlib import Path
from typing import Any

EDGE_EXPLORER_PAGE_SIZE = 250


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
    if schema == "edgp.graph.diff.v1":
        return render_graph_diff_report(payload)
    if schema == "edgp.impact.report.v1":
        return render_impact_report(payload)
    if schema == "edgp.advisory.report.v1":
        return render_advisory_report(payload)
    if schema == "edgp.npm.diagnostics.v1":
        return render_npm_diagnostics_report(payload)
    if schema == "edgp.albs.artifact_inventory.v1":
        return render_albs_artifact_inventory_report(payload)
    if schema == "edgp.albs.build_timing.v1":
        return render_albs_build_timing_report(payload)
    if schema == "edgp.albs.build_diff.v1":
        return render_albs_build_diff_report(payload)
    if schema == "edgp.rpm.albs_provenance.v1":
        return render_rpm_albs_provenance_report(payload)
    if schema == "edgp.rpm.repository_summary.v1":
        return render_rpm_repository_summary_report(payload)
    if schema == "edgp.rpm.repository_diff.v1":
        return render_rpm_repository_diff_report(payload)
    if schema == "edgp.albs.log_intelligence.v1":
        return render_albs_log_intelligence_report(payload)
    if schema == "edgp.albs.release_completeness.v1":
        return render_albs_release_completeness_report(payload)
    if schema == "edgp.libsolv.bridge.v1":
        return render_libsolv_bridge_report(payload)
    if schema == "edgp.public.advisory_feed.v1":
        return render_public_advisory_feed_report(payload)
    if schema == "edgp.performance.report.v1":
        return render_performance_report(payload)
    if schema == "edgp.query.report.v1":
        return render_query_report(payload)
    if schema == "edgp.license.report.v1":
        return render_license_report(payload)
    if schema == "edgp.triage.summary.v1":
        return render_triage_summary_report(payload)
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
            _edge_explorer_panel(edges),
            _ranking_panel(rankings),
            _node_table(nodes),
            "</main>",
            f"<script>{_edge_filter_script()}</script>",
            f"<script>{_table_sort_script()}</script>",
            "</body>",
            "</html>",
        ]
    )


def render_graph_diff_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.graph.diff.v1":
        raise ValueError("HTML graph diff input must be an EDGP graph diff report")

    summary = report.get("summary", {})
    nodes = report.get("nodes", {})
    edges = report.get("edges", {})
    if not isinstance(nodes, dict):
        nodes = {}
    if not isinstance(edges, dict):
        edges = {}
    heading = f"{report.get('leftRoot') or 'left'} -> {report.get('rightRoot') or 'right'}"
    return _document(
        "EDGP Graph Diff",
        [
            _generic_hero(
                eyebrow="graph diff",
                heading=heading,
                schema=str(report.get("schema")),
                metrics=[
                    ("Added Nodes", _dict_value(summary, "addedNodes")),
                    ("Removed Nodes", _dict_value(summary, "removedNodes")),
                    ("Added Edges", _dict_value(summary, "addedEdges")),
                    ("Removed Edges", _dict_value(summary, "removedEdges")),
                    (
                        "Metadata Changed",
                        _dict_value(summary, "metadataChangedNodes"),
                    ),
                ],
            ),
            _package_list_panel(
                "Added Nodes",
                nodes.get("added", []),
                test_id="graph-diff-added-nodes-panel",
            ),
            _package_list_panel(
                "Removed Nodes",
                nodes.get("removed", []),
                test_id="graph-diff-removed-nodes-panel",
            ),
            _package_list_panel(
                "Metadata Changed Nodes",
                nodes.get("metadataChanged", []),
                test_id="graph-diff-metadata-nodes-panel",
            ),
            _rows_panel(
                "Added Edges",
                edges.get("added", []),
                ["source", "target", "relationshipType"],
                test_id="graph-diff-added-edges-panel",
            ),
            _rows_panel(
                "Removed Edges",
                edges.get("removed", []),
                ["source", "target", "relationshipType"],
                test_id="graph-diff-removed-edges-panel",
            ),
        ],
        scripts=[_table_sort_script()],
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


def render_albs_artifact_inventory_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.albs.artifact_inventory.v1":
        raise ValueError("HTML ALBS artifact inventory input must be an EDGP ALBS report")

    summary = report.get("summary", {})
    title = f"EDGP ALBS Artifact Inventory - {report.get('root') or 'build'}"
    return _document(
        title,
        [
            _generic_hero(
                eyebrow=str(report.get("ecosystem", "albs")),
                heading=str(report.get("root") or "ALBS artifact inventory"),
                schema=str(report.get("schema")),
                metrics=[
                    ("Artifacts", summary.get("artifacts", 0)),
                    ("Build Tasks", summary.get("buildTasks", 0)),
                    ("Packages", summary.get("packages", 0)),
                ],
            ),
            _albs_arch_summary_panel(report.get("byBuildArch", [])),
            _albs_artifact_table(report.get("items", [])),
        ],
        scripts=[_table_sort_script()],
    )


def render_albs_build_timing_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.albs.build_timing.v1":
        raise ValueError("HTML ALBS build timing input must be an EDGP ALBS report")

    summary = report.get("summary", {})
    title = f"EDGP ALBS Build Timing - {report.get('root') or 'build'}"
    return _document(
        title,
        [
            _generic_hero(
                eyebrow=str(report.get("ecosystem", "albs")),
                heading=str(report.get("root") or "ALBS build timing"),
                schema=str(report.get("schema")),
                metrics=[
                    ("Build Tasks", summary.get("buildTasks", 0)),
                    ("Critical Seconds", summary.get("criticalBuildTaskWallSeconds", 0)),
                    ("Artifacts", summary.get("artifacts", 0)),
                ],
            ),
            _albs_task_timing_panel(report.get("taskTimings", [])),
            _albs_sign_timing_panel(report.get("signTimings", [])),
            _albs_artifact_timing_panel(report.get("artifactTimings", [])),
        ],
        scripts=[_table_sort_script()],
    )


def render_albs_build_diff_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.albs.build_diff.v1":
        raise ValueError("HTML ALBS build diff input must be an EDGP ALBS report")

    summary = report.get("summary", {})
    left = report.get("left", {})
    right = report.get("right", {})
    title = "EDGP ALBS Build Diff"
    return _document(
        title,
        [
            _generic_hero(
                eyebrow="albs",
                heading=f"{_dict_value(left, 'buildId')} -> {_dict_value(right, 'buildId')}",
                schema=str(report.get("schema")),
                metrics=[
                    ("Added", summary.get("addedArtifacts", 0)),
                    ("Removed", summary.get("removedArtifacts", 0)),
                    ("Changed", summary.get("changedArtifacts", 0)),
                ],
            ),
            _rows_panel(
                "Changed Artifacts",
                report.get("changedArtifacts", []),
                ["packageName", "artifactArch", "buildArch", "changedFields"],
                test_id="albs-build-diff-changed-panel",
            ),
            _rows_panel(
                "Added Artifacts",
                report.get("addedArtifacts", []),
                ["filename", "packageName", "artifactArch", "buildArch"],
                test_id="albs-build-diff-added-panel",
            ),
            _rows_panel(
                "Removed Artifacts",
                report.get("removedArtifacts", []),
                ["filename", "packageName", "artifactArch", "buildArch"],
                test_id="albs-build-diff-removed-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_rpm_albs_provenance_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.rpm.albs_provenance.v1":
        raise ValueError("HTML RPM ALBS provenance input must be an EDGP report")

    summary = report.get("summary", {})
    rows = []
    for match in report.get("matches", []) if isinstance(report.get("matches"), list) else []:
        if not isinstance(match, dict):
            continue
        installed = match.get("installedPackage", {})
        artifact = match.get("albsArtifact", {})
        rows.append(
            {
                "package": _dict_value(installed, "nodeId"),
                "artifact": _dict_value(artifact, "filename"),
                "buildId": match.get("buildId", ""),
                "releaseId": match.get("releaseId", ""),
            }
        )
    return _document(
        "EDGP RPM ALBS Provenance",
        [
            _generic_hero(
                eyebrow="rpm",
                heading=str(report.get("root") or "RPM to ALBS provenance"),
                schema=str(report.get("schema")),
                metrics=[
                    ("Installed", summary.get("installedPackages", 0)),
                    ("Matched", summary.get("matchedPackages", 0)),
                    ("Unmatched", summary.get("unmatchedPackages", 0)),
                ],
            ),
            _rows_panel(
                "Matched Packages",
                rows,
                ["package", "artifact", "buildId", "releaseId"],
                test_id="rpm-albs-provenance-matches-panel",
            ),
            _rows_panel(
                "Unmatched Installed Packages",
                report.get("unmatchedInstalledPackages", []),
                ["nodeId", "name", "version", "release", "arch"],
                test_id="rpm-albs-provenance-unmatched-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_rpm_repository_summary_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.rpm.repository_summary.v1":
        raise ValueError("HTML RPM repository summary input must be an EDGP report")

    summary = report.get("summary", {})
    return _document(
        "EDGP RPM Repository Summary",
        [
            _generic_hero(
                eyebrow="rpm",
                heading=str(report.get("root") or "RPM repository"),
                schema=str(report.get("schema")),
                metrics=[
                    ("Packages", summary.get("packages", 0)),
                    ("Source RPMs", summary.get("sourceRpms", 0)),
                    ("Unresolved", summary.get("unresolvedRequirements", 0)),
                ],
            ),
            _rows_panel(
                "Architectures",
                report.get("architectures", []),
                ["arch", "packages"],
                test_id="rpm-repository-architectures-panel",
            ),
            _rows_panel(
                "Top Source RPMs",
                report.get("topSourceRpms", []),
                ["sourceRpm", "packages"],
                test_id="rpm-repository-source-rpms-panel",
            ),
            _rows_panel(
                "Unresolved Requirements",
                report.get("unresolvedRequirements", []),
                ["package", "capability"],
                test_id="rpm-repository-unresolved-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_rpm_repository_diff_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.rpm.repository_diff.v1":
        raise ValueError("HTML RPM repository diff input must be an EDGP report")

    summary = report.get("summary", {})
    left = report.get("left", {})
    right = report.get("right", {})
    heading = f"{_dict_value(left, 'root')} -> {_dict_value(right, 'root')}"
    return _document(
        "EDGP RPM Repository Diff",
        [
            _generic_hero(
                eyebrow="rpm",
                heading=heading,
                schema=str(report.get("schema")),
                metrics=[
                    ("Added", summary.get("addedPackages", 0)),
                    ("Removed", summary.get("removedPackages", 0)),
                    ("Changed", summary.get("changedPackages", 0)),
                ],
            ),
            _rows_panel(
                "Changed Packages",
                report.get("changedPackages", []),
                ["name", "arch", "changedFields"],
                test_id="rpm-repository-diff-changed-panel",
            ),
            _rows_panel(
                "Added Packages",
                report.get("addedPackages", []),
                ["name", "version", "release", "arch", "sourceRpm"],
                test_id="rpm-repository-diff-added-panel",
            ),
            _rows_panel(
                "Removed Packages",
                report.get("removedPackages", []),
                ["name", "version", "release", "arch", "sourceRpm"],
                test_id="rpm-repository-diff-removed-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_albs_log_intelligence_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.albs.log_intelligence.v1":
        raise ValueError("HTML ALBS log intelligence input must be an EDGP report")

    summary = report.get("summary", {})
    return _document(
        "EDGP ALBS Log Intelligence",
        [
            _generic_hero(
                eyebrow="albs",
                heading=str(report.get("root") or "ALBS logs"),
                schema=str(report.get("schema")),
                metrics=[
                    ("Logs", summary.get("logArtifacts", 0)),
                    ("Signals", summary.get("signals", 0)),
                    ("Signal Kinds", summary.get("signalKinds", 0)),
                ],
            ),
            _rows_panel(
                "Build Logs",
                report.get("logs", []),
                ["name", "buildArch", "contentAvailable", "signals", "sample"],
                test_id="albs-log-intelligence-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_albs_release_completeness_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.albs.release_completeness.v1":
        raise ValueError("HTML ALBS release completeness input must be an EDGP report")

    summary = report.get("summary", {})
    return _document(
        "EDGP ALBS Release Completeness",
        [
            _generic_hero(
                eyebrow="albs",
                heading="ALBS release completeness",
                schema=str(report.get("schema")),
                metrics=[
                    ("Builds", summary.get("builds", 0)),
                    ("Released", summary.get("releasedBuilds", 0)),
                    ("Missing Arches", summary.get("missingBuildArchitectures", 0)),
                ],
            ),
            _rows_panel(
                "Build Coverage",
                report.get("builds", []),
                [
                    "buildId",
                    "released",
                    "observedBuildArchitectures",
                    "missingBuildArchitectures",
                    "failedBuildTasks",
                    "rpmArtifacts",
                ],
                test_id="albs-release-completeness-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_libsolv_bridge_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.libsolv.bridge.v1":
        raise ValueError("HTML libsolv bridge input must be an EDGP report")

    summary = report.get("summary", {})
    metrics = [
        ("Commands", summary.get("commandsAvailable", 0)),
        ("Actions", summary.get("transactionActions", 0)),
        ("Installs", summary.get("installs", 0)),
    ]
    if "graphMatchedActions" in summary:
        metrics.extend(
            [
                ("Graph Matches", summary.get("graphMatchedActions", 0)),
                ("Impacted", summary.get("graphImpactedActions", 0)),
            ]
        )
    sections = [
        _generic_hero(
            eyebrow="rpm",
            heading="libsolv bridge",
            schema=str(report.get("schema")),
            metrics=metrics,
        ),
        _rows_panel(
            "libsolv Commands",
            report.get("commands", []),
            ["command", "available", "path"],
            test_id="libsolv-commands-panel",
        ),
        _rows_panel(
            "Transaction Actions",
            report.get("transactionActions", []),
            [
                "action",
                "packageName",
                "packageArch",
                "nodeId",
                "graphMatchStatus",
                "graphAffectedDependents",
                "oldNodeId",
                "newNodeId",
                "purl",
            ],
            test_id="libsolv-transaction-panel",
        ),
    ]
    if isinstance(report.get("transactionImpact"), list):
        sections.append(
            _rows_panel(
                "Transaction Graph Impact",
                report.get("transactionImpact", []),
                [
                    "actionIndex",
                    "action",
                    "packageName",
                    "matchStatus",
                    "directDependents",
                    "affectedDependents",
                    "matchedNodeIds",
                ],
                test_id="libsolv-impact-panel",
            )
        )
    return _document(
        "EDGP libsolv Bridge",
        sections,
        scripts=[_table_sort_script()],
    )


def render_public_advisory_feed_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.public.advisory_feed.v1":
        raise ValueError("HTML public advisory feed input must be an EDGP report")

    summary = report.get("summary", {})
    return _document(
        "EDGP Public Advisory Feed",
        [
            _generic_hero(
                eyebrow=str(report.get("ecosystem", "public")),
                heading="Public advisory normalization",
                schema=str(report.get("schema")),
                metrics=[
                    ("Advisories", summary.get("advisories", 0)),
                    ("Packages", summary.get("packages", 0)),
                    ("Severities", summary.get("severities", 0)),
                ],
            ),
            _rows_panel(
                "Normalized Advisories",
                report.get("advisories", []),
                ["id", "severity", "package", "versions", "ranges", "summary"],
                test_id="public-advisory-feed-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_performance_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.performance.report.v1":
        raise ValueError("HTML performance report input must be an EDGP report")

    summary = report.get("summary", {})
    return _document(
        "EDGP Performance Report",
        [
            _generic_hero(
                eyebrow="generic",
                heading="CSR performance",
                schema=str(report.get("schema")),
                metrics=[
                    ("Scenarios", summary.get("scenarios", 0)),
                    ("Max Nodes", summary.get("maxNodes", 0)),
                    ("Layout", summary.get("layout", "")),
                ],
            ),
            _rows_panel(
                "Benchmark Results",
                report.get("results", []),
                ["nodes", "fanout", "edges", "buildMs", "reachableMs", "mostDependedUponMs", "storage"],
                test_id="performance-results-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_query_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.query.report.v1":
        raise ValueError("HTML query report input must be an EDGP report")

    summary = report.get("summary", {})
    operation = str(report.get("operation", "query"))
    context = [
        {
            "source": report.get("source", ""),
            "ecosystem": report.get("ecosystem", ""),
            "root": report.get("root", ""),
            "operation": operation,
            "direction": report.get("direction", ""),
            "node": report.get("node", ""),
            "target": report.get("target", ""),
        }
    ]
    result = report.get("result", [])
    if operation == "most-depended-upon":
        result_panel = _rows_panel(
            "Most Depended Upon",
            result,
            ["package", "dependents"],
            test_id="query-ranking-panel",
        )
    else:
        result_panel = _package_list_panel(
            "Query Result",
            result,
            test_id="query-result-panel",
        )
    return _document(
        "EDGP Query Report",
        [
            _generic_hero(
                eyebrow=str(report.get("source", "graph")),
                heading=operation,
                schema=str(report.get("schema")),
                metrics=[
                    ("Results", summary.get("resultCount", 0)),
                    ("Kind", summary.get("resultKind", "")),
                    ("Limit", report.get("limit", "")),
                ],
            ),
            _rows_panel(
                "Query Context",
                context,
                ["source", "ecosystem", "root", "operation", "direction", "node", "target"],
                test_id="query-context-panel",
            ),
            result_panel,
        ],
        scripts=[_table_sort_script()],
    )


def render_license_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.license.report.v1":
        raise ValueError("HTML license report input must be an EDGP report")

    summary = report.get("summary", {})
    return _document(
        "EDGP License Report",
        [
            _generic_hero(
                eyebrow=str(report.get("ecosystem", "generic")),
                heading=str(report.get("root") or "License policy"),
                schema=str(report.get("schema")),
                metrics=[
                    ("Packages", summary.get("packages", 0)),
                    ("Denied", summary.get("deniedFindings", 0)),
                    ("Missing", summary.get("missingLicenses", 0)),
                ],
            ),
            _rows_panel(
                "License Inventory",
                report.get("licenses", []),
                ["license", "packages"],
                test_id="license-inventory-panel",
            ),
            _rows_panel(
                "Denied License Findings",
                report.get("findings", []),
                ["package", "license", "matchedDeniedLicenses"],
                test_id="license-denied-panel",
            ),
            _rows_panel(
                "Missing Licenses",
                report.get("missingLicenses", []),
                ["package"],
                test_id="license-missing-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_triage_summary_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.triage.summary.v1":
        raise ValueError("HTML triage summary input must be an EDGP report")

    summary = report.get("summary", {})
    top_findings = report.get("topFindings", {})
    top_findings = top_findings if isinstance(top_findings, dict) else {}
    npm_findings = top_findings.get("npm", [])
    return _document(
        "EDGP Triage Summary",
        [
            _generic_hero(
                eyebrow=str(report.get("status", "unknown")),
                heading="Triage summary",
                schema=str(report.get("schema")),
                metrics=[
                    ("Reports", summary.get("reports", 0)),
                    ("Advisories", summary.get("advisoryFindings", 0)),
                    ("Denied Licenses", summary.get("deniedLicenseFindings", 0)),
                ],
            ),
            _rows_panel(
                "Checks",
                report.get("checks", []),
                ["kind", "status", "findings", "deniedFindings"],
                test_id="triage-checks-panel",
            ),
            _rows_panel(
                "Advisory Findings",
                top_findings.get("advisories", []),
                ["id", "severity", "package", "summary"],
                test_id="triage-advisory-panel",
            ),
            _rows_panel(
                "License Findings",
                top_findings.get("licenses", []),
                ["package", "license", "matchedDeniedLicenses"],
                test_id="triage-license-panel",
            ),
            _rows_panel(
                "npm Signals",
                npm_findings,
                ["kind", "count", "root"],
                test_id="triage-npm-panel",
            ),
            _rows_panel(
                "Source Reports",
                report.get("reports", []),
                ["schema", "root", "summary"],
                test_id="triage-reports-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def _document(
    title: str,
    sections: list[str],
    *,
    scripts: list[str] | None = None,
) -> str:
    script_markup = [f"<script>{script}</script>" for script in scripts or []]
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
            *script_markup,
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


def _rows_panel(
    title: str,
    rows: object,
    columns: list[str],
    *,
    test_id: str,
) -> str:
    rendered_rows = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            rendered_rows.append(
                "<tr>"
                + "".join(f"<td>{escape(_cell(row.get(column)))}</td>" for column in columns)
                + "</tr>"
            )
    header = "".join(
        f'<th><button type="button" data-sort-index="{index}">{escape(_humanize_label(column))}</button></th>'
        for index, column in enumerate(columns)
    )
    body = "".join(rendered_rows) or (
        f'<tr><td colspan="{len(columns)}">No rows.</td></tr>'
    )
    return f"""
<section class="panel" data-testid="{escape(test_id)}">
  <div class="section-head">
    <h2>{escape(title)}</h2>
    <span>{len(rendered_rows)} rows</span>
  </div>
  <div class="table-wrap">
    <table data-sortable-table>
      <thead><tr>{header}</tr></thead>
      <tbody>{body}</tbody>
    </table>
  </div>
</section>""".strip()


def _cell(value: object) -> str:
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True)
    return str(value if value is not None else "")


def _dict_value(value: object, key: str) -> str:
    if isinstance(value, dict):
        return str(value.get(key, ""))
    return ""


def _humanize_label(key: str) -> str:
    return key.replace("_", " ").replace("-", " ").title()


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


def _albs_arch_summary_panel(summaries: object) -> str:
    rows = []
    if isinstance(summaries, list):
        for summary in summaries:
            if not isinstance(summary, dict):
                continue
            artifact_arches = summary.get("artifactArches", {})
            arch_text = (
                ", ".join(
                    f"{arch}: {count}"
                    for arch, count in sorted(artifact_arches.items())
                )
                if isinstance(artifact_arches, dict)
                else ""
            )
            packages = summary.get("packages", [])
            package_text = (
                ", ".join(str(package) for package in packages)
                if isinstance(packages, list)
                else ""
            )
            rows.append(
                "<tr>"
                f"<td>{escape(str(summary.get('buildArch', '')))}</td>"
                f"<td>{escape(str(summary.get('totalArtifacts', 0)))}</td>"
                f"<td>{escape(arch_text)}</td>"
                f"<td>{escape(package_text)}</td>"
                "</tr>"
            )
    body = "".join(rows) or '<tr><td colspan="4">No build architecture summaries.</td></tr>'
    return f"""
<section class="panel" data-testid="albs-arch-summary-panel">
  <div class="section-head">
    <h2>Build Architectures</h2>
    <span>{len(rows)} arches</span>
  </div>
  <div class="table-wrap">
    <table data-sortable-table>
      <thead>
        <tr>
          <th><button type="button" data-sort-index="0">Build Arch</button></th>
          <th><button type="button" data-sort-index="1" data-sort-type="number">Artifacts</button></th>
          <th><button type="button" data-sort-index="2">Artifact Arches</button></th>
          <th><button type="button" data-sort-index="3">Packages</button></th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>
  </div>
</section>""".strip()


def _albs_artifact_table(items: object) -> str:
    rows = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            rows.append(
                "<tr>"
                f"<td>{escape(str(item.get('filename', '')))}</td>"
                f"<td>{escape(str(item.get('artifactKind', '')))}</td>"
                f"<td>{escape(str(item.get('packageName', '')))}</td>"
                f"<td>{escape(str(item.get('version', '')))}</td>"
                f"<td>{escape(str(item.get('release', '')))}</td>"
                f"<td>{escape(str(item.get('artifactArch', '')))}</td>"
                f"<td>{escape(str(item.get('buildArch', '')))}</td>"
                f"<td>{escape(str(item.get('artifactNodeId', '')))}</td>"
                "</tr>"
            )
    body = "".join(rows) or '<tr><td colspan="8">No artifacts.</td></tr>'
    return f"""
<section class="panel" data-testid="albs-artifact-table-panel">
  <div class="section-head">
    <h2>Artifacts</h2>
    <span>{len(rows)} total</span>
  </div>
  <div class="table-wrap">
    <table data-sortable-table>
      <thead>
        <tr>
          <th><button type="button" data-sort-index="0">Filename</button></th>
          <th><button type="button" data-sort-index="1">Kind</button></th>
          <th><button type="button" data-sort-index="2">Package</button></th>
          <th><button type="button" data-sort-index="3">Version</button></th>
          <th><button type="button" data-sort-index="4">Release</button></th>
          <th><button type="button" data-sort-index="5">Artifact Arch</button></th>
          <th><button type="button" data-sort-index="6">Build Arch</button></th>
          <th><button type="button" data-sort-index="7">Node</button></th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>
  </div>
</section>""".strip()


def _albs_task_timing_panel(tasks: object) -> str:
    rows = []
    if isinstance(tasks, list):
        for task in tasks:
            if not isinstance(task, dict):
                continue
            artifact_counts = task.get("artifactCounts", {})
            artifact_text = (
                ", ".join(f"{key}: {value}" for key, value in sorted(artifact_counts.items()))
                if isinstance(artifact_counts, dict)
                else ""
            )
            rows.append(
                "<tr>"
                f"<td>{escape(str(task.get('taskId', '')))}</td>"
                f"<td>{escape(str(task.get('arch', '')))}</td>"
                f"<td>{escape(str(task.get('status', '')))}</td>"
                f"<td>{escape(str(task.get('wallSeconds', '')))}</td>"
                f"<td>{escape(artifact_text)}</td>"
                f"<td>{escape(str(task.get('startedAt', '')))}</td>"
                f"<td>{escape(str(task.get('finishedAt', '')))}</td>"
                "</tr>"
            )
    body = "".join(rows) or '<tr><td colspan="7">No build task timings.</td></tr>'
    return f"""
<section class="panel" data-testid="albs-task-timing-panel">
  <div class="section-head">
    <h2>Build Task Timing</h2>
    <span>{len(rows)} tasks</span>
  </div>
  <div class="table-wrap">
    <table data-sortable-table>
      <thead>
        <tr>
          <th><button type="button" data-sort-index="0">Task</button></th>
          <th><button type="button" data-sort-index="1">Arch</button></th>
          <th><button type="button" data-sort-index="2">Status</button></th>
          <th><button type="button" data-sort-index="3" data-sort-type="number">Wall Seconds</button></th>
          <th><button type="button" data-sort-index="4">Artifacts</button></th>
          <th><button type="button" data-sort-index="5">Started</button></th>
          <th><button type="button" data-sort-index="6">Finished</button></th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>
  </div>
</section>""".strip()


def _albs_sign_timing_panel(sign_tasks: object) -> str:
    rows = []
    if isinstance(sign_tasks, list):
        for sign_task in sign_tasks:
            if not isinstance(sign_task, dict):
                continue
            stats = sign_task.get("statsSeconds", {})
            stats_text = (
                ", ".join(f"{key}: {value}" for key, value in sorted(stats.items()))
                if isinstance(stats, dict)
                else ""
            )
            rows.append(
                "<tr>"
                f"<td>{escape(str(sign_task.get('signTaskId', '')))}</td>"
                f"<td>{escape(str(sign_task.get('status', '')))}</td>"
                f"<td>{escape(str(sign_task.get('wallSeconds', '')))}</td>"
                f"<td>{escape(stats_text)}</td>"
                f"<td>{escape(str(sign_task.get('startedAt', '')))}</td>"
                f"<td>{escape(str(sign_task.get('finishedAt', '')))}</td>"
                "</tr>"
            )
    body = "".join(rows) or '<tr><td colspan="6">No sign task timings.</td></tr>'
    return f"""
<section class="panel" data-testid="albs-sign-timing-panel">
  <div class="section-head">
    <h2>Sign Task Timing</h2>
    <span>{len(rows)} tasks</span>
  </div>
  <div class="table-wrap">
    <table data-sortable-table>
      <thead>
        <tr>
          <th><button type="button" data-sort-index="0">Sign Task</button></th>
          <th><button type="button" data-sort-index="1">Status</button></th>
          <th><button type="button" data-sort-index="2" data-sort-type="number">Wall Seconds</button></th>
          <th><button type="button" data-sort-index="3">Stats</button></th>
          <th><button type="button" data-sort-index="4">Started</button></th>
          <th><button type="button" data-sort-index="5">Finished</button></th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>
  </div>
</section>""".strip()


def _albs_artifact_timing_panel(artifacts: object) -> str:
    rows = []
    if isinstance(artifacts, list):
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            rows.append(
                "<tr>"
                f"<td>{escape(str(artifact.get('name', '')))}</td>"
                f"<td>{escape(str(artifact.get('artifactType', '')))}</td>"
                f"<td>{escape(str(artifact.get('packageName', '')))}</td>"
                f"<td>{escape(str(artifact.get('buildArch', '')))}</td>"
                f"<td>{escape(str(artifact.get('artifactArch', '')))}</td>"
                f"<td>{escape(str(artifact.get('taskWallSeconds', '')))}</td>"
                f"<td>{escape(str(artifact.get('buildTaskId', '')))}</td>"
                "</tr>"
            )
    body = "".join(rows) or '<tr><td colspan="7">No artifact timings.</td></tr>'
    return f"""
<section class="panel" data-testid="albs-artifact-timing-panel">
  <div class="section-head">
    <h2>Artifact Timing</h2>
    <span>{len(rows)} artifacts</span>
  </div>
  <div class="table-wrap">
    <table data-sortable-table>
      <thead>
        <tr>
          <th><button type="button" data-sort-index="0">Artifact</button></th>
          <th><button type="button" data-sort-index="1">Type</button></th>
          <th><button type="button" data-sort-index="2">Package</button></th>
          <th><button type="button" data-sort-index="3">Build Arch</button></th>
          <th><button type="button" data-sort-index="4">Artifact Arch</button></th>
          <th><button type="button" data-sort-index="5" data-sort-type="number">Task Seconds</button></th>
          <th><button type="button" data-sort-index="6">Task</button></th>
        </tr>
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
  {_edge_relationship_summary(edges)}
</section>""".strip()


def _edge_relationship_summary(edges: list[dict[str, Any]]) -> str:
    if not edges:
        return '<p class="empty">No edge relationships.</p>'
    counts: dict[int, int] = {}
    for edge in edges:
        relationship_type = _edge_relationship_type(edge)
        counts[relationship_type] = counts.get(relationship_type, 0) + 1

    rows = "\n".join(
        "<li>"
        f"<span>{escape(_relationship_label(relationship_type))}</span>"
        f"<strong>{count}</strong>"
        "</li>"
        for relationship_type, count in sorted(counts.items())
    )
    return f"""
<div class="edge-types" data-testid="edge-relationship-panel">
  <h3>Edge Relationships</h3>
  <ul>{rows}</ul>
</div>""".strip()


def _edge_explorer_panel(edges: list[dict[str, Any]]) -> str:
    relationship_types = sorted({_edge_relationship_type(edge) for edge in edges})
    options = ['<option value="">All relationships</option>']
    options.extend(
        f'<option value="{relationship_type}">'
        f"{escape(_relationship_label(relationship_type))}"
        "</option>"
        for relationship_type in relationship_types
    )
    rows = "\n".join(_edge_row(edge) for edge in edges)
    body = rows or '<tr><td colspan="3">No edges in snapshot.</td></tr>'
    more_hidden = " hidden" if len(edges) <= EDGE_EXPLORER_PAGE_SIZE else ""
    return f"""
<section class="panel" data-testid="edge-filter-panel" data-edge-filter-panel data-edge-page-size="{EDGE_EXPLORER_PAGE_SIZE}">
  <div class="section-head">
    <h2>Edge Explorer</h2>
    <span data-edge-filter-count>{len(edges)} shown</span>
  </div>
  <div class="edge-filter-controls" data-testid="edge-filter-controls">
    <label>
      <span>Source Or Target</span>
      <input type="search" data-edge-filter-search aria-label="Filter edges by source or target" placeholder="Filter edges">
    </label>
    <label>
      <span>Relationship</span>
      <select data-edge-filter-type aria-label="Filter edges by relationship type">{"".join(options)}</select>
    </label>
    <div class="edge-filter-actions">
      <button type="button" data-edge-filter-reset>Reset</button>
      <button type="button" data-edge-filter-more{more_hidden}>More</button>
    </div>
  </div>
  <div class="table-wrap">
    <table class="edge-table" data-sortable-table>
      <thead>
        <tr>
          <th><button type="button" data-sort-index="0">Source</button></th>
          <th><button type="button" data-sort-index="1">Target</button></th>
          <th><button type="button" data-sort-index="2">Relationship</button></th>
        </tr>
      </thead>
      <tbody data-edge-filter-body>{body}</tbody>
    </table>
  </div>
</section>""".strip()


def _edge_row(edge: dict[str, Any]) -> str:
    source = str(edge.get("source", ""))
    target = str(edge.get("target", ""))
    relationship_type = _edge_relationship_type(edge)
    return (
        '<tr data-edge-row '
        f'data-edge-source="{escape(source.lower())}" '
        f'data-edge-target="{escape(target.lower())}" '
        f'data-edge-type="{relationship_type}">'
        f"<td>{escape(source)}</td>"
        f"<td>{escape(target)}</td>"
        f"<td>{escape(_relationship_label(relationship_type))}</td>"
        "</tr>"
    )


def _edge_relationship_type(edge: dict[str, Any]) -> int:
    try:
        return int(edge.get("relationshipType", 1))
    except (TypeError, ValueError):
        return 1


def _relationship_label(relationship_type: int) -> str:
    labels = {
        1: "1 - Ordinary Dependency",
        2: "2 - Maven Optional",
        3: "3 - Maven Omitted",
        4: "4 - Maven Excluded",
        20: "20 - ALBS Source Package",
        21: "21 - ALBS Git Repository",
        22: "22 - ALBS Git Commit",
        23: "23 - ALBS Build Task",
        24: "24 - ALBS Build Environment",
        25: "25 - ALBS Produces Artifact",
        26: "26 - ALBS Sign Task",
        27: "27 - ALBS Test Task",
        28: "28 - ALBS Release",
        30: "30 - RPM Requires Provider",
        31: "31 - RPM Unresolved Requirement",
    }
    return labels.get(relationship_type, f"{relationship_type} - Custom Relationship")


def _edge_filter_script() -> str:
    return """
(() => {
  for (const panel of document.querySelectorAll("[data-edge-filter-panel]")) {
    const search = panel.querySelector("[data-edge-filter-search]");
    const type = panel.querySelector("[data-edge-filter-type]");
    const reset = panel.querySelector("[data-edge-filter-reset]");
    const more = panel.querySelector("[data-edge-filter-more]");
    const count = panel.querySelector("[data-edge-filter-count]");
    const currentRows = () => Array.from(panel.querySelectorAll("[data-edge-row]"));
    const pageSize = Number(panel.dataset.edgePageSize || "250");
    let visibleLimit = pageSize;
    const apply = (resetLimit = false) => {
      if (resetLimit) visibleLimit = pageSize;
      const query = (search.value || "").trim().toLowerCase();
      const selectedType = type.value;
      let matched = 0;
      let shown = 0;
      for (const row of currentRows()) {
        const edgeText = `${row.dataset.edgeSource || ""} ${row.dataset.edgeTarget || ""}`;
        const textMatches = !query || edgeText.includes(query);
        const typeMatches = !selectedType || row.dataset.edgeType === selectedType;
        const matches = textMatches && typeMatches;
        if (matches) matched += 1;
        const visible = matches && matched <= visibleLimit;
        row.hidden = !visible;
        if (visible) shown += 1;
      }
      count.textContent = matched > pageSize ? `${shown} of ${matched} shown` : `${shown} shown`;
      more.hidden = shown >= matched;
    };
    search.addEventListener("input", () => apply(true));
    type.addEventListener("change", () => apply(true));
    more.addEventListener("click", () => {
      visibleLimit += pageSize;
      apply();
    });
    reset.addEventListener("click", () => {
      search.value = "";
      type.value = "";
      apply(true);
      search.focus();
    });
    apply();
  }
})();
""".strip()


def _table_sort_script() -> str:
    return """
(() => {
  const valueFor = (row, index, type) => {
    const text = (row.cells[index]?.textContent || "").trim();
    if (type === "number") {
      const parsed = Number(text);
      return Number.isFinite(parsed) ? parsed : 0;
    }
    return text.toLowerCase();
  };
  for (const table of document.querySelectorAll("[data-sortable-table]")) {
    for (const button of table.querySelectorAll("[data-sort-index]")) {
      button.addEventListener("click", () => {
        const index = Number(button.dataset.sortIndex || "0");
        const type = button.dataset.sortType || "text";
        const direction = button.dataset.sortDirection === "asc" ? "desc" : "asc";
        for (const other of table.querySelectorAll("[data-sort-index]")) {
          other.removeAttribute("data-sort-direction");
          other.removeAttribute("aria-sort");
        }
        button.dataset.sortDirection = direction;
        button.setAttribute("aria-sort", direction === "asc" ? "ascending" : "descending");
        const body = table.tBodies[0];
        const rows = Array.from(body.rows);
        rows.sort((left, right) => {
          const leftValue = valueFor(left, index, type);
          const rightValue = valueFor(right, index, type);
          if (leftValue < rightValue) return direction === "asc" ? -1 : 1;
          if (leftValue > rightValue) return direction === "asc" ? 1 : -1;
          return 0;
        });
        body.append(...rows);
        table.dispatchEvent(new CustomEvent("edgp:table-sorted", { bubbles: true }));
      });
    }
  }
})();
""".strip()


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
    <table data-sortable-table>
      <thead>
        <tr>
          <th><button type="button" data-sort-index="0">Package</button></th>
          <th><button type="button" data-sort-index="1" data-sort-type="number">Deps</button></th>
          <th><button type="button" data-sort-index="2" data-sort-type="number">Dependents</button></th>
          <th><button type="button" data-sort-index="3">Metadata</button></th>
        </tr>
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
.edge-types {
  margin-top: 14px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.edge-types h3 {
  margin: 0 0 10px;
  font-size: 15px;
  line-height: 1.25;
}
.edge-types ul {
  display: grid;
  grid-template-columns: repeat(4, minmax(120px, 1fr));
  gap: 10px;
  margin: 0;
  padding: 0;
  list-style: none;
}
.edge-types li {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.edge-types span {
  display: block;
  color: var(--muted);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.edge-types strong {
  display: block;
  margin-top: 2px;
  font-size: 18px;
}
.edge-filter-controls {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(180px, 260px) auto;
  gap: 12px;
  align-items: end;
  margin-bottom: 14px;
}
.edge-filter-controls label {
  display: grid;
  gap: 6px;
  min-width: 0;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
.edge-filter-controls input,
.edge-filter-controls select {
  width: 100%;
  min-height: 42px;
  padding: 9px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
  color: var(--ink);
  font: inherit;
}
.edge-filter-controls button {
  min-height: 42px;
  padding: 9px 14px;
  border: 1px solid var(--ink);
  border-radius: 8px;
  background: var(--ink);
  color: #ffffff;
  font: inherit;
  cursor: pointer;
}
.edge-filter-actions {
  display: flex;
  gap: 8px;
  align-items: end;
}
.edge-filter-actions button[data-edge-filter-more] {
  background: #ffffff;
  color: var(--ink);
}
.edge-filter-actions button[hidden] { display: none; }
.edge-table td:nth-child(3) { white-space: nowrap; }
tr[hidden] { display: none; }
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
th button {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  max-width: 100%;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  text-transform: inherit;
  cursor: pointer;
}
th button::after {
  content: "\\2195";
  font-size: 11px;
  line-height: 1;
}
th button[data-sort-direction="asc"]::after { content: "\\2191"; }
th button[data-sort-direction="desc"]::after { content: "\\2193"; }
td { overflow-wrap: anywhere; }
tr:last-child td { border-bottom: 0; }
.empty { color: var(--muted); margin: 0; }
@media (max-width: 760px) {
  .report-shell { width: min(100vw - 20px, 1120px); padding-top: 10px; }
  .hero { grid-template-columns: 1fr; padding: 18px; }
  .metrics { grid-template-columns: 1fr; }
  .edge-filter-controls { grid-template-columns: 1fr; }
  .edge-types ul { grid-template-columns: 1fr; }
  h1 { font-size: 24px; }
}
""".strip()
