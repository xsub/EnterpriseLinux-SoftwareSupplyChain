"""HTML report tests for EDGP JSON analysis documents."""

import json
from pathlib import Path

import pytest

from src.output.html_report import render_report, render_snapshot_report, write_report_file


def test_render_snapshot_report_includes_summary_graph_and_tables() -> None:
    snapshot = json.loads(Path("tests/fixtures/snapshot-right.json").read_text())

    html = render_snapshot_report(snapshot)

    assert "<!doctype html>" in html
    assert "EDGP Snapshot Report - app==1.0.0" in html
    assert 'data-testid="graph-panel"' in html
    assert 'data-testid="edge-filter-panel"' in html
    assert 'data-edge-filter-search' in html
    assert 'data-edge-filter-count' in html
    assert 'data-edge-filter-more' in html
    assert 'data-edge-type="1"' in html
    assert "data-sortable-table" in html
    assert 'data-sort-index="0"' in html
    assert 'data-sort-type="number"' in html
    assert "lib==2.0.0" in html
    assert "Most Depended Upon" in html


def test_render_snapshot_report_labels_maven_relationship_types() -> None:
    snapshot = {
        "schema": "edgp.graph.snapshot.v1",
        "ecosystem": "maven",
        "root": "app==1.0.0",
        "stats": {"nodes": 3, "edges": 2},
        "nodes": [
            {"id": "app==1.0.0", "dependencies": [], "dependents": [], "metadata": {}},
            {
                "id": "optional==1.0.0",
                "dependencies": [],
                "dependents": [],
                "metadata": {"optional": "true"},
            },
            {
                "id": "omitted==1.0.0",
                "dependencies": [],
                "dependents": [],
                "metadata": {"omitted": "true"},
            },
        ],
        "edges": [
            {
                "source": "app==1.0.0",
                "target": "optional==1.0.0",
                "relationshipType": 2,
            },
            {
                "source": "app==1.0.0",
                "target": "omitted==1.0.0",
                "relationshipType": 3,
            },
        ],
        "rankings": {"mostDependedUpon": []},
    }

    html = render_snapshot_report(snapshot)

    assert 'data-testid="edge-relationship-panel"' in html
    assert 'data-testid="edge-filter-panel"' in html
    assert 'data-edge-type="2"' in html
    assert 'data-edge-type="3"' in html
    assert "2 - Maven Optional" in html
    assert "3 - Maven Omitted" in html


def test_render_snapshot_report_adds_edge_windowing_for_large_graphs() -> None:
    edges = [
        {
            "source": f"package-{index}==1.0.0",
            "target": f"package-{index + 1}==1.0.0",
            "relationshipType": 1,
        }
        for index in range(260)
    ]
    snapshot = {
        "schema": "edgp.graph.snapshot.v1",
        "ecosystem": "generic",
        "root": "large-graph",
        "stats": {"nodes": 261, "edges": len(edges)},
        "nodes": [],
        "edges": edges,
        "rankings": {"mostDependedUpon": []},
    }

    html = render_snapshot_report(snapshot)

    assert 'data-edge-page-size="250"' in html
    assert 'data-edge-filter-more' in html
    assert "${shown} of ${matched} shown" in html
    assert html.count("<tr data-edge-row") == 260


def test_write_snapshot_report_file_writes_html(tmp_path) -> None:
    output_path = tmp_path / "report.html"

    returned = write_report_file(
        Path("tests/fixtures/snapshot-right.json"),
        output_path,
    )

    assert returned == output_path
    assert output_path.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_render_report_supports_impact_json() -> None:
    report = json.loads(Path("tests/fixtures/impact-report.json").read_text())

    html = render_report(report)

    assert "EDGP Impact Report - left-pad==1.3.0" in html
    assert 'data-testid="impact-chains-panel"' in html
    assert "@scope/tool==2.1.0 -&gt; left-pad==1.3.0" in html


def test_render_report_supports_advisory_json() -> None:
    report = json.loads(Path("tests/fixtures/advisory-report.json").read_text())

    html = render_report(report)

    assert "EDGP Advisory Report - demo-app==1.0.0" in html
    assert 'data-testid="advisory-findings-panel"' in html
    assert "ADV-LOCAL-0001" in html


def test_render_report_supports_npm_diagnostics_json() -> None:
    report = json.loads(Path("tests/fixtures/npm-diagnostics-report.json").read_text())

    html = render_report(report)

    assert "EDGP npm Diagnostics - conflict-app==1.0.0" in html
    assert 'data-testid="npm-conflicts-panel"' in html
    assert "shared==2.0.0" in html
    assert "node_modules/tool/node_modules/shared" in html
    assert "missing" in html


def test_render_report_supports_albs_artifact_inventory_json() -> None:
    report = json.loads(Path("tests/fixtures/albs-artifact-inventory.json").read_text())

    html = render_report(report)

    assert "EDGP ALBS Artifact Inventory - albs-build:17812" in html
    assert 'data-testid="albs-arch-summary-panel"' in html
    assert 'data-testid="albs-artifact-table-panel"' in html
    assert "nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm" in html
    assert "data-sortable-table" in html


def test_render_report_supports_albs_build_timing_json() -> None:
    report = json.loads(Path("tests/fixtures/albs-build-timing.json").read_text())

    html = render_report(report)

    assert "EDGP ALBS Build Timing - albs-build:17812" in html
    assert 'data-testid="albs-task-timing-panel"' in html
    assert 'data-testid="albs-sign-timing-panel"' in html
    assert 'data-testid="albs-artifact-timing-panel"' in html
    assert "371.070048" in html


def test_render_report_supports_graph_diff_json() -> None:
    report = json.loads(Path("tests/fixtures/graph-diff.json").read_text())
    report["policy"] = {
        "exitCode": 2,
        "failOnChange": ["added-node"],
        "matchedChanges": ["added-node"],
        "status": "fail",
    }

    html = render_report(report)

    assert "EDGP Graph Diff" in html
    assert 'data-testid="graph-diff-policy-panel"' in html
    assert "Graph Diff Policy" in html
    assert 'data-testid="graph-diff-classification-panel"' in html
    assert 'data-testid="graph-diff-added-nodes-panel"' in html
    assert 'data-testid="graph-diff-added-edges-panel"' in html
    assert "upgrade" in html
    assert "core==1.0.0" in html


def test_render_report_supports_graph_diff_tree_json() -> None:
    report = json.loads(Path("tests/fixtures/graph-diff-tree.json").read_text())
    report["policy"] = {
        "exitCode": 2,
        "failOnKind": ["upgrade", "replacement"],
        "matchedKinds": ["upgrade"],
        "status": "fail",
    }

    html = render_report(report)

    assert "EDGP Graph Diff Tree" in html
    assert 'data-testid="graph-diff-tree-policy-panel"' in html
    assert "Diff Tree Policy" in html
    assert 'data-testid="graph-diff-tree-visual-panel"' in html
    assert 'data-testid="graph-diff-tree-classification-panel"' in html
    assert 'data-testid="graph-diff-tree-paths-panel"' in html
    assert 'class="diff-edge diff-edge-added"' in html
    assert 'class="diff-edge diff-edge-removed"' in html
    assert "Selected Node" in html
    assert "upgrade" in html
    assert "app==1.0.0 -&gt; lib==2.0.0 -&gt; core==1.0.0" in html
    assert 'data-testid="graph-diff-tree-added-nodes-panel"' in html
    assert 'data-testid="graph-diff-tree-added-edges-panel"' in html
    assert "lib==2.0.0" in html


def test_render_report_supports_query_report_json() -> None:
    report = json.loads(Path("tests/fixtures/query-report.json").read_text())

    html = render_report(report)

    assert "EDGP Query Report" in html
    assert 'data-testid="query-context-panel"' in html
    assert 'data-testid="query-result-panel"' in html
    assert "left-pad==1.3.0" in html


def test_render_report_supports_bundle_catalog_json() -> None:
    report = json.loads(Path("tests/fixtures/bundle-catalog.json").read_text())

    html = render_report(report)

    assert "EDGP Bundle Catalog" in html
    assert 'data-testid="bundle-catalog-bundles-panel"' in html
    assert 'data-testid="bundle-catalog-source-kinds-panel"' in html
    assert "Status" in html
    assert "fail" in html
    assert "Diff Tree Policies" in html
    assert "Diff Tree Policy Failures" in html
    assert "htmlDigestMismatch" in html


def test_render_report_supports_triage_diff_policy_findings() -> None:
    report = json.loads(Path("tests/fixtures/triage-summary.json").read_text())
    report["summary"]["graphDiffPolicyFailures"] = 1
    report["summary"]["diffTreePolicyFailures"] = 1
    report["checks"].append(
        {
            "kind": "graph-diff-policy",
            "status": "fail",
            "failOnChange": ["added-node"],
            "matchedChanges": ["added-node"],
            "exitCode": 2,
        }
    )
    report["checks"].append(
        {
            "kind": "diff-tree-policy",
            "status": "fail",
            "failOnKind": ["upgrade"],
            "matchedKinds": ["upgrade"],
            "exitCode": 2,
        }
    )
    report["topFindings"]["diffTreePolicies"] = [
        {
            "selector": "app",
            "direction": "dependencies",
            "depth": 2,
            "failOnKind": ["upgrade"],
            "matchedKinds": ["upgrade"],
            "exitCode": 2,
        }
    ]
    report["topFindings"]["graphDiffPolicies"] = [
        {
            "leftRoot": "app==1.0.0",
            "rightRoot": "app==1.0.0",
            "failOnChange": ["added-node"],
            "matchedChanges": ["added-node"],
            "exitCode": 2,
        }
    ]

    html = render_report(report)

    assert 'data-testid="triage-graph-diff-policy-panel"' in html
    assert "Graph Diff Policy Findings" in html
    assert 'data-testid="triage-diff-tree-policy-panel"' in html
    assert "Diff Tree Policy Findings" in html
    assert "upgrade" in html


def test_render_report_supports_validation_triage_policy_metrics() -> None:
    report = {
        "schema": "edgp.validation.report.v1",
        "target": "/tmp/reports/diff-tree",
        "targetType": "report-bundle",
        "contract": "edgp.report.bundle.v1",
        "ok": True,
        "summary": {"failures": 0},
        "failures": [],
        "reportStatus": "fail",
        "reportSummary": {
            "bundles": 1,
            "okBundles": 1,
            "failedBundles": 0,
            "failures": 0,
            "triageWarn": 0,
            "triageFail": 1,
            "diffTreePolicyFailures": 1,
        },
        "triageSummary": {
            "schema": "edgp.triage.summary.v1",
            "source": "triage-summary.json",
            "status": "fail",
            "summary": {
                "reports": 1,
                "failedChecks": 1,
                "diffTreePolicyFailures": 1,
                "advisoryFindings": 0,
                "deniedLicenseFindings": 0,
                "npmDuplicatePackageNames": 0,
                "npmNestedResolutionConflicts": 0,
                "npmUnresolvedDependencies": 0,
            },
        },
    }

    html = render_report(report)

    assert 'data-testid="validation-triage-panel"' in html
    assert 'data-testid="validation-report-summary-panel"' in html
    assert "diffTreePolicyFailures" in html
    assert "failedChecks" in html


@pytest.mark.parametrize(
    ("fixture", "test_id"),
    [
        ("tests/fixtures/albs-build-diff.json", "albs-build-diff-changed-panel"),
        ("tests/fixtures/rpm-albs-provenance.json", "rpm-albs-provenance-matches-panel"),
        (
            "tests/fixtures/rpm-repository-summary.json",
            "rpm-repository-architectures-panel",
        ),
        (
            "tests/fixtures/rpm-repository-diff.json",
            "rpm-repository-diff-changed-panel",
        ),
        ("tests/fixtures/albs-log-intelligence.json", "albs-log-intelligence-panel"),
        (
            "tests/fixtures/albs-release-completeness.json",
            "albs-release-completeness-panel",
        ),
        ("tests/fixtures/libsolv-bridge.json", "libsolv-commands-panel"),
        ("tests/fixtures/license-report.json", "license-denied-panel"),
        ("tests/fixtures/public-advisory-feed.json", "public-advisory-feed-panel"),
        ("tests/fixtures/performance-report.json", "performance-results-panel"),
        ("tests/fixtures/triage-summary.json", "triage-checks-panel"),
    ],
)
def test_render_report_supports_public_vertical_reports(
    fixture: str,
    test_id: str,
) -> None:
    report = json.loads(Path(fixture).read_text())

    html = render_report(report)

    assert "<!doctype html>" in html
    assert f'data-testid="{test_id}"' in html
    assert "data-sortable-table" in html
