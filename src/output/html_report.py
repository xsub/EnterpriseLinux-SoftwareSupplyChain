"""Static HTML report exporter for EDGP JSON analysis documents."""

from __future__ import annotations

import json
import math
import re
from html import escape
from pathlib import Path
from typing import Any, Callable, Mapping

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
    if schema == "edgp.graph.diff_tree.v1":
        return render_graph_diff_tree_report(payload)
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
    if schema == "edgp.fixture.provenance.v1":
        return render_fixture_provenance_report(payload)
    if schema == "edgp.real_data.coverage.v1":
        return render_real_data_coverage_report(payload)
    if schema == "edgp.real_data.replacement_plan.v1":
        return render_real_data_replacement_plan_report(payload)
    if schema == "edgp.real_data.replacement_plan_diff.v1":
        return render_real_data_replacement_plan_diff_report(payload)
    if schema == "edgp.real_data.coverage_diff.v1":
        return render_real_data_coverage_diff_report(payload)
    if schema == "edgp.performance.report.v1":
        return render_performance_report(payload)
    if schema == "edgp.query.report.v1":
        return render_query_report(payload)
    if schema == "edgp.bundle.catalog.v1":
        return render_bundle_catalog_report(payload)
    if schema == "edgp.license.report.v1":
        return render_license_report(payload)
    if schema == "edgp.triage.summary.v1":
        return render_triage_summary_report(payload)
    if schema == "edgp.report.bundle.v1":
        return render_report_bundle_manifest_report(payload)
    if schema == "edgp.validation.report.v1":
        return render_validation_report(payload)
    if schema == "edgp.validation.failure.example.index.v1":
        return render_failure_example_index_report(payload)
    if schema == "edgp.validation.failure.example.filters.v1":
        return render_failure_example_filters_report(payload)
    if schema == "edgp.report.bundle.verification.v1":
        return render_report_bundle_verification_report(payload)
    if schema == "edgp.report.bundle.archive.v1":
        return render_report_bundle_archive_report(payload)
    if schema == "edgp.export.batch.v1":
        return render_export_batch_report(payload)
    if schema == "edgp.export.batch.verification.v1":
        return render_export_batch_verification_report(payload)
    if schema == "edgp.export.batch.archive.v1":
        return render_export_batch_archive_report(payload)
    if schema in {
        "edgp.export.batch.submission_plan.v1",
        "edgp.report.bundle.submission_plan.v1",
    }:
        return render_submission_plan_report(payload)
    if schema == "edgp.submission.plan.index.v1":
        return render_submission_plan_index_report(payload)
    if schema == "edgp.schema.index.v1":
        return render_schema_index_report(payload)
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
    classifications = report.get("classifications", [])
    top_findings = report.get("topFindings", {})
    policy = report.get("policy")
    if not isinstance(nodes, dict):
        nodes = {}
    if not isinstance(edges, dict):
        edges = {}
    if not isinstance(classifications, list):
        classifications = []
    if not isinstance(top_findings, dict):
        top_findings = {}
    if not isinstance(policy, dict):
        policy = {}
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
                    ("Classified Changes", _dict_value(summary, "classifiedChanges")),
                    ("Upgrades", _dict_value(summary, "upgradeChanges")),
                    ("Downgrades", _dict_value(summary, "downgradeChanges")),
                ],
            ),
            _graph_diff_policy_panel(policy),
            _graph_diff_top_findings_panel(top_findings),
            _graph_diff_classification_panel(classifications),
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


def _graph_diff_policy_panel(policy: dict[str, Any]) -> str:
    if not policy:
        return ""
    return _rows_panel(
        "Graph Diff Policy",
        [policy],
        [
            "status",
            "exitCode",
            "failOnChange",
            "matchedChanges",
            "failOnKind",
            "matchedKinds",
        ],
        test_id="graph-diff-policy-panel",
    )


def _graph_diff_classification_panel(classifications: list[object]) -> str:
    rows = [item for item in classifications if isinstance(item, dict)]
    return _rows_panel(
        "Change Classification",
        rows,
        [
            "kind",
            "name",
            "leftNode",
            "rightNode",
            "leftVersion",
            "rightVersion",
            "changedKeys",
        ],
        test_id="graph-diff-classification-panel",
    )


def _graph_diff_top_findings_panel(top_findings: dict[str, Any]) -> str:
    return _package_change_top_findings_panel(
        top_findings,
        test_id="graph-diff-top-findings-panel",
    )


def render_graph_diff_tree_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.graph.diff_tree.v1":
        raise ValueError("HTML graph diff tree input must be an EDGP graph diff tree report")

    summary = report.get("summary", {})
    nodes = report.get("nodes", {})
    edges = report.get("edges", {})
    classifications = report.get("classifications", [])
    top_findings = report.get("topFindings", {})
    policy = report.get("policy")
    if not isinstance(nodes, dict):
        nodes = {}
    if not isinstance(edges, dict):
        edges = {}
    if not isinstance(classifications, list):
        classifications = []
    if not isinstance(top_findings, dict):
        top_findings = {}
    if not isinstance(policy, dict):
        policy = {}
    heading = (
        f"{report.get('selector') or report.get('leftNode') or report.get('rightNode')} "
        f"({report.get('direction', 'dependencies')}, depth {report.get('depth', 0)})"
    )
    return _document(
        "EDGP Graph Diff Tree",
        [
            _generic_hero(
                eyebrow="graph diff tree",
                heading=heading,
                schema=str(report.get("schema")),
                metrics=[
                    ("Added Nodes", _dict_value(summary, "addedNodes")),
                    ("Removed Nodes", _dict_value(summary, "removedNodes")),
                    (
                        "Metadata Changed",
                        _dict_value(summary, "metadataChangedNodes"),
                    ),
                    ("Added Edges", _dict_value(summary, "addedEdges")),
                    ("Removed Edges", _dict_value(summary, "removedEdges")),
                    ("Upgrades", _dict_value(summary, "upgradeChanges")),
                    ("Replacements", _dict_value(summary, "replacementChanges")),
                ],
            ),
            _graph_diff_tree_policy_panel(policy),
            _graph_diff_tree_visual_panel(report),
            _graph_diff_tree_top_findings_panel(top_findings),
            _graph_diff_tree_classification_panel(classifications),
            _graph_diff_tree_paths_panel(nodes),
            _rows_panel(
                "Added Nodes In Focused Cone",
                nodes.get("added", []),
                ["id", "name", "version", "metadata"],
                test_id="graph-diff-tree-added-nodes-panel",
            ),
            _rows_panel(
                "Removed Nodes In Focused Cone",
                nodes.get("removed", []),
                ["id", "name", "version", "metadata"],
                test_id="graph-diff-tree-removed-nodes-panel",
            ),
            _rows_panel(
                "Metadata Changed Nodes",
                nodes.get("metadataChanged", []),
                ["id", "changedKeys", "leftMetadata", "rightMetadata"],
                test_id="graph-diff-tree-metadata-nodes-panel",
            ),
            _rows_panel(
                "Added Edges In Focused Cone",
                edges.get("added", []),
                ["source", "target", "relationshipType"],
                test_id="graph-diff-tree-added-edges-panel",
            ),
            _rows_panel(
                "Removed Edges In Focused Cone",
                edges.get("removed", []),
                ["source", "target", "relationshipType"],
                test_id="graph-diff-tree-removed-edges-panel",
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
    top_findings = report.get("topFindings", {})
    if not isinstance(top_findings, dict):
        top_findings = {}
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
            _albs_build_diff_top_findings_panel(top_findings),
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


def _albs_build_diff_top_findings_panel(top_findings: dict[str, Any]) -> str:
    rows: list[dict[str, Any]] = []
    for category, columns in (
        (
            "changed",
            ["packageName", "artifactArch", "buildArch", "changedFields"],
        ),
        (
            "added",
            ["filename", "packageName", "artifactArch", "buildArch"],
        ),
        (
            "removed",
            ["filename", "packageName", "artifactArch", "buildArch"],
        ),
        (
            "missingBuildArchitecture",
            ["side", "arch"],
        ),
        (
            "timingDelta",
            ["metric", "left", "right", "delta"],
        ),
        (
            "gitCommitChange",
            ["left", "right"],
        ),
    ):
        source_key = {
            "changed": "changedArtifacts",
            "added": "addedArtifacts",
            "removed": "removedArtifacts",
            "missingBuildArchitecture": "missingBuildArchitectures",
            "timingDelta": "timingDeltas",
            "gitCommitChange": "gitCommitChanges",
        }[category]
        findings = top_findings.get(source_key, [])
        if not isinstance(findings, list):
            continue
        for item in findings:
            if not isinstance(item, dict):
                continue
            row = {"category": category}
            for column in columns:
                row[column] = item.get(column, "")
            rows.append(row)
    return _rows_panel(
        "Top Build Changes",
        rows,
        [
            "category",
            "packageName",
            "filename",
            "artifactArch",
            "buildArch",
            "changedFields",
            "side",
            "arch",
            "metric",
            "left",
            "right",
            "delta",
        ],
        test_id="albs-build-diff-top-findings-panel",
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
    top_findings = report.get("topFindings", {})
    if not isinstance(top_findings, dict):
        top_findings = {}
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
            _rpm_repository_diff_top_findings_panel(top_findings),
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


def _rpm_repository_diff_top_findings_panel(top_findings: dict[str, Any]) -> str:
    rows: list[dict[str, Any]] = []
    for category, columns in (
        (
            "changed",
            ["name", "arch", "changedFields"],
        ),
        (
            "added",
            ["name", "version", "release", "arch", "sourceRpm"],
        ),
        (
            "removed",
            ["name", "version", "release", "arch", "sourceRpm"],
        ),
        (
            "sourceRpmDelta",
            ["status", "sourceRpm"],
        ),
    ):
        source_key = (
            f"{category}Packages"
            if category in {"changed", "added", "removed"}
            else category
        )
        findings = top_findings.get(source_key, [])
        if not isinstance(findings, list):
            continue
        for item in findings:
            if not isinstance(item, dict):
                continue
            row = {"category": category}
            for column in columns:
                row[column] = item.get(column, "")
            rows.append(row)
    return _rows_panel(
        "Top Repository Changes",
        rows,
        [
            "category",
            "name",
            "version",
            "release",
            "arch",
            "changedFields",
            "sourceRpm",
            "status",
        ],
        test_id="rpm-repository-diff-top-findings-panel",
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


def render_fixture_provenance_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.fixture.provenance.v1":
        raise ValueError("HTML fixture provenance input must be an EDGP report")

    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    return _document(
        "EDGP Fixture Provenance",
        [
            _generic_hero(
                eyebrow="fixtures",
                heading="Fixture provenance catalog",
                schema=str(report.get("schema")),
                metrics=[
                    (
                        "Public Sources",
                        summary.get("publicDerivedSources", 0),
                    ),
                    (
                        "Public Variants",
                        summary.get("deterministicPublicDerivedVariants", 0),
                    ),
                    (
                        "Generated Reports",
                        summary.get("generatedPublicReports", 0),
                    ),
                    ("Synthetic Groups", summary.get("syntheticGroups", 0)),
                    ("Cataloged Files", summary.get("catalogedFiles", 0)),
                ],
            ),
            _rows_panel(
                "Public Source URLs",
                report.get("sourceUrls", []),
                ["label", "url", "access", "refreshedAt"],
                test_id="fixture-provenance-sources-panel",
            ),
            _rows_panel(
                "Fixture Entries",
                report.get("entries", []),
                [
                    "path",
                    "kind",
                    "source",
                    "sourceUrl",
                    "reportSchema",
                    "generator",
                    "derivedFrom",
                    "bytes",
                    "sha256",
                    "notes",
                ],
                test_id="fixture-provenance-entries-panel",
            ),
            _rows_panel(
                "Synthetic Fixture Groups",
                report.get("syntheticGroups", []),
                ["group", "kind", "fileCount", "files", "sha256", "reason"],
                test_id="fixture-provenance-synthetic-groups-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_real_data_coverage_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.real_data.coverage.v1":
        raise ValueError("HTML real-data coverage input must be an EDGP report")

    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    return _document(
        "EDGP Real-Data Coverage",
        [
            _generic_hero(
                eyebrow=str(report.get("status", "coverage")),
                heading="Fixture data quality coverage",
                schema=str(report.get("schema")),
                metrics=[
                    ("Public Evidence", summary.get("publicEvidenceFiles", 0)),
                    ("Direct Sources", summary.get("directPublicSources", 0)),
                    ("Generated Reports", summary.get("generatedPublicReports", 0)),
                    ("Synthetic Files", summary.get("syntheticFiles", 0)),
                    (
                        "Coverage %",
                        summary.get("publicEvidenceCoveragePercent", 0.0),
                    ),
                    (
                        "Replacement Candidates",
                        summary.get("replacementCandidateGroups", 0),
                    ),
                ],
            ),
            _rows_panel(
                "Public Evidence",
                report.get("publicEvidence", []),
                [
                    "path",
                    "kind",
                    "source",
                    "sourceUrl",
                    "reportSchema",
                    "generator",
                    "derivedFrom",
                    "refreshedAt",
                    "notes",
                ],
                test_id="real-data-coverage-public-panel",
            ),
            _rows_panel(
                "Synthetic Fixture Groups",
                report.get("syntheticGroups", []),
                ["group", "kind", "fileCount", "files", "reason"],
                test_id="real-data-coverage-synthetic-panel",
            ),
            _rows_panel(
                "Replacement Plan",
                report.get("replacementPlan", []),
                ["group", "kind", "fileCount", "decision", "priority", "nextStep"],
                test_id="real-data-coverage-plan-panel",
            ),
            _rows_panel(
                "Policy Gate",
                _real_data_coverage_policy_rows(report.get("policy")),
                [
                    "status",
                    "minPublicEvidenceCoveragePercent",
                    "failOnPriority",
                    "matchedReplacementGroups",
                    "exitCode",
                    "failures",
                ],
                test_id="real-data-coverage-policy-panel",
            ),
            _rows_panel(
                "Quality Gates",
                report.get("qualityGates", []),
                ["name", "command"],
                test_id="real-data-coverage-gates-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def _real_data_coverage_policy_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    failures = value.get("failures", [])
    if isinstance(failures, list):
        failure_codes = [
            str(item.get("code", "unknown"))
            for item in failures
            if isinstance(item, dict)
        ]
    else:
        failure_codes = []
    return [
        {
            "status": value.get("status"),
            "minPublicEvidenceCoveragePercent": value.get(
                "minPublicEvidenceCoveragePercent"
            ),
            "failOnPriority": value.get("failOnPriority"),
            "matchedReplacementGroups": value.get("matchedReplacementGroups"),
            "exitCode": value.get("exitCode"),
            "failures": failure_codes,
        }
    ]


def render_real_data_replacement_plan_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.real_data.replacement_plan.v1":
        raise ValueError(
            "HTML real-data replacement plan input must be an EDGP report"
        )

    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    return _document(
        "EDGP Real-Data Replacement Plan",
        [
            _generic_hero(
                eyebrow=str(report.get("status", "plan")),
                heading="Public fixture replacement plan",
                schema=str(report.get("schema")),
                metrics=[
                    ("Candidates", summary.get("replacementCandidates", 0)),
                    ("Candidate Files", summary.get("candidateFiles", 0)),
                    ("High Priority", summary.get("highPriorityGroups", 0)),
                    ("Medium Priority", summary.get("mediumPriorityGroups", 0)),
                    ("Deferred", summary.get("deferredGroups", 0)),
                    (
                        "Coverage %",
                        summary.get("publicEvidenceCoveragePercent", 0.0),
                    ),
                ],
            ),
            _rows_panel(
                "Ranked Replacement Candidates",
                report.get("replacementCandidates", []),
                [
                    "rank",
                    "group",
                    "kind",
                    "fileCount",
                    "priority",
                    "decision",
                    "nextStep",
                    "files",
                ],
                test_id="real-data-replacement-plan-candidates-panel",
            ),
            _rows_panel(
                "Deferred Groups",
                report.get("deferredGroups", []),
                [
                    "group",
                    "kind",
                    "fileCount",
                    "priority",
                    "decision",
                    "nextStep",
                    "files",
                ],
                test_id="real-data-replacement-plan-deferred-panel",
            ),
            _rows_panel(
                "Coverage Context",
                [report.get("coverageSummary", {})],
                [
                    "coverageStatus",
                    "catalogedFiles",
                    "directPublicSources",
                    "generatedPublicReports",
                    "publicEvidenceFiles",
                    "syntheticFiles",
                    "publicEvidenceCoveragePercent",
                ],
                test_id="real-data-replacement-plan-coverage-panel",
            ),
            _rows_panel(
                "Policy Gate",
                _real_data_replacement_plan_policy_rows(report.get("policy")),
                [
                    "status",
                    "failOnPriority",
                    "matchedReplacementGroups",
                    "exitCode",
                    "failures",
                ],
                test_id="real-data-replacement-plan-policy-panel",
            ),
            _rows_panel(
                "Quality Gates",
                report.get("qualityGates", []),
                ["name", "command"],
                test_id="real-data-replacement-plan-gates-panel",
            ),
            _rows_panel(
                "Public Source URLs",
                report.get("sourceUrls", []),
                ["label", "url", "access", "refreshedAt"],
                test_id="real-data-replacement-plan-sources-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def _real_data_replacement_plan_policy_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    failures = value.get("failures", [])
    if isinstance(failures, list):
        failure_codes = [
            str(item.get("code", "unknown"))
            for item in failures
            if isinstance(item, dict)
        ]
    else:
        failure_codes = []
    return [
        {
            "status": value.get("status"),
            "failOnPriority": value.get("failOnPriority"),
            "matchedReplacementGroups": value.get("matchedReplacementGroups"),
            "exitCode": value.get("exitCode"),
            "failures": failure_codes,
        }
    ]


def render_real_data_replacement_plan_diff_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.real_data.replacement_plan_diff.v1":
        raise ValueError(
            "HTML real-data replacement plan diff input must be an EDGP report"
        )

    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    return _document(
        "EDGP Real-Data Replacement Plan Diff",
        [
            _generic_hero(
                eyebrow=str(report.get("status", "diff")),
                heading="Replacement backlog trend",
                schema=str(report.get("schema")),
                metrics=[
                    (
                        "Candidate Delta",
                        summary.get("replacementCandidatesDelta", 0),
                    ),
                    ("File Delta", summary.get("candidateFilesDelta", 0)),
                    ("High Delta", summary.get("highPriorityGroupsDelta", 0)),
                    ("Medium Delta", summary.get("mediumPriorityGroupsDelta", 0)),
                    ("Deferred Delta", summary.get("deferredGroupsDelta", 0)),
                    ("Regressions", summary.get("regressions", 0)),
                ],
            ),
            _rows_panel(
                "Compared Plans",
                [report.get("left", {}), report.get("right", {})],
                [
                    "label",
                    "fixtureRoot",
                    "status",
                    "replacementCandidates",
                    "candidateFiles",
                    "highPriorityGroups",
                    "mediumPriorityGroups",
                    "deferredGroups",
                    "publicEvidenceCoveragePercent",
                ],
                test_id="real-data-replacement-plan-diff-sides-panel",
            ),
            _rows_panel(
                "Regressions",
                report.get("regressions", []),
                ["code", "metric", "delta", "message"],
                test_id="real-data-replacement-plan-diff-regressions-panel",
            ),
            _rows_panel(
                "Added Candidates",
                _nested_rows(report, "replacementCandidates", "added"),
                ["rank", "group", "priority", "decision", "fileCount", "nextStep"],
                test_id="real-data-replacement-plan-diff-added-candidates-panel",
            ),
            _rows_panel(
                "Removed Candidates",
                _nested_rows(report, "replacementCandidates", "removed"),
                ["rank", "group", "priority", "decision", "fileCount", "nextStep"],
                test_id="real-data-replacement-plan-diff-removed-candidates-panel",
            ),
            _rows_panel(
                "Changed Candidates",
                _nested_rows(report, "replacementCandidates", "changed"),
                ["group", "changedKeys", "left", "right"],
                test_id="real-data-replacement-plan-diff-changed-candidates-panel",
            ),
            _rows_panel(
                "Changed Deferred Groups",
                _nested_rows(report, "deferredGroups", "changed"),
                ["group", "changedKeys", "left", "right"],
                test_id="real-data-replacement-plan-diff-deferred-panel",
            ),
            _rows_panel(
                "Policy Gate",
                _real_data_replacement_plan_diff_policy_rows(report.get("policy")),
                ["status", "failOnRegression", "exitCode", "failures"],
                test_id="real-data-replacement-plan-diff-policy-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def _real_data_replacement_plan_diff_policy_rows(
    value: object,
) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    failures = value.get("failures", [])
    if isinstance(failures, list):
        failure_codes = [
            str(item.get("code", "unknown"))
            for item in failures
            if isinstance(item, dict)
        ]
    else:
        failure_codes = []
    return [
        {
            "status": value.get("status"),
            "failOnRegression": value.get("failOnRegression"),
            "exitCode": value.get("exitCode"),
            "failures": failure_codes,
        }
    ]


def render_real_data_coverage_diff_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.real_data.coverage_diff.v1":
        raise ValueError("HTML real-data coverage diff input must be an EDGP report")

    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    return _document(
        "EDGP Real-Data Coverage Diff",
        [
            _generic_hero(
                eyebrow=str(report.get("status", "diff")),
                heading="Real-data coverage trend",
                schema=str(report.get("schema")),
                metrics=[
                    (
                        "Coverage Delta",
                        summary.get("publicEvidenceCoveragePercentDelta", 0.0),
                    ),
                    (
                        "Public Evidence Delta",
                        summary.get("publicEvidenceFilesDelta", 0),
                    ),
                    ("Synthetic Delta", summary.get("syntheticFilesDelta", 0)),
                    (
                        "Replacement Delta",
                        summary.get("replacementCandidateGroupsDelta", 0),
                    ),
                    ("Regressions", summary.get("regressions", 0)),
                ],
            ),
            _rows_panel(
                "Compared Reports",
                [report.get("left", {}), report.get("right", {})],
                [
                    "label",
                    "fixtureRoot",
                    "status",
                    "publicEvidenceCoveragePercent",
                    "publicEvidenceFiles",
                    "syntheticFiles",
                    "replacementCandidateGroups",
                ],
                test_id="real-data-coverage-diff-sides-panel",
            ),
            _rows_panel(
                "Regressions",
                report.get("regressions", []),
                ["code", "metric", "delta", "message"],
                test_id="real-data-coverage-diff-regressions-panel",
            ),
            _rows_panel(
                "Added Public Evidence",
                _nested_rows(report, "publicEvidence", "added"),
                ["path", "kind", "source", "sourceUrl", "reportSchema"],
                test_id="real-data-coverage-diff-added-public-panel",
            ),
            _rows_panel(
                "Removed Public Evidence",
                _nested_rows(report, "publicEvidence", "removed"),
                ["path", "kind", "source", "sourceUrl", "reportSchema"],
                test_id="real-data-coverage-diff-removed-public-panel",
            ),
            _rows_panel(
                "Changed Replacement Groups",
                _nested_rows(report, "replacementPlan", "changed"),
                ["group", "changedKeys", "left", "right"],
                test_id="real-data-coverage-diff-plan-panel",
            ),
            _rows_panel(
                "Policy Gate",
                _real_data_coverage_diff_policy_rows(report.get("policy")),
                ["status", "failOnRegression", "exitCode", "failures"],
                test_id="real-data-coverage-diff-policy-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def _real_data_coverage_diff_policy_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    failures = value.get("failures", [])
    if isinstance(failures, list):
        failure_codes = [
            str(item.get("code", "unknown"))
            for item in failures
            if isinstance(item, dict)
        ]
    else:
        failure_codes = []
    return [
        {
            "status": value.get("status"),
            "failOnRegression": value.get("failOnRegression"),
            "exitCode": value.get("exitCode"),
            "failures": failure_codes,
        }
    ]


def _nested_rows(report: dict[str, Any], section: str, key: str) -> list[Any]:
    value = report.get(section)
    if not isinstance(value, dict):
        return []
    rows = value.get(key, [])
    return rows if isinstance(rows, list) else []


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
                [
                    "nodes",
                    "fanout",
                    "edges",
                    "backend",
                    "buildMs",
                    "freezeMs",
                    "reachableMs",
                    "reverseReachableMs",
                    "mostDependedUponMs",
                    "accelerators",
                    "storage",
                ],
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


def render_bundle_catalog_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.bundle.catalog.v1":
        raise ValueError("HTML bundle catalog input must be an EDGP report")

    summary = report.get("summary", {})
    bundles = report.get("bundles", [])
    source_kinds = report.get("sourceKinds", [])
    return _document(
        "EDGP Bundle Catalog",
        [
            _generic_hero(
                eyebrow="report bundles",
                heading="Bundle catalog",
                schema=str(report.get("schema")),
                metrics=[
                    ("Status", report.get("status", "")),
                    ("Bundles", _dict_value(summary, "bundles")),
                    ("OK", _dict_value(summary, "okBundles")),
                    ("Failed", _dict_value(summary, "failedBundles")),
                    ("Reports", _dict_value(summary, "reports")),
                    (
                        "Diff Tree Policies",
                        _dict_value(summary, "diffTreePolicyFailures"),
                    ),
                    (
                        "Real-Data Policies",
                        _dict_value(summary, "realDataCoveragePolicyFailures"),
                    ),
                    (
                        "Real-Data Diff Policies",
                        _dict_value(summary, "realDataCoverageDiffPolicyFailures"),
                    ),
                    (
                        "Replacement Plan Policies",
                        _dict_value(
                            summary,
                            "realDataReplacementPlanPolicyFailures",
                        ),
                    ),
                    (
                        "Replacement Plan Diff Policies",
                        _dict_value(
                            summary,
                            "realDataReplacementPlanDiffPolicyFailures",
                        ),
                    ),
                ],
            ),
            _bundle_catalog_filter_panel(bundles),
            _rows_panel(
                "Bundle Verification",
                bundles,
                [
                    "path",
                    "inputType",
                    "ok",
                    "sourceKind",
                    "reportCount",
                    "triageStatus",
                    "graphDiffPolicyFailures",
                    "diffTreePolicyFailures",
                    "realDataCoveragePolicyFailures",
                    "realDataCoverageDiffPolicyFailures",
                    "realDataReplacementPlanPolicyFailures",
                    "realDataReplacementPlanDiffPolicyFailures",
                    "realDataCoverageFailureCodes",
                    "realDataCoverageDiffFailureCodes",
                    "realDataReplacementPlanFailureCodes",
                    "realDataReplacementPlanDiffFailureCodes",
                    "graphDiffMatchedChanges",
                    "graphDiffMatchedKinds",
                    "diffTreeMatchedKinds",
                    "failureCount",
                    "failureCodes",
                    "reportSchemas",
                    "bundleSha256",
                ],
                test_id="bundle-catalog-bundles-panel",
                row_attrs=_bundle_catalog_bundle_row_attrs,
            ),
            _rows_panel(
                "Source Kinds",
                source_kinds,
                [
                    "sourceKind",
                    "bundles",
                    "reports",
                    "failures",
                    "graphDiffPolicyFailures",
                    "diffTreePolicyFailures",
                    "realDataCoveragePolicyFailures",
                    "realDataCoverageDiffPolicyFailures",
                    "realDataReplacementPlanPolicyFailures",
                    "realDataReplacementPlanDiffPolicyFailures",
                    "failureCodes",
                    "realDataCoverageFailureCodes",
                    "realDataCoverageDiffFailureCodes",
                    "realDataReplacementPlanFailureCodes",
                    "realDataReplacementPlanDiffFailureCodes",
                    "triagePass",
                    "triageWarn",
                    "triageFail",
                    "withoutTriage",
                ],
                test_id="bundle-catalog-source-kinds-panel",
            ),
        ],
        scripts=[_bundle_catalog_filter_script(), _table_sort_script()],
    )


def _bundle_catalog_filter_panel(rows: object) -> str:
    bundles = (
        [row for row in rows if isinstance(row, dict)]
        if isinstance(rows, list)
        else []
    )
    source_kinds = sorted(
        {
            str(row.get("sourceKind"))
            for row in bundles
            if isinstance(row.get("sourceKind"), str) and row.get("sourceKind")
        }
    )
    triage_statuses = sorted(
        {
            str(row.get("triageStatus"))
            for row in bundles
            if isinstance(row.get("triageStatus"), str) and row.get("triageStatus")
        }
    )
    source_options = "".join(
        f'<option value="{escape(source_kind)}">{escape(source_kind)}</option>'
        for source_kind in source_kinds
    )
    status_options = "".join(
        f'<option value="{escape(status)}">{escape(status)}</option>'
        for status in triage_statuses
    )
    return f"""
<section class="panel" data-testid="bundle-catalog-filter-panel" data-bundle-catalog-filter-panel>
  <div class="section-head">
    <h2>Catalog Filters</h2>
    <span data-bundle-catalog-filter-count>{len(bundles)} rows</span>
  </div>
  <div class="bundle-catalog-filter-controls">
    <label>Search
      <input type="search" data-bundle-catalog-search aria-label="Filter bundle rows by text" placeholder="Path, code, schema">
    </label>
    <label>Source Kind
      <select data-bundle-catalog-source aria-label="Filter bundle rows by source kind">
        <option value="">All</option>{source_options}
      </select>
    </label>
    <label>Triage Status
      <select data-bundle-catalog-status aria-label="Filter bundle rows by triage status">
        <option value="">All</option>{status_options}
      </select>
    </label>
    <label class="checkbox-control">
      <input type="checkbox" data-bundle-catalog-problems>
      <span>Problem bundles only</span>
    </label>
    <div class="bundle-catalog-filter-actions">
      <button type="button" data-bundle-catalog-reset>Reset</button>
    </div>
  </div>
</section>""".strip()


def _bundle_catalog_bundle_row_attrs(row: dict[str, Any]) -> Mapping[str, object]:
    policy_failures = sum(
        int(row.get(key, 0) or 0)
        for key in (
            "graphDiffPolicyFailures",
            "diffTreePolicyFailures",
            "realDataCoveragePolicyFailures",
            "realDataCoverageDiffPolicyFailures",
            "realDataReplacementPlanPolicyFailures",
            "realDataReplacementPlanDiffPolicyFailures",
        )
    )
    failure_count = int(row.get("failureCount", 0) or 0)
    triage_status = str(row.get("triageStatus") or "")
    problem = (
        row.get("ok") is not True
        or failure_count > 0
        or policy_failures > 0
        or triage_status in {"warn", "fail"}
    )
    return {
        "data-bundle-catalog-row": "true",
        "data-source-kind": row.get("sourceKind") or "",
        "data-triage-status": triage_status,
        "data-bundle-problem": str(problem).lower(),
    }


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
    bundle_catalog_findings = top_findings.get("bundleCatalog", [])
    diff_policy_findings = top_findings.get("graphDiffPolicies", [])
    diff_tree_policy_findings = top_findings.get("diffTreePolicies", [])
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
                    (
                        "Graph Diff Policies",
                        summary.get("graphDiffPolicyFailures", 0),
                    ),
                    (
                        "Diff Tree Policies",
                        summary.get("diffTreePolicyFailures", 0),
                    ),
                    (
                        "Real-Data Policies",
                        summary.get("realDataCoveragePolicyFailures", 0),
                    ),
                    (
                        "Real-Data Diff Policies",
                        summary.get("realDataCoverageDiffPolicyFailures", 0),
                    ),
                    (
                        "Replacement Plan Policies",
                        summary.get("realDataReplacementPlanPolicyFailures", 0),
                    ),
                    (
                        "Replacement Plan Diff Policies",
                        summary.get(
                            "realDataReplacementPlanDiffPolicyFailures",
                            0,
                        ),
                    ),
                ],
            ),
            _rows_panel(
                "Checks",
                report.get("checks", []),
                [
                    "kind",
                    "status",
                    "findings",
                    "deniedFindings",
                    "failOnChange",
                    "matchedChanges",
                    "failOnKind",
                    "matchedKinds",
                    "realDataCoveragePolicyFailures",
                    "realDataCoverageDiffPolicyFailures",
                    "realDataReplacementPlanPolicyFailures",
                    "realDataReplacementPlanDiffPolicyFailures",
                    "failOnPriority",
                    "matchedReplacementGroups",
                    "failOnRegression",
                    "exitCode",
                ],
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
                "Bundle Catalog Findings",
                bundle_catalog_findings,
                [
                    "path",
                    "sourceKind",
                    "ok",
                    "failureCount",
                    "triageStatus",
                    "graphDiffPolicyFailures",
                    "diffTreePolicyFailures",
                    "realDataCoveragePolicyFailures",
                    "realDataCoverageDiffPolicyFailures",
                    "realDataReplacementPlanPolicyFailures",
                    "realDataReplacementPlanDiffPolicyFailures",
                    "realDataCoverageFailureCodes",
                    "realDataCoverageDiffFailureCodes",
                    "realDataReplacementPlanFailureCodes",
                    "realDataReplacementPlanDiffFailureCodes",
                    "graphDiffMatchedChanges",
                    "graphDiffMatchedKinds",
                    "diffTreeMatchedKinds",
                    "failureCodes",
                ],
                test_id="triage-bundle-catalog-panel",
            ),
            _rows_panel(
                "Graph Diff Policy Findings",
                diff_policy_findings,
                [
                    "leftRoot",
                    "rightRoot",
                    "failOnChange",
                    "matchedChanges",
                    "failOnKind",
                    "matchedKinds",
                    "exitCode",
                ],
                test_id="triage-graph-diff-policy-panel",
            ),
            _rows_panel(
                "Diff Tree Policy Findings",
                diff_tree_policy_findings,
                [
                    "selector",
                    "direction",
                    "depth",
                    "failOnKind",
                    "matchedKinds",
                    "exitCode",
                ],
                test_id="triage-diff-tree-policy-panel",
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


def render_report_bundle_manifest_report(manifest: dict[str, Any]) -> str:
    if manifest.get("schema") != "edgp.report.bundle.v1":
        raise ValueError("HTML report bundle manifest input must be an EDGP manifest")

    bundle = manifest.get("bundle", {})
    if not isinstance(bundle, dict):
        bundle = {}
    reports = manifest.get("reports", [])
    if not isinstance(reports, list):
        reports = []
    triage_summary = manifest.get("triageSummary")

    sections = [
        _generic_hero(
            eyebrow=str(bundle.get("sourceKind") or "report bundle"),
            heading="Report bundle manifest",
            schema=str(manifest.get("schema")),
            metrics=[
                ("Reports", manifest.get("reportCount", len(reports))),
                ("Index", manifest.get("index", "")),
                ("Bundle SHA-256", manifest.get("bundleSha256", "")),
            ],
        ),
        _rows_panel(
            "Bundle",
            [_report_bundle_manifest_row(manifest, bundle)],
            ["sourceKind", "index", "reportCount", "bundleSha256", "command"],
            test_id="report-bundle-manifest-panel",
        ),
        _rows_panel(
            "Reports",
            _report_bundle_manifest_report_rows(reports),
            [
                "title",
                "schema",
                "source",
                "href",
                "sourceSha256",
                "htmlSha256",
                "summary",
            ],
            test_id="report-bundle-manifest-reports-panel",
        ),
    ]

    metadata_rows = _report_bundle_manifest_metadata_rows(bundle)
    if metadata_rows:
        sections.append(
            _rows_panel(
                "Bundle Metadata",
                metadata_rows,
                ["key", "value"],
                test_id="report-bundle-manifest-metadata-panel",
            )
        )

    if isinstance(triage_summary, dict):
        sections.append(
            _rows_panel(
                "Triage Summary",
                [_report_bundle_manifest_entry_row(triage_summary)],
                [
                    "title",
                    "schema",
                    "source",
                    "href",
                    "sourceSha256",
                    "htmlSha256",
                    "summary",
                ],
                test_id="report-bundle-manifest-triage-panel",
            )
        )

    return _document(
        "EDGP Report Bundle Manifest",
        sections,
        scripts=[_table_sort_script()],
    )


def _report_bundle_manifest_row(
    manifest: dict[str, Any],
    bundle: dict[str, Any],
) -> dict[str, object]:
    return {
        "sourceKind": bundle.get("sourceKind", ""),
        "index": manifest.get("index", ""),
        "reportCount": manifest.get("reportCount", ""),
        "bundleSha256": manifest.get("bundleSha256", ""),
        "command": bundle.get("command", ""),
    }


def _report_bundle_manifest_report_rows(
    reports: list[object],
) -> list[dict[str, object]]:
    return [
        _report_bundle_manifest_entry_row(report)
        for report in reports
        if isinstance(report, dict)
    ]


def _report_bundle_manifest_entry_row(entry: dict[str, object]) -> dict[str, object]:
    return {
        "title": entry.get("title", ""),
        "schema": entry.get("schema", ""),
        "source": entry.get("source", ""),
        "href": entry.get("href", ""),
        "sourceSha256": entry.get("sourceSha256", ""),
        "htmlSha256": entry.get("htmlSha256", ""),
        "summary": entry.get("summary", {}),
    }


def _report_bundle_manifest_metadata_rows(
    bundle: dict[str, Any],
) -> list[dict[str, object]]:
    return [
        {"key": str(key), "value": value}
        for key, value in sorted(bundle.items(), key=lambda item: str(item[0]))
    ]


def render_validation_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.validation.report.v1":
        raise ValueError("HTML validation input must be an EDGP validation report")

    summary = report.get("summary", {})
    sections = [
        _generic_hero(
            eyebrow="ok" if report.get("ok") is True else "failed",
            heading=str(report.get("targetType") or "Validation report"),
            schema=str(report.get("schema")),
            metrics=[
                ("Contract", report.get("contract", "")),
                ("Failures", _dict_value(summary, "failures")),
            ],
        ),
        _rows_panel(
            "Validation Target",
            [_validation_target_row(report)],
            ["target", "targetType", "contract", "schemaFile", "ok"],
            test_id="validation-target-panel",
        ),
        _rows_panel(
            "Failures",
            report.get("failures", []),
            ["code", "message", "path"],
            test_id="validation-failures-panel",
        ),
        _rows_panel(
            "Nested Verification",
            _validation_verification_rows(report),
            [
                "kind",
                "schema",
                "ok",
                "path",
                "manifest",
                "fingerprint",
                "reports",
                "exports",
                "files",
                "bytes",
                "failures",
            ],
            test_id="validation-nested-verification-panel",
        ),
    ]
    triage_summary = report.get("triageSummary")
    if isinstance(triage_summary, dict):
        sections.append(
            _rows_panel(
                "Triage Summary",
                [_validation_triage_row(triage_summary)],
                [
                    "schema",
                    "source",
                    "status",
                    "reports",
                    "failedChecks",
                    "diffTreePolicyFailures",
                    "advisoryFindings",
                    "deniedLicenseFindings",
                    "npmSignals",
                    "summary",
                ],
                test_id="validation-triage-panel",
            )
        )
        sections.append(
            _rows_panel(
                "Triage Top Findings",
                _validation_top_finding_rows(triage_summary.get("topFindings")),
                _validation_top_finding_columns(),
                test_id="validation-triage-top-findings-panel",
            )
        )
    report_summary = report.get("reportSummary")
    report_status = report.get("reportStatus")
    if isinstance(report_summary, dict) or isinstance(report_status, str):
        sections.append(
            _rows_panel(
                "Validated Report Summary",
                [_validation_report_summary_row(report)],
                [
                    "status",
                    "reports",
                    "bundles",
                    "okBundles",
                    "failedBundles",
                    "failures",
                    "triageWarn",
                    "triageFail",
                    "diffTreePolicyFailures",
                    "summary",
                ],
                test_id="validation-report-summary-panel",
            )
        )
    sections.append(
        _rows_panel(
            "Validated Report Top Findings",
            _validation_top_finding_rows(report.get("reportTopFindings")),
            _validation_top_finding_columns(),
            test_id="validation-report-top-findings-panel",
        )
    )
    return _document(
        "EDGP Validation Report",
        sections,
        scripts=[_table_sort_script()],
    )


def render_failure_example_index_report(index: dict[str, Any]) -> str:
    if index.get("schema") != "edgp.validation.failure.example.index.v1":
        raise ValueError(
            "HTML failure example input must be an EDGP failure example index"
        )

    examples = index.get("examples", [])
    example_rows = _failure_example_rows(examples)
    contract_count = len({row["contract"] for row in example_rows if row["contract"]})
    target_type_count = len(
        {row["targetType"] for row in example_rows if row["targetType"]}
    )
    validation_code_count = len(
        {
            code
            for row in example_rows
            for code in _split_codes(str(row["validationFailureCodes"]))
        }
    )
    verification_code_count = len(
        {
            code
            for row in example_rows
            for code in _split_codes(str(row["verificationFailureCodes"]))
        }
    )
    return _document(
        "EDGP Validation Failure Examples",
        [
            _generic_hero(
                eyebrow="failure examples",
                heading="Validation failure catalog",
                schema=str(index.get("schema")),
                metrics=[
                    ("Examples", index.get("exampleCount", len(example_rows))),
                    ("Contracts", contract_count),
                    ("Target Types", target_type_count),
                    ("Validation Codes", validation_code_count),
                    ("Verifier Codes", verification_code_count),
                ],
            ),
            _rows_panel(
                "Examples",
                example_rows,
                [
                    "id",
                    "targetType",
                    "contract",
                    "target",
                    "firstFailureCode",
                    "firstFailurePath",
                    "validationFailureCodes",
                    "verificationFailureCodes",
                    "validationFixture",
                    "verificationFixture",
                ],
                test_id="failure-example-index-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_failure_example_filters_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.validation.failure.example.filters.v1":
        raise ValueError(
            "HTML failure filters input must be an EDGP failure filter listing"
        )

    rows = _failure_example_filter_rows(report)
    return _document(
        "EDGP Validation Failure Example Filters",
        [
            _generic_hero(
                eyebrow="failure filters",
                heading="Validation failure filter catalog",
                schema=str(report.get("schema")),
                metrics=[
                    ("Examples", report.get("exampleCount", 0)),
                    ("Ids", _list_len(report.get("ids"))),
                    ("Contracts", _list_len(report.get("contracts"))),
                    ("Target Types", _list_len(report.get("targetTypes"))),
                    (
                        "Validation Codes",
                        _list_len(report.get("validationFailureCodes")),
                    ),
                    (
                        "Verifier Codes",
                        _list_len(report.get("verificationFailureCodes")),
                    ),
                ],
            ),
            _rows_panel(
                "Available Filters",
                rows,
                ["kind", "count", "values"],
                test_id="failure-example-filters-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def _validation_target_row(report: dict[str, object]) -> dict[str, object]:
    return {
        "target": report.get("target", ""),
        "targetType": report.get("targetType", ""),
        "contract": report.get("contract", ""),
        "schemaFile": report.get("schemaFile", ""),
        "ok": report.get("ok", ""),
    }


def _failure_example_rows(examples: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not isinstance(examples, list):
        return rows
    for example in examples:
        if not isinstance(example, dict):
            continue
        first_failure = example.get("firstFailure", {})
        if not isinstance(first_failure, dict):
            first_failure = {}
        rows.append(
            {
                "id": example.get("id", ""),
                "targetType": example.get("targetType", ""),
                "contract": example.get("contract", ""),
                "target": example.get("target", ""),
                "firstFailureCode": first_failure.get("code", ""),
                "firstFailurePath": first_failure.get("path", ""),
                "validationFailureCodes": ", ".join(
                    _as_string_list(example.get("validationFailureCodes"))
                ),
                "verificationFailureCodes": ", ".join(
                    _as_string_list(example.get("verificationFailureCodes"))
                ),
                "validationFixture": example.get("validationFixture", ""),
                "verificationFixture": example.get("verificationFixture", ""),
            }
        )
    return rows


def _failure_example_filter_rows(report: dict[str, object]) -> list[dict[str, object]]:
    return [
        _failure_example_filter_row("ids", report.get("ids")),
        _failure_example_filter_row("contracts", report.get("contracts")),
        _failure_example_filter_row("targetTypes", report.get("targetTypes")),
        _failure_example_filter_row(
            "validationFailureCodes",
            report.get("validationFailureCodes"),
        ),
        _failure_example_filter_row(
            "verificationFailureCodes",
            report.get("verificationFailureCodes"),
        ),
    ]


def _failure_example_filter_row(kind: str, values: object) -> dict[str, object]:
    items = _as_string_list(values)
    return {"kind": kind, "count": len(items), "values": ", ".join(items)}


def _split_codes(value: str) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _list_len(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _validation_triage_row(triage_summary: dict[str, object]) -> dict[str, object]:
    summary = triage_summary.get("summary", {})
    summary = summary if isinstance(summary, dict) else {}
    return {
        "schema": triage_summary.get("schema", ""),
        "source": triage_summary.get("source", ""),
        "status": triage_summary.get("status", ""),
        "reports": summary.get("reports", ""),
        "failedChecks": summary.get("failedChecks", ""),
        "diffTreePolicyFailures": summary.get("diffTreePolicyFailures", ""),
        "advisoryFindings": summary.get("advisoryFindings", ""),
        "deniedLicenseFindings": summary.get("deniedLicenseFindings", ""),
        "npmSignals": _triage_npm_signal_count(summary),
        "summary": summary,
    }


def _validation_report_summary_row(report: dict[str, object]) -> dict[str, object]:
    summary = report.get("reportSummary", {})
    if not isinstance(summary, dict):
        summary = {}
    return {
        "status": report.get("reportStatus", ""),
        "reports": summary.get("reports", ""),
        "bundles": summary.get("bundles", ""),
        "okBundles": summary.get("okBundles", ""),
        "failedBundles": summary.get("failedBundles", ""),
        "failures": summary.get("failures", ""),
        "triageWarn": summary.get("triageWarn", ""),
        "triageFail": summary.get("triageFail", ""),
        "diffTreePolicyFailures": summary.get("diffTreePolicyFailures", ""),
        "summary": summary,
    }


def _validation_top_finding_rows(top_findings: object) -> list[dict[str, object]]:
    if not isinstance(top_findings, dict):
        return []
    rows: list[dict[str, object]] = []
    for category in sorted(top_findings):
        findings = top_findings.get(category)
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            row: dict[str, object] = {"category": category}
            row.update(finding)
            rows.append(row)
    return rows


def _validation_top_finding_columns() -> list[str]:
    return [
        "category",
        "path",
        "sourceKind",
        "triageStatus",
        "graphDiffPolicyFailures",
        "diffTreePolicyFailures",
        "graphDiffFailOnChanges",
        "graphDiffMatchedChanges",
        "graphDiffFailOnKinds",
        "graphDiffMatchedKinds",
        "diffTreeFailOnKinds",
        "diffTreeMatchedKinds",
        "leftRoot",
        "rightRoot",
        "failOnChange",
        "matchedChanges",
        "failOnKind",
        "matchedKinds",
        "selector",
        "direction",
        "depth",
        "id",
        "severity",
        "package",
        "license",
        "kind",
        "count",
    ]


def _triage_npm_signal_count(summary: Mapping[str, object]) -> int:
    return sum(
        int(summary.get(key, 0) or 0)
        for key in (
            "npmDuplicatePackageNames",
            "npmNestedResolutionConflicts",
            "npmUnresolvedDependencies",
        )
    )


def _validation_verification_rows(report: dict[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for kind, key in [
        ("report bundle", "bundleVerification"),
        ("report bundle archive", "bundleArchiveVerification"),
        ("export batch", "exportBatchVerification"),
        ("export batch archive", "exportBatchArchiveVerification"),
    ]:
        verification = report.get(key)
        if isinstance(verification, dict):
            rows.append(_validation_verification_row(kind, verification))
    return rows


def _validation_verification_row(
    kind: str,
    verification: dict[str, object],
) -> dict[str, object]:
    summary = verification.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    nested = verification.get("verification", {})
    if not isinstance(nested, dict):
        nested = {}
    nested_summary = nested.get("summary", {})
    if not isinstance(nested_summary, dict):
        nested_summary = {}
    return {
        "kind": kind,
        "schema": verification.get("schema", ""),
        "ok": verification.get("ok", ""),
        "path": (
            verification.get("archive")
            or verification.get("bundleDir")
            or verification.get("batchDir")
            or ""
        ),
        "manifest": verification.get("manifest") or nested.get("manifest") or "",
        "fingerprint": (
            verification.get("archiveSha256")
            or verification.get("bundleSha256")
            or verification.get("manifestSha256")
            or ""
        ),
        "reports": summary.get("reports") or nested_summary.get("reports") or "",
        "exports": summary.get("exports") or nested_summary.get("exports") or "",
        "files": summary.get("files", ""),
        "bytes": summary.get("bytes", ""),
        "failures": summary.get("failures")
        if "failures" in summary
        else summary.get("verificationFailures", ""),
    }


def render_report_bundle_verification_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.report.bundle.verification.v1":
        raise ValueError("HTML report bundle verification input must be an EDGP report")

    summary = report.get("summary", {})
    return _document(
        "EDGP Report Bundle Verification",
        [
            _generic_hero(
                eyebrow="ok" if report.get("ok") is True else "failed",
                heading="Report bundle verification",
                schema=str(report.get("schema")),
                metrics=[
                    ("Reports", _dict_value(summary, "reports")),
                    ("Failures", _dict_value(summary, "failures")),
                ],
            ),
            _rows_panel(
                "Verified Bundle",
                [_report_bundle_verification_row(report)],
                ["bundleDir", "manifest", "bundleSha256", "ok"],
                test_id="report-bundle-verification-report-panel",
            ),
            _rows_panel(
                "Failures",
                report.get("failures", []),
                ["code", "message", "path"],
                test_id="report-bundle-verification-failures-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_report_bundle_archive_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.report.bundle.archive.v1":
        raise ValueError("HTML report bundle archive input must be an EDGP report")

    summary = report.get("summary", {})
    verification = report.get("verification", {})
    if not isinstance(verification, dict):
        verification = {}
    return _document(
        "EDGP Report Bundle Archive",
        [
            _generic_hero(
                eyebrow="ok" if report.get("ok") is True else "failed",
                heading="Deterministic report bundle archive",
                schema=str(report.get("schema")),
                metrics=[
                    ("Files", _dict_value(summary, "files")),
                    ("Bytes", _dict_value(summary, "bytes")),
                    (
                        "Verification Failures",
                        _dict_value(summary, "verificationFailures"),
                    ),
                ],
            ),
            _rows_panel(
                "Archive",
                [_report_bundle_archive_row(report)],
                ["archive", "bundleDir", "ok", "archiveSha256", "bundleSha256"],
                test_id="report-bundle-archive-panel",
            ),
            _rows_panel(
                "Embedded Verification",
                [_report_bundle_verification_row(verification)] if verification else [],
                ["bundleDir", "manifest", "bundleSha256", "ok"],
                test_id="report-bundle-archive-verification-panel",
            ),
            _rows_panel(
                "Failures",
                verification.get("failures", []),
                ["code", "message", "path"],
                test_id="report-bundle-archive-failures-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def _report_bundle_verification_row(report: dict[str, object]) -> dict[str, object]:
    return {
        "bundleDir": report.get("bundleDir", ""),
        "manifest": report.get("manifest", ""),
        "bundleSha256": report.get("bundleSha256", ""),
        "ok": report.get("ok", ""),
    }


def _report_bundle_archive_row(report: dict[str, object]) -> dict[str, object]:
    return {
        "archive": report.get("archive", ""),
        "bundleDir": report.get("bundleDir", ""),
        "ok": report.get("ok", ""),
        "archiveSha256": report.get("archiveSha256", ""),
        "bundleSha256": report.get("bundleSha256", ""),
    }


def render_export_batch_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.export.batch.v1":
        raise ValueError("HTML export batch input must be an EDGP export batch")

    summary = report.get("summary", {})
    source = report.get("source", {})
    if not isinstance(source, dict):
        source = {}
    heading = str(source.get("root") or "Graph export batch")
    return _document(
        "EDGP Export Batch",
        [
            _generic_hero(
                eyebrow=str(source.get("ecosystem", "export batch")),
                heading=heading,
                schema=str(report.get("schema")),
                metrics=[
                    ("Exports", _dict_value(summary, "exports")),
                    ("Formats", ", ".join(_as_string_list(summary.get("formats")))),
                    ("Bytes", _dict_value(summary, "bytes")),
                ],
            ),
            _rows_panel(
                "Source Snapshot",
                _export_batch_source_rows(source, report.get("command")),
                ["path", "root", "ecosystem", "nodes", "edges", "command"],
                test_id="export-batch-source-panel",
            ),
            _rows_panel(
                "Export Artifacts",
                report.get("exports", []),
                ["format", "path", "mediaType", "bytes", "sha256"],
                test_id="export-batch-artifacts-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_export_batch_verification_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.export.batch.verification.v1":
        raise ValueError("HTML export batch verification input must be an EDGP report")

    summary = report.get("summary", {})
    heading = "Export batch verification"
    return _document(
        "EDGP Export Batch Verification",
        [
            _generic_hero(
                eyebrow="ok" if report.get("ok") is True else "failed",
                heading=heading,
                schema=str(report.get("schema")),
                metrics=[
                    ("Exports", _dict_value(summary, "exports")),
                    ("Bytes", _dict_value(summary, "bytes")),
                    ("Failures", _dict_value(summary, "failures")),
                ],
            ),
            _rows_panel(
                "Verified Batch",
                [_export_batch_verification_row(report)],
                ["batchDir", "manifest", "manifestSha256", "ok"],
                test_id="export-batch-verification-panel",
            ),
            _rows_panel(
                "Failures",
                report.get("failures", []),
                ["code", "message", "path"],
                test_id="export-batch-failures-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_export_batch_archive_report(report: dict[str, Any]) -> str:
    if report.get("schema") != "edgp.export.batch.archive.v1":
        raise ValueError("HTML export batch archive input must be an EDGP report")

    summary = report.get("summary", {})
    verification = report.get("verification", {})
    if not isinstance(verification, dict):
        verification = {}
    return _document(
        "EDGP Export Batch Archive",
        [
            _generic_hero(
                eyebrow="ok" if report.get("ok") is True else "failed",
                heading="Deterministic export batch archive",
                schema=str(report.get("schema")),
                metrics=[
                    ("Files", _dict_value(summary, "files")),
                    ("Bytes", _dict_value(summary, "bytes")),
                    (
                        "Verification Failures",
                        _dict_value(summary, "verificationFailures"),
                    ),
                ],
            ),
            _rows_panel(
                "Archive",
                [_export_batch_archive_row(report)],
                [
                    "archive",
                    "batchDir",
                    "ok",
                    "archiveSha256",
                    "manifestSha256",
                ],
                test_id="export-batch-archive-panel",
            ),
            _rows_panel(
                "Embedded Verification",
                [_export_batch_verification_row(verification)] if verification else [],
                ["batchDir", "manifest", "manifestSha256", "ok"],
                test_id="export-batch-archive-verification-panel",
            ),
            _rows_panel(
                "Failures",
                verification.get("failures", []),
                ["code", "message", "path"],
                test_id="export-batch-archive-failures-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def _export_batch_source_rows(
    source: dict[str, object], command: object
) -> list[dict[str, object]]:
    stats = source.get("stats", {})
    if not isinstance(stats, dict):
        stats = {}
    return [
        {
            "path": source.get("path", ""),
            "root": source.get("root", ""),
            "ecosystem": source.get("ecosystem", ""),
            "nodes": stats.get("nodes", ""),
            "edges": stats.get("edges", ""),
            "command": command or "",
        }
    ]


def _export_batch_verification_row(report: dict[str, object]) -> dict[str, object]:
    return {
        "batchDir": report.get("batchDir", ""),
        "manifest": report.get("manifest", ""),
        "manifestSha256": report.get("manifestSha256", ""),
        "ok": report.get("ok", ""),
    }


def _export_batch_archive_row(report: dict[str, object]) -> dict[str, object]:
    return {
        "archive": report.get("archive", ""),
        "batchDir": report.get("batchDir", ""),
        "ok": report.get("ok", ""),
        "archiveSha256": report.get("archiveSha256", ""),
        "manifestSha256": report.get("manifestSha256", ""),
    }


def render_submission_plan_report(report: dict[str, Any]) -> str:
    schemas = {
        "edgp.export.batch.submission_plan.v1",
        "edgp.report.bundle.submission_plan.v1",
    }
    if report.get("schema") not in schemas:
        raise ValueError("HTML submission plan input must be an EDGP submission plan")

    summary = report.get("summary", {})
    source = report.get("source", {})
    target = report.get("target", {})
    if not isinstance(source, dict):
        source = {}
    if not isinstance(target, dict):
        target = {}
    target_kind = str(target.get("kind") or "submission target")
    title = f"EDGP Submission Plan - {target_kind}"
    source_rows = [_submission_source_row(source)] if source else []
    return _document(
        title,
        [
            _generic_hero(
                eyebrow="submission plan",
                heading=target_kind,
                schema=str(report.get("schema")),
                metrics=[
                    ("Mode", report.get("mode", "")),
                    ("Target", target.get("endpoint", "")),
                    ("Artifacts", _dict_value(summary, "artifacts")),
                    ("Bytes", _dict_value(summary, "bytes")),
                    ("Failures", _dict_value(summary, "failures")),
                    ("Reports", _dict_value(summary, "reports")),
                ],
            ),
            _rows_panel(
                "Selected Artifacts",
                _submission_artifact_rows(report.get("artifacts", [])),
                ["kind", "path", "mediaType", "bytes", "action", "method", "endpoint"],
                test_id="submission-artifacts-panel",
            ),
            _rows_panel(
                "Source",
                source_rows,
                [
                    "inputType",
                    "path",
                    "manifest",
                    "manifestSha256",
                    "bundleSha256",
                    "archiveSha256",
                ],
                test_id="submission-source-panel",
            ),
            _rows_panel(
                "Failures",
                report.get("failures", []),
                ["code", "message", "path"],
                test_id="submission-failures-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_submission_plan_index_report(index: dict[str, Any]) -> str:
    if index.get("schema") != "edgp.submission.plan.index.v1":
        raise ValueError("HTML submission index input must be an EDGP submission index")

    summary = index.get("summary", {})
    return _document(
        "EDGP Submission Plan Index",
        [
            _generic_hero(
                eyebrow="submission index",
                heading="Dry-run submission index",
                schema=str(index.get("schema")),
                metrics=[
                    ("Plans", _dict_value(summary, "plans")),
                    ("OK Plans", _dict_value(summary, "okPlans")),
                    ("Failed Plans", _dict_value(summary, "failedPlans")),
                    ("Artifacts", _dict_value(summary, "artifacts")),
                    ("Bytes", _dict_value(summary, "bytes")),
                    ("Failures", _dict_value(summary, "failures")),
                    ("Triage Warn", _dict_value(summary, "triageWarn")),
                    ("Triage Fail", _dict_value(summary, "triageFail")),
                ],
            ),
            _rows_panel(
                "Plans",
                _submission_index_plan_rows(index.get("plans", [])),
                [
                    "schema",
                    "ok",
                    "mode",
                    "targetKind",
                    "targetEndpoint",
                    "artifacts",
                    "bytes",
                    "failures",
                    "triageStatus",
                    "path",
                ],
                test_id="submission-plan-index-panel",
            ),
            _rows_panel(
                "Failures",
                index.get("failures", []),
                ["code", "message", "path"],
                test_id="submission-index-failures-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def render_schema_index_report(index: dict[str, Any]) -> str:
    if index.get("schema") != "edgp.schema.index.v1":
        raise ValueError("HTML schema index input must be an EDGP schema index")

    schemas = index.get("schemas", [])
    if not isinstance(schemas, list):
        schemas = []
    return _document(
        "EDGP Schema Index",
        [
            _generic_hero(
                eyebrow="schema catalog",
                heading="EDGP JSON Schema index",
                schema=str(index.get("schema")),
                metrics=[
                    ("Schemas", index.get("schemaCount", len(schemas))),
                    ("Generated By", index.get("generatedBy", "")),
                ],
            ),
            _rows_panel(
                "Schema Groups",
                _schema_index_group_rows(schemas),
                ["group", "schemas"],
                test_id="schema-index-groups-panel",
            ),
            _rows_panel(
                "Schemas",
                _schema_index_rows(schemas),
                ["contract", "title", "file", "id", "jsonSchema", "description"],
                test_id="schema-index-schemas-panel",
            ),
        ],
        scripts=[_table_sort_script()],
    )


def _submission_artifact_rows(artifacts: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not isinstance(artifacts, list):
        return rows
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        rows.append(
            {
                "kind": artifact.get("format") or artifact.get("role") or "",
                "path": artifact.get("path", ""),
                "mediaType": artifact.get("mediaType", ""),
                "bytes": artifact.get("bytes", ""),
                "action": artifact.get("action", ""),
                "method": artifact.get("method", ""),
                "endpoint": artifact.get("endpoint", ""),
            }
        )
    return rows


def _submission_source_row(source: dict[str, object]) -> dict[str, object]:
    return {
        "inputType": source.get("inputType", ""),
        "path": source.get("path", ""),
        "manifest": source.get("manifest", ""),
        "manifestSha256": source.get("manifestSha256", ""),
        "bundleSha256": source.get("bundleSha256", ""),
        "archiveSha256": source.get("archiveSha256", ""),
    }


def _submission_index_plan_rows(plans: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not isinstance(plans, list):
        return rows
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        target = plan.get("target", {})
        if not isinstance(target, dict):
            target = {}
        rows.append(
            {
                "schema": plan.get("schema", ""),
                "ok": plan.get("ok", ""),
                "mode": plan.get("mode", ""),
                "targetKind": target.get("kind", ""),
                "targetEndpoint": target.get("endpoint", ""),
                "artifacts": plan.get("artifacts", ""),
                "bytes": plan.get("bytes", ""),
                "failures": plan.get("failures", ""),
                "triageStatus": plan.get("triageStatus", ""),
                "path": plan.get("path", ""),
            }
        )
    return rows


def _schema_index_rows(schemas: object) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not isinstance(schemas, list):
        return rows
    for schema in schemas:
        if not isinstance(schema, dict):
            continue
        rows.append(
            {
                "contract": schema.get("contract", ""),
                "title": schema.get("title", ""),
                "file": schema.get("file", ""),
                "id": schema.get("id", ""),
                "jsonSchema": schema.get("jsonSchema", ""),
                "description": schema.get("description", ""),
            }
        )
    return rows


def _schema_index_group_rows(schemas: object) -> list[dict[str, object]]:
    groups: dict[str, int] = {}
    if not isinstance(schemas, list):
        return []
    for schema in schemas:
        if not isinstance(schema, dict):
            continue
        group = _schema_index_group(str(schema.get("contract", "")))
        groups[group] = groups.get(group, 0) + 1
    return [
        {"group": group, "schemas": count}
        for group, count in sorted(groups.items())
    ]


def _schema_index_group(contract: str) -> str:
    parts = contract.split(".")
    if len(parts) >= 3 and parts[1] in {
        "export",
        "report",
        "submission",
        "validation",
    }:
        return ".".join(parts[1:3])
    if len(parts) >= 2 and parts[1]:
        return parts[1]
    return "uncontracted"


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
    row_attrs: Callable[[dict[str, Any]], Mapping[str, object]] | None = None,
) -> str:
    rendered_rows = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            attrs = _html_attrs(row_attrs(row)) if row_attrs is not None else ""
            rendered_rows.append(
                f"<tr{attrs}>"
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


def _html_attrs(attrs: Mapping[str, object]) -> str:
    rendered = []
    for key, value in attrs.items():
        if value is None:
            continue
        rendered.append(f' {escape(str(key))}="{escape(str(value))}"')
    return "".join(rendered)


def _cell(value: object) -> str:
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True)
    return str(value if value is not None else "")


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _dict_value(value: object, key: str) -> str:
    if isinstance(value, dict):
        return str(value.get(key, ""))
    return ""


def _humanize_label(key: str) -> str:
    label = key.replace("_", " ").replace("-", " ")
    label = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", label)
    return label.title()


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


def _graph_diff_tree_visual_panel(report: dict[str, Any]) -> str:
    nodes = report.get("nodes", {})
    edges = report.get("edges", {})
    if not isinstance(nodes, dict):
        nodes = {}
    if not isinstance(edges, dict):
        edges = {}
    status_by_node: dict[str, str] = {}
    label_by_node: dict[str, str] = {}
    for status in ("added", "removed"):
        raw_nodes = nodes.get(status, [])
        if not isinstance(raw_nodes, list):
            continue
        for raw_node in raw_nodes:
            if not isinstance(raw_node, dict):
                continue
            node_id = str(raw_node.get("id") or "")
            if not node_id:
                continue
            status_by_node[node_id] = status
            label_by_node[node_id] = str(raw_node.get("name") or node_id)
    changed_nodes = nodes.get("metadataChanged", [])
    if isinstance(changed_nodes, list):
        for raw_node in changed_nodes:
            if not isinstance(raw_node, dict):
                continue
            node_id = str(raw_node.get("id") or "")
            if node_id:
                status_by_node[node_id] = "changed"
                label_by_node.setdefault(node_id, node_id)
    unchanged_nodes = nodes.get("unchanged", [])
    if isinstance(unchanged_nodes, list):
        for raw_node in unchanged_nodes:
            node_id = str(raw_node)
            status_by_node.setdefault(node_id, "unchanged")
            label_by_node.setdefault(node_id, node_id)

    edge_entries: list[tuple[str, dict[str, Any]]] = []
    for status in ("removed", "unchanged", "added"):
        raw_edges = edges.get(status, [])
        if not isinstance(raw_edges, list):
            continue
        for edge in raw_edges:
            if not isinstance(edge, dict):
                continue
            edge_entries.append((status, edge))
            source = str(edge.get("source") or "")
            target = str(edge.get("target") or "")
            if source:
                status_by_node.setdefault(source, "unchanged")
                label_by_node.setdefault(source, source)
            if target:
                status_by_node.setdefault(target, "unchanged")
                label_by_node.setdefault(target, target)

    focus_nodes = {
        str(value)
        for value in (report.get("leftNode"), report.get("rightNode"))
        if isinstance(value, str) and value
    }
    for node_id in focus_nodes:
        status_by_node.setdefault(node_id, "unchanged")
        label_by_node.setdefault(node_id, node_id)

    visible_ids = _diff_tree_visible_node_ids(
        status_by_node,
        edge_entries,
        focus_nodes,
        direction=str(report.get("direction") or "dependencies"),
    )
    positions = _diff_tree_positions(visible_ids, edge_entries, focus_nodes, report)
    visible_edges = [
        (status, edge)
        for status, edge in edge_entries[:128]
        if str(edge.get("source") or "") in positions
        and str(edge.get("target") or "") in positions
    ]

    edge_markup = []
    for status, edge in visible_edges:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        x1, y1 = positions[source]
        x2, y2 = positions[target]
        edge_markup.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'class="diff-edge diff-edge-{escape(status)}" />'
        )

    node_markup = []
    for node_id in visible_ids:
        if node_id not in positions:
            continue
        x, y = positions[node_id]
        status = status_by_node.get(node_id, "unchanged")
        focus_class = " diff-node-focus" if node_id in focus_nodes else ""
        label = label_by_node.get(node_id, node_id)
        short_label = label if len(label) <= 22 else f"{label[:19]}..."
        node_markup.append(
            f'<g class="diff-node diff-node-{escape(status)}{focus_class}">'
            f"<title>{escape(node_id)}</title>"
            f'<circle cx="{x}" cy="{y}" r="14" />'
            f'<text x="{x}" y="{y + 31}">{escape(short_label)}</text>'
            "</g>"
        )

    legend = _diff_tree_legend()
    hidden_nodes = max(0, len(status_by_node) - len(visible_ids))
    hidden_edges = max(0, len(edge_entries) - len(visible_edges))
    budget_note = (
        f"{hidden_nodes} nodes / {hidden_edges} edges outside preview"
        if hidden_nodes or hidden_edges
        else "complete focused cone preview"
    )
    return f"""
<section class="panel" data-testid="graph-diff-tree-visual-panel" data-diff-tree-visual>
  <div class="section-head">
    <h2>Focused Graph Change</h2>
    <span>{escape(budget_note)}</span>
  </div>
  <svg viewBox="0 0 760 420" role="img" aria-label="Focused graph difference preview">
    <rect x="1" y="1" width="758" height="418" rx="8" class="svg-bg" />
    {"".join(edge_markup)}
    {"".join(node_markup)}
  </svg>
  {legend}
</section>""".strip()


def _graph_diff_tree_classification_panel(classifications: list[object]) -> str:
    rows = [
        item
        for item in classifications
        if isinstance(item, dict)
    ]
    return _rows_panel(
        "Change Classification",
        rows,
        [
            "kind",
            "name",
            "leftNode",
            "rightNode",
            "leftVersion",
            "rightVersion",
            "leftDistance",
            "rightDistance",
            "changedKeys",
        ],
        test_id="graph-diff-tree-classification-panel",
    )


def _graph_diff_tree_top_findings_panel(top_findings: dict[str, Any]) -> str:
    return _package_change_top_findings_panel(
        top_findings,
        test_id="graph-diff-tree-top-findings-panel",
    )


def _package_change_top_findings_panel(
    top_findings: dict[str, Any],
    *,
    test_id: str,
) -> str:
    package_changes = top_findings.get("packageChanges", [])
    rows = [item for item in package_changes if isinstance(item, dict)]
    return _rows_panel(
        "Top Package Changes",
        rows,
        [
            "kind",
            "name",
            "leftNode",
            "rightNode",
            "leftVersion",
            "rightVersion",
            "leftDistance",
            "rightDistance",
            "changedKeys",
        ],
        test_id=test_id,
    )


def _graph_diff_tree_policy_panel(policy: dict[str, Any]) -> str:
    if not policy:
        return ""
    return _rows_panel(
        "Diff Tree Policy",
        [policy],
        ["status", "exitCode", "failOnKind", "matchedKinds"],
        test_id="graph-diff-tree-policy-panel",
    )


def _graph_diff_tree_paths_panel(nodes: dict[str, Any]) -> str:
    rows: list[dict[str, Any]] = []
    for status in ("added", "removed"):
        raw_nodes = nodes.get(status, [])
        if not isinstance(raw_nodes, list):
            continue
        for raw_node in raw_nodes:
            if not isinstance(raw_node, dict):
                continue
            path = raw_node.get("path", [])
            if not isinstance(path, list) or not path:
                continue
            rows.append(
                {
                    "status": status,
                    "node": raw_node.get("id", ""),
                    "distance": raw_node.get("distance", ""),
                    "path": " -> ".join(str(item) for item in path),
                }
            )
    changed_nodes = nodes.get("metadataChanged", [])
    if isinstance(changed_nodes, list):
        for raw_node in changed_nodes:
            if not isinstance(raw_node, dict):
                continue
            for side in ("left", "right"):
                path = raw_node.get(f"{side}Path", [])
                if not isinstance(path, list) or not path:
                    continue
                rows.append(
                    {
                        "status": f"metadataChanged:{side}",
                        "node": raw_node.get("id", ""),
                        "distance": raw_node.get(f"{side}Distance", ""),
                        "path": " -> ".join(str(item) for item in path),
                    }
                )
    return _rows_panel(
        "Change Paths",
        rows,
        ["status", "node", "distance", "path"],
        test_id="graph-diff-tree-paths-panel",
    )


def _diff_tree_visible_node_ids(
    status_by_node: dict[str, str],
    edge_entries: list[tuple[str, dict[str, Any]]],
    focus_nodes: set[str],
    *,
    direction: str,
) -> list[str]:
    nodes = set(status_by_node)
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for _, edge in edge_entries:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if not source or not target:
            continue
        origin, neighbor = (source, target) if direction == "dependencies" else (target, source)
        adjacency.setdefault(origin, []).append(neighbor)
        adjacency.setdefault(neighbor, [])
    starts = sorted(focus_nodes & nodes) or sorted(nodes)[:1]
    ordered: list[str] = []
    seen: set[str] = set()
    queue: list[str] = starts[:]
    while queue and len(ordered) < 64:
        node_id = queue.pop(0)
        if node_id in seen:
            continue
        seen.add(node_id)
        ordered.append(node_id)
        queue.extend(sorted(neighbor for neighbor in adjacency.get(node_id, []) if neighbor not in seen))
    for node_id in sorted(nodes):
        if len(ordered) >= 64:
            break
        if node_id not in seen:
            ordered.append(node_id)
            seen.add(node_id)
    return ordered


def _diff_tree_positions(
    node_ids: list[str],
    edge_entries: list[tuple[str, dict[str, Any]]],
    focus_nodes: set[str],
    report: dict[str, Any],
) -> dict[str, tuple[int, int]]:
    if not node_ids:
        return {}
    direction = str(report.get("direction") or "dependencies")
    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
    node_set = set(node_ids)
    for _, edge in edge_entries:
        source = str(edge.get("source") or "")
        target = str(edge.get("target") or "")
        if source not in node_set or target not in node_set:
            continue
        origin, neighbor = (source, target) if direction == "dependencies" else (target, source)
        adjacency.setdefault(origin, []).append(neighbor)

    distances: dict[str, int] = {}
    queue: list[str] = []
    for node_id in sorted(focus_nodes & node_set):
        distances[node_id] = 0
        queue.append(node_id)
    if not queue:
        distances[node_ids[0]] = 0
        queue.append(node_ids[0])
    while queue:
        node_id = queue.pop(0)
        for neighbor in sorted(adjacency.get(node_id, [])):
            if neighbor in distances:
                continue
            distances[neighbor] = distances[node_id] + 1
            queue.append(neighbor)
    fallback_level = (max(distances.values()) if distances else 0) + 1
    levels: dict[int, list[str]] = {}
    for node_id in node_ids:
        levels.setdefault(distances.get(node_id, fallback_level), []).append(node_id)

    max_level = max(levels) if levels else 0
    x_span = 600
    x_start = 80
    positions: dict[str, tuple[int, int]] = {}
    for level, level_nodes in sorted(levels.items()):
        x = x_start + round((x_span * level) / max(1, max_level))
        count = len(level_nodes)
        for index, node_id in enumerate(level_nodes):
            y = 210 if count == 1 else 72 + round((276 * index) / max(1, count - 1))
            positions[node_id] = (x, y)
    return positions


def _diff_tree_legend() -> str:
    items = [
        ("added", "Added"),
        ("removed", "Removed"),
        ("changed", "Metadata Changed"),
        ("unchanged", "Unchanged"),
        ("focus", "Selected Node"),
    ]
    rows = "".join(
        '<li>'
        f'<span class="diff-legend-swatch diff-legend-{escape(status)}"></span>'
        f"<strong>{escape(label)}</strong>"
        "</li>"
        for status, label in items
    )
    return f'<ul class="diff-legend" aria-label="Graph diff legend">{rows}</ul>'


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


def _bundle_catalog_filter_script() -> str:
    return """
(() => {
  const queryParam = "catalogQuery";
  const sourceParam = "catalogSource";
  const statusParam = "catalogStatus";
  const problemsParam = "catalogProblems";
  const panel = document.querySelector("[data-bundle-catalog-filter-panel]");
  const bundlePanel = document.querySelector('[data-testid="bundle-catalog-bundles-panel"]');
  if (!panel || !bundlePanel) return;
  const search = panel.querySelector("[data-bundle-catalog-search]");
  const source = panel.querySelector("[data-bundle-catalog-source]");
  const status = panel.querySelector("[data-bundle-catalog-status]");
  const problems = panel.querySelector("[data-bundle-catalog-problems]");
  const reset = panel.querySelector("[data-bundle-catalog-reset]");
  const count = panel.querySelector("[data-bundle-catalog-filter-count]");
  const rows = () => Array.from(bundlePanel.querySelectorAll("[data-bundle-catalog-row]"));
  const setSelectValue = (element, value) => {
    if (!value) return;
    const values = Array.from(element.options).map((option) => option.value);
    if (values.includes(value)) element.value = value;
  };
  const readUrlState = () => {
    const params = new URLSearchParams(window.location.search);
    search.value = params.get(queryParam) || "";
    setSelectValue(source, params.get(sourceParam));
    setSelectValue(status, params.get(statusParam));
    problems.checked = ["1", "true"].includes(
      (params.get(problemsParam) || "").toLowerCase(),
    );
  };
  const updateUrlState = () => {
    const url = new URL(window.location.href);
    const query = (search.value || "").trim();
    if (query) url.searchParams.set(queryParam, query);
    else url.searchParams.delete(queryParam);
    if (source.value) url.searchParams.set(sourceParam, source.value);
    else url.searchParams.delete(sourceParam);
    if (status.value) url.searchParams.set(statusParam, status.value);
    else url.searchParams.delete(statusParam);
    if (problems.checked) url.searchParams.set(problemsParam, "1");
    else url.searchParams.delete(problemsParam);
    window.history.replaceState({}, "", url);
  };
  const apply = (options = {}) => {
    const syncUrl = options.syncUrl !== false;
    const query = (search.value || "").trim().toLowerCase();
    const sourceKind = source.value;
    const triageStatus = status.value;
    let shown = 0;
    const allRows = rows();
    for (const row of allRows) {
      const textMatches = !query || (row.textContent || "").toLowerCase().includes(query);
      const sourceMatches = !sourceKind || row.dataset.sourceKind === sourceKind;
      const statusMatches = !triageStatus || row.dataset.triageStatus === triageStatus;
      const problemMatches = !problems.checked || row.dataset.bundleProblem === "true";
      const visible = textMatches && sourceMatches && statusMatches && problemMatches;
      row.hidden = !visible;
      if (visible) shown += 1;
    }
    count.textContent = `${shown} of ${allRows.length} rows`;
    if (syncUrl) updateUrlState();
  };
  search.addEventListener("input", () => apply());
  source.addEventListener("change", () => apply());
  status.addEventListener("change", () => apply());
  problems.addEventListener("change", () => apply());
  reset.addEventListener("click", () => {
    search.value = "";
    source.value = "";
    status.value = "";
    problems.checked = false;
    apply();
    search.focus();
  });
  bundlePanel.addEventListener("edgp:table-sorted", () => apply());
  readUrlState();
  apply({ syncUrl: false });
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
.diff-edge { stroke-width: 3; stroke-linecap: round; opacity: .78; }
.diff-edge-added { stroke: #2e7d5b; }
.diff-edge-removed { stroke: #b2413c; stroke-dasharray: 9 7; }
.diff-edge-unchanged { stroke: #78909c; stroke-width: 2; opacity: .5; }
.diff-node circle { stroke-width: 4; }
.diff-node-added circle { fill: #2e7d5b; }
.diff-node-removed circle { fill: #b2413c; }
.diff-node-changed circle { fill: var(--amber); }
.diff-node-unchanged circle { fill: #6f8793; }
.diff-node-focus circle { stroke: var(--ink); stroke-width: 5; }
.diff-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
}
.diff-legend li {
  display: flex;
  gap: 8px;
  align-items: center;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.diff-legend strong { font-size: 13px; }
.diff-legend-swatch {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  display: inline-block;
}
.diff-legend-added { background: #2e7d5b; }
.diff-legend-removed { background: #b2413c; }
.diff-legend-changed { background: var(--amber); }
.diff-legend-unchanged { background: #6f8793; }
.diff-legend-focus { background: #ffffff; border: 3px solid var(--ink); }
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
.bundle-catalog-filter-controls {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(160px, 220px) minmax(150px, 200px) minmax(150px, auto) auto;
  gap: 12px;
  align-items: end;
}
.bundle-catalog-filter-controls label {
  display: grid;
  gap: 6px;
  min-width: 0;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}
.bundle-catalog-filter-controls input[type="search"],
.bundle-catalog-filter-controls select {
  width: 100%;
  min-height: 42px;
  padding: 9px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #ffffff;
  color: var(--ink);
  font: inherit;
}
.bundle-catalog-filter-controls .checkbox-control {
  align-self: stretch;
  display: flex;
  gap: 8px;
  align-items: center;
  padding: 9px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
.bundle-catalog-filter-controls .checkbox-control input {
  width: 16px;
  height: 16px;
}
.bundle-catalog-filter-actions button {
  min-height: 42px;
  padding: 9px 14px;
  border: 1px solid var(--ink);
  border-radius: 8px;
  background: var(--ink);
  color: #ffffff;
  font: inherit;
  cursor: pointer;
}
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
  .bundle-catalog-filter-controls { grid-template-columns: 1fr; }
  .edge-types ul { grid-template-columns: 1fr; }
  h1 { font-size: 24px; }
}
""".strip()
