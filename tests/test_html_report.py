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
    report["topFindings"] = {
        "packageChanges": [
            {
                "kind": "upgrade",
                "name": "lib",
                "leftNode": "lib==1.0.0",
                "rightNode": "lib==2.0.0",
                "leftVersion": "1.0.0",
                "rightVersion": "2.0.0",
            }
        ]
    }

    html = render_report(report)

    assert "EDGP Graph Diff" in html
    assert 'data-testid="graph-diff-policy-panel"' in html
    assert 'data-testid="graph-diff-top-findings-panel"' in html
    assert 'data-testid="graph-diff-filter-panel"' in html
    assert "Graph Diff Policy" in html
    assert "Top Package Changes" in html
    assert 'data-testid="graph-diff-classification-panel"' in html
    assert 'data-graph-diff-search' in html
    assert 'data-graph-diff-kind' in html
    assert 'data-graph-diff-reset' in html
    assert 'data-graph-diff-row="true"' in html
    assert 'data-change-kind="upgrade"' in html
    assert "graphDiffQuery" in html
    assert "graphDiffKind" in html
    assert "window.history.replaceState" in html
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
    report["topFindings"] = {
        "packageChanges": [
            {
                "kind": "upgrade",
                "name": "lib",
                "leftNode": "lib==1.0.0",
                "rightNode": "lib==2.0.0",
                "leftVersion": "1.0.0",
                "rightVersion": "2.0.0",
            }
        ]
    }

    html = render_report(report)

    assert "EDGP Graph Diff Tree" in html
    assert 'data-testid="graph-diff-tree-policy-panel"' in html
    assert "Diff Tree Policy" in html
    assert 'data-testid="graph-diff-tree-visual-panel"' in html
    assert 'data-testid="graph-diff-tree-shape-panel"' in html
    assert "Focused Cone Shape" in html
    assert 'data-testid="graph-diff-tree-top-findings-panel"' in html
    assert 'data-testid="graph-diff-tree-filter-panel"' in html
    assert 'data-testid="graph-diff-tree-classification-panel"' in html
    assert 'data-graph-diff-tree-search' in html
    assert 'data-graph-diff-tree-kind' in html
    assert 'data-graph-diff-tree-reset' in html
    assert 'data-graph-diff-tree-row="true"' in html
    assert 'data-change-kind="upgrade"' in html
    assert "graphDiffTreeQuery" in html
    assert "graphDiffTreeKind" in html
    assert "window.history.replaceState" in html
    assert 'data-testid="graph-diff-tree-paths-panel"' in html
    assert "Top Package Changes" in html
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
    report["bundles"][0]["graphDiffMatchedKinds"] = ["upgrade"]
    report["bundles"][0]["graphDiffMatchedChanges"] = ["added-node"]
    report["bundles"][0]["diffTreeMatchedKinds"] = ["replacement"]

    html = render_report(report)

    assert "EDGP Bundle Catalog" in html
    assert 'data-testid="bundle-catalog-filter-panel"' in html
    assert 'data-testid="bundle-catalog-bundles-panel"' in html
    assert 'data-testid="bundle-catalog-source-kinds-panel"' in html
    assert 'data-bundle-catalog-search' in html
    assert 'data-bundle-catalog-source' in html
    assert 'data-bundle-catalog-status' in html
    assert 'data-bundle-catalog-problems' in html
    assert 'data-bundle-catalog-reset' in html
    assert 'data-bundle-catalog-row="true"' in html
    assert "catalogQuery" in html
    assert "catalogSource" in html
    assert "catalogStatus" in html
    assert "catalogProblems" in html
    assert "window.history.replaceState" in html
    assert 'data-source-kind="edgp-json"' in html
    assert 'data-source-kind="npm-diagnostics"' in html
    assert 'data-triage-status="warn"' in html
    assert 'data-bundle-problem="true"' in html
    assert 'data-bundle-problem="false"' in html
    assert "Status" in html
    assert "fail" in html
    assert "Diff Tree Policies" in html
    assert "Diff Tree Policy Failures" in html
    assert "Diff Tree Node Churn" in html
    assert "Diff Tree Edge Churn" in html
    assert "Diff Tree Net Node Delta" in html
    assert "Diff Tree Net Edge Delta" in html
    assert "Real-Data Policies" in html
    assert "Real Data Coverage Policy Failures" in html
    assert "Real Data Coverage Diff Policy Failures" in html
    assert "Replacement Plan Policies" in html
    assert "Real Data Replacement Plan Policy Failures" in html
    assert "Real Data Replacement Plan Diff Policy Failures" in html
    assert "htmlDigestMismatch" in html
    assert "upgrade" in html
    assert "added-node" in html
    assert "replacement" in html


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
            "failOnKind": ["upgrade"],
            "matchedKinds": ["upgrade"],
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
            "failOnKind": ["upgrade"],
            "matchedKinds": ["upgrade"],
            "exitCode": 2,
        }
    ]

    html = render_report(report)

    assert 'data-testid="triage-graph-diff-policy-panel"' in html
    assert "Graph Diff Policy Findings" in html
    assert 'data-testid="triage-diff-tree-policy-panel"' in html
    assert "Diff Tree Policy Findings" in html
    assert "added-node" in html
    assert "upgrade" in html


def test_render_report_supports_triage_bundle_catalog_policy_details() -> None:
    report = json.loads(Path("tests/fixtures/triage-summary.json").read_text())
    report["topFindings"]["bundleCatalog"] = [
        {
            "path": "/tmp/reports/cataloged-diff",
            "sourceKind": "graph-diff",
            "ok": True,
            "failureCount": 0,
            "failureCodes": [],
            "triageStatus": "fail",
            "graphDiffPolicyFailures": 1,
            "diffTreePolicyFailures": 1,
            "realDataCoveragePolicyFailures": 1,
            "realDataCoverageDiffPolicyFailures": 1,
            "realDataReplacementPlanPolicyFailures": 1,
            "realDataReplacementPlanDiffPolicyFailures": 1,
            "realDataCoverageFailureCodes": ["replacementPriorityMatched"],
            "realDataCoverageDiffFailureCodes": [
                "publicEvidenceCoverageDecreased"
            ],
            "realDataReplacementPlanFailureCodes": [
                "replacementPlanPriorityMatched"
            ],
            "realDataReplacementPlanDiffFailureCodes": [
                "replacementCandidatesIncreased"
            ],
            "graphDiffMatchedChanges": ["added-node"],
            "graphDiffMatchedKinds": ["upgrade"],
            "diffTreeMatchedKinds": ["replacement"],
        }
    ]

    html = render_report(report)

    assert 'data-testid="triage-bundle-catalog-panel"' in html
    assert "cataloged-diff" in html
    assert "added-node" in html
    assert "upgrade" in html
    assert "replacement" in html
    assert "Real Data Coverage Policy Failures" in html
    assert "Real Data Coverage Diff Policy Failures" in html
    assert "Real Data Replacement Plan Policy Failures" in html
    assert "Real Data Replacement Plan Diff Policy Failures" in html
    assert "replacementPriorityMatched" in html
    assert "publicEvidenceCoverageDecreased" in html
    assert "replacementPlanPriorityMatched" in html
    assert "replacementCandidatesIncreased" in html


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
            "topFindings": {
                "diffTreePolicies": [
                    {
                        "selector": "app",
                        "direction": "dependencies",
                        "depth": 2,
                        "matchedKinds": ["upgrade"],
                    }
                ]
            },
        },
        "reportTopFindings": {
            "bundleCatalog": [
                {
                    "path": "/tmp/reports/cataloged-diff",
                    "sourceKind": "graph-diff",
                    "triageStatus": "fail",
                    "graphDiffMatchedKinds": ["upgrade"],
                }
            ]
        },
    }

    html = render_report(report)

    assert 'data-testid="validation-triage-panel"' in html
    assert 'data-testid="validation-report-summary-panel"' in html
    assert 'data-testid="validation-triage-top-findings-panel"' in html
    assert 'data-testid="validation-report-top-findings-panel"' in html
    assert "diffTreePolicyFailures" in html
    assert "failedChecks" in html
    assert "cataloged-diff" in html
    assert "upgrade" in html


def test_render_report_supports_csr_artifact_validation_summary() -> None:
    report = {
        "schema": "edgp.validation.report.v1",
        "target": "/tmp/artifacts/csr",
        "targetType": "csr-artifact",
        "contract": "edgp.csr.artifact.v1",
        "ok": True,
        "summary": {"failures": 0},
        "failures": [],
        "csrArtifact": {
            "nodes": 3,
            "edges": 2,
            "matrixViews": {
                "csr": {
                    "format": "csr",
                    "direction": "outgoing_dependencies",
                    "values": "values",
                    "indices": "column_indices",
                    "indptr": "row_pointers",
                },
                "csc": {
                    "format": "csc",
                    "direction": "incoming_dependents",
                    "values": "reverse_values",
                    "indices": "reverse_column_indices",
                    "indptr": "reverse_row_pointers",
                    "materialization": "reverse_csr_transpose",
                },
            },
            "storageProfile": {
                "layout": "numpy.int32.c_contiguous",
                "dtype": "int32",
                "memoryMapped": True,
                "readOnly": True,
                "totalBytes": 64,
            },
        },
    }

    html = render_report(report)

    assert 'data-testid="validation-csr-artifact-panel"' in html
    assert "outgoing_dependencies" in html
    assert "incoming_dependents" in html
    assert "reverse_csr_transpose" in html
    assert "numpy.int32.c_contiguous" in html


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
        ("tests/fixtures/fixture-provenance.json", "fixture-provenance-entries-panel"),
        ("tests/fixtures/real-data-coverage.json", "real-data-coverage-plan-panel"),
        (
            "tests/fixtures/real-data-replacement-plan.json",
            "real-data-replacement-plan-candidates-panel",
        ),
        (
            "tests/fixtures/real-data-replacement-plan-diff.json",
            "real-data-replacement-plan-diff-sides-panel",
        ),
        (
            "tests/fixtures/real-data-coverage-diff.json",
            "real-data-coverage-diff-sides-panel",
        ),
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


def test_render_report_supports_albs_build_diff_top_findings() -> None:
    report = json.loads(Path("tests/fixtures/albs-build-diff.json").read_text())
    report["topFindings"] = {
        "changedArtifacts": [
            {
                "packageName": "nginx",
                "artifactArch": "x86_64",
                "buildArch": "x86_64",
                "changedFields": ["release", "casHash"],
            }
        ],
        "addedArtifacts": [
            {
                "filename": "nginx-mod-stream-1.20.1-16.el9_4.2.x86_64.rpm",
                "packageName": "nginx-mod-stream",
                "artifactArch": "x86_64",
                "buildArch": "x86_64",
            }
        ],
        "removedArtifacts": [
            {
                "filename": "nginx-1.20.1-16.el9_4.1.x86_64.rpm",
                "packageName": "nginx",
                "artifactArch": "x86_64",
                "buildArch": "x86_64",
            }
        ],
        "missingBuildArchitectures": [{"side": "left", "arch": "aarch64"}],
        "timingDeltas": [
            {
                "metric": "criticalBuildTaskWallSeconds",
                "left": 371.070048,
                "right": 424.070048,
                "delta": 53.0,
            }
        ],
        "gitCommitChanges": [{"left": ["old"], "right": ["new"]}],
    }

    html = render_report(report)

    assert 'data-testid="albs-build-diff-top-findings-panel"' in html
    assert "Top Build Changes" in html
    assert "gitCommitChange" in html


def test_render_report_supports_rpm_repository_diff_top_findings() -> None:
    report = json.loads(Path("tests/fixtures/rpm-repository-diff.json").read_text())
    report["topFindings"] = {
        "changedPackages": [
            {
                "name": "nginx",
                "arch": "x86_64",
                "changedFields": ["version", "release", "sourceRpm"],
            }
        ],
        "addedPackages": [
            {
                "name": "nginx-filesystem",
                "version": "1.26.3",
                "release": "9.module_el9.8.0+247+aa936373",
                "arch": "noarch",
                "sourceRpm": "nginx-1.26.3-9.module_el9.8.0+247+aa936373.src.rpm",
            }
        ],
        "removedPackages": [
            {
                "name": "nginx-core",
                "version": "1.20.1",
                "release": "28.el9_8.2.alma.1",
                "arch": "x86_64",
                "sourceRpm": "nginx-1.20.1-28.el9_8.2.alma.1.src.rpm",
            }
        ],
        "sourceRpmDelta": [
            {
                "status": "added",
                "sourceRpm": "nginx-1.26.3-9.module_el9.8.0+247+aa936373.src.rpm",
            }
        ],
    }

    html = render_report(report)

    assert 'data-testid="rpm-repository-diff-top-findings-panel"' in html
    assert "Top Repository Changes" in html
    assert "sourceRpmDelta" in html
