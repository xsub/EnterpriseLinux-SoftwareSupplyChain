"""Triage summary tests for aggregating EDGP report artifacts."""

import json
from pathlib import Path

from src.cli import main
from src.triage_summary import build_triage_summary_from_paths


def test_triage_summary_from_report_paths_matches_fixture() -> None:
    report = build_triage_summary_from_paths(
        [
            Path("tests/fixtures/snapshot-right.json"),
            Path("tests/fixtures/advisory-report.json"),
            Path("tests/fixtures/license-report.json"),
            Path("tests/fixtures/npm-diagnostics-report.json"),
        ]
    )

    assert report == json.loads(
        Path("tests/fixtures/triage-summary.json").read_text(encoding="utf-8")
    )


def test_cli_triage_summary_from_inputs(capsys) -> None:
    assert (
        main(
            [
                "triage-summary",
                "--input",
                "tests/fixtures/snapshot-right.json",
                "--input",
                "tests/fixtures/advisory-report.json",
                "--input",
                "tests/fixtures/license-report.json",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.triage.summary.v1"
    assert payload["status"] == "fail"
    assert payload["summary"]["failedChecks"] == 2


def test_cli_triage_summary_from_bundle(tmp_path, capsys) -> None:
    output_dir = tmp_path / "sbom-bundle"

    assert (
        main(
            [
                "sbom-bundle",
                "--path",
                "tests/fixtures/sample-bom.json",
                "--deny-license",
                "WTFPL",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["triage-summary", "--bundle", str(output_dir)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema"] == "edgp.triage.summary.v1"
    assert payload["source"]["kind"] == "bundle"
    assert payload["bundle"]["sourceKind"] == "cyclonedx-sbom"
    assert payload["status"] == "fail"
    assert payload["summary"]["deniedLicenseFindings"] == 1


def test_cli_triage_summary_from_bundle_archive(tmp_path, capsys) -> None:
    output_dir = tmp_path / "report-bundle"
    archive_path = tmp_path / "report-bundle.tar.gz"

    assert (
        main(
            [
                "report-bundle",
                "--input",
                "tests/fixtures/snapshot-right.json",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "archive-bundle",
                "--path",
                str(output_dir),
                "--output",
                str(archive_path),
            ]
        )
        == 0
    )
    archive_report = json.loads(capsys.readouterr().out)

    assert main(["triage-summary", "--bundle", str(archive_path)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["schema"] == "edgp.triage.summary.v1"
    assert payload["source"]["kind"] == "bundle-archive"
    assert payload["source"]["archive"] == str(archive_path.resolve())
    assert payload["source"]["archiveSha256"] == archive_report["archiveSha256"]
    assert payload["source"]["bundleSha256"] == archive_report["bundleSha256"]
    assert payload["bundle"]["sourceKind"] == "edgp-json"
    assert payload["status"] == "warn"
    assert payload["summary"]["reports"] == 2
    assert payload["summary"]["graphSnapshots"] == 1
    assert payload["summary"]["npmDiagnosticsReports"] == 1
    assert payload["summary"]["npmUnresolvedDependencies"] == 1

    assert (
        main(
            [
                "triage-summary",
                "--bundle",
                str(archive_path),
                "--fail-on-status",
                "warn",
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["source"]["kind"] == "bundle-archive"


def test_cli_triage_summary_can_fail_on_status(capsys) -> None:
    assert (
        main(
            [
                "triage-summary",
                "--input",
                "tests/fixtures/advisory-report.json",
                "--fail-on-status",
                "fail",
            ]
        )
        == 2
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.triage.summary.v1"
    assert payload["status"] == "fail"


def test_cli_triage_summary_text_can_fail_on_status(tmp_path, capsys) -> None:
    diff_path = tmp_path / "graph-diff-policy.json"

    assert (
        main(
            [
                "diff",
                "--left",
                "tests/fixtures/snapshot-left.json",
                "--right",
                "tests/fixtures/snapshot-right.json",
                "--fail-on-change",
                "added-node",
            ]
        )
        == 2
    )
    diff_path.write_text(capsys.readouterr().out, encoding="utf-8")

    assert (
        main(
            [
                "triage-summary",
                "--input",
                str(diff_path),
                "--format",
                "text",
                "--fail-on-status",
                "fail",
            ]
        )
        == 2
    )

    assert capsys.readouterr().out.strip() == (
        "TRIAGE status=fail reports=1 failedChecks=1 "
        "graphDiffPolicyFailures=1"
    )


def test_cli_triage_summary_warn_threshold(capsys) -> None:
    assert (
        main(
            [
                "triage-summary",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--fail-on-status",
                "fail",
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "warn"

    assert (
        main(
            [
                "triage-summary",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--fail-on-status",
                "warn",
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["status"] == "warn"


def test_cli_triage_summary_text_reports_npm_signals(capsys) -> None:
    assert (
        main(
            [
                "triage-summary",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--format",
                "text",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out.strip() == (
        "TRIAGE status=warn reports=1 failedChecks=0 npmSignals=3"
    )


def test_triage_summary_fails_on_graph_diff_policy_gate(tmp_path, capsys) -> None:
    diff_path = tmp_path / "graph-diff-policy.json"

    assert (
        main(
            [
                "diff",
                "--left",
                "tests/fixtures/snapshot-left.json",
                "--right",
                "tests/fixtures/snapshot-right.json",
                "--fail-on-change",
                "added-node",
            ]
        )
        == 2
    )
    diff_path.write_text(capsys.readouterr().out, encoding="utf-8")

    assert (
        main(
            [
                "triage-summary",
                "--input",
                str(diff_path),
                "--fail-on-status",
                "fail",
            ]
        )
        == 2
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "fail"
    assert payload["summary"]["graphDiffReports"] == 1
    assert payload["summary"]["graphDiffPolicyFailures"] == 1
    assert payload["summary"]["failedChecks"] == 1
    assert payload["checks"] == [
        {
            "kind": "graph-diff-policy",
            "status": "fail",
            "failOnChange": ["added-node"],
            "matchedChanges": ["added-node"],
            "failOnKind": [],
            "matchedKinds": [],
            "exitCode": 2,
        }
    ]
    assert payload["topFindings"]["graphDiffPolicies"][0]["matchedChanges"] == [
        "added-node"
    ]
    assert payload["topFindings"]["graphDiffPolicies"][0]["matchedKinds"] == []


def test_triage_summary_fails_on_graph_diff_package_kind_gate(
    tmp_path,
    capsys,
) -> None:
    diff_path = tmp_path / "graph-diff-kind-policy.json"

    assert (
        main(
            [
                "diff",
                "--left",
                "tests/fixtures/snapshot-left.json",
                "--right",
                "tests/fixtures/snapshot-right.json",
                "--fail-on-kind",
                "upgrade",
            ]
        )
        == 2
    )
    diff_path.write_text(capsys.readouterr().out, encoding="utf-8")

    assert (
        main(
            [
                "triage-summary",
                "--input",
                str(diff_path),
                "--fail-on-status",
                "fail",
            ]
        )
        == 2
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "fail"
    assert payload["summary"]["graphDiffReports"] == 1
    assert payload["summary"]["graphDiffPolicyFailures"] == 1
    assert payload["summary"]["failedChecks"] == 1
    assert payload["checks"] == [
        {
            "kind": "graph-diff-policy",
            "status": "fail",
            "failOnChange": [],
            "matchedChanges": [],
            "failOnKind": ["upgrade"],
            "matchedKinds": ["upgrade"],
            "exitCode": 2,
        }
    ]
    assert payload["topFindings"]["graphDiffPolicies"][0]["matchedKinds"] == [
        "upgrade"
    ]


def test_triage_summary_fails_on_diff_tree_policy_gate(tmp_path, capsys) -> None:
    diff_tree_path = tmp_path / "graph-diff-tree-policy.json"

    assert (
        main(
            [
                "diff-tree",
                "--left",
                "tests/fixtures/snapshot-left.json",
                "--right",
                "tests/fixtures/snapshot-right.json",
                "--node",
                "app",
                "--depth",
                "2",
                "--fail-on-kind",
                "upgrade",
            ]
        )
        == 2
    )
    diff_tree_path.write_text(capsys.readouterr().out, encoding="utf-8")

    assert (
        main(
            [
                "triage-summary",
                "--input",
                str(diff_tree_path),
                "--fail-on-status",
                "fail",
            ]
        )
        == 2
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["status"] == "fail"
    assert payload["summary"]["diffTreeReports"] == 1
    assert payload["summary"]["diffTreePolicyFailures"] == 1
    assert payload["summary"]["diffTreeNodeChurn"] == 3
    assert payload["summary"]["diffTreeEdgeChurn"] == 3
    assert payload["summary"]["diffTreeNetNodeDelta"] == 1
    assert payload["summary"]["diffTreeNetEdgeDelta"] == 1
    assert payload["summary"]["failedChecks"] == 1
    assert payload["checks"] == [
        {
            "kind": "diff-tree-policy",
            "status": "fail",
            "failOnKind": ["upgrade"],
            "matchedKinds": ["upgrade"],
            "exitCode": 2,
        }
    ]
    assert payload["topFindings"]["diffTreePolicies"][0]["matchedKinds"] == [
        "upgrade"
    ]


def test_cli_triage_summary_text_reports_diff_tree_cone_rollup(
    tmp_path,
    capsys,
) -> None:
    diff_tree_path = tmp_path / "graph-diff-tree-policy.json"

    assert (
        main(
            [
                "diff-tree",
                "--left",
                "tests/fixtures/snapshot-left.json",
                "--right",
                "tests/fixtures/snapshot-right.json",
                "--node",
                "app",
                "--depth",
                "2",
                "--fail-on-kind",
                "upgrade",
            ]
        )
        == 2
    )
    diff_tree_path.write_text(capsys.readouterr().out, encoding="utf-8")

    assert (
        main(
            [
                "triage-summary",
                "--input",
                str(diff_tree_path),
                "--format",
                "text",
                "--fail-on-status",
                "fail",
            ]
        )
        == 2
    )

    assert capsys.readouterr().out.strip() == (
        "TRIAGE status=fail reports=1 failedChecks=1 "
        "diffTreePolicyFailures=1 diffTreeNodeChurn=3 "
        "diffTreeEdgeChurn=3 diffTreeNetNodeDelta=1 "
        "diffTreeNetEdgeDelta=1"
    )


def test_diff_tree_bundle_triage_summary_reflects_policy_gate(tmp_path, capsys) -> None:
    output_dir = tmp_path / "diff-tree-policy-bundle"

    assert (
        main(
            [
                "diff-tree-bundle",
                "--left",
                "tests/fixtures/snapshot-left.json",
                "--right",
                "tests/fixtures/snapshot-right.json",
                "--node",
                "app",
                "--depth",
                "2",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
                "--fail-on-kind",
                "upgrade",
            ]
        )
        == 2
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    triage = json.loads(
        (output_dir / "triage-summary.json").read_text(encoding="utf-8")
    )

    assert triage["status"] == "fail"
    assert triage["summary"]["diffTreePolicyFailures"] == 1
    assert triage["summary"]["diffTreeNodeChurn"] == 3
    assert triage["summary"]["diffTreeEdgeChurn"] == 3
    assert triage["summary"]["diffTreeNetNodeDelta"] == 1
    assert triage["summary"]["diffTreeNetEdgeDelta"] == 1
    assert triage["checks"][0]["kind"] == "diff-tree-policy"
    assert triage["checks"][0]["status"] == "fail"
    triage_html = (output_dir / "triage-summary.html").read_text(encoding="utf-8")
    assert 'data-testid="triage-diff-tree-policy-panel"' in triage_html
    assert "Diff Tree Node Churn" in triage_html


def test_graph_diff_bundle_triage_summary_reflects_package_kind_policy_gate(
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "graph-diff-kind-policy-bundle"

    assert (
        main(
            [
                "diff-bundle",
                "--left",
                "tests/fixtures/snapshot-left.json",
                "--right",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
                "--fail-on-kind",
                "upgrade",
            ]
        )
        == 2
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    triage = json.loads(
        (output_dir / "triage-summary.json").read_text(encoding="utf-8")
    )

    assert triage["status"] == "fail"
    assert triage["summary"]["graphDiffPolicyFailures"] == 1
    assert triage["checks"][0]["kind"] == "graph-diff-policy"
    assert triage["checks"][0]["failOnKind"] == ["upgrade"]
    assert triage["checks"][0]["matchedKinds"] == ["upgrade"]
    triage_html = (output_dir / "triage-summary.html").read_text(encoding="utf-8")
    assert 'data-testid="triage-graph-diff-policy-panel"' in triage_html
    assert "upgrade" in triage_html


def test_triage_summary_includes_bundle_catalog_failures() -> None:
    report = build_triage_summary_from_paths(
        [Path("tests/fixtures/bundle-catalog.json")]
    )

    assert report["status"] == "fail"
    assert report["summary"]["bundleCatalogReports"] == 1
    assert report["summary"]["catalogBundles"] == 2
    assert report["summary"]["catalogFailedBundles"] == 1
    assert report["summary"]["catalogFailures"] == 1
    assert report["summary"]["catalogTriageWarn"] == 1
    assert report["summary"]["failedChecks"] == 1
    assert report["checks"] == [
        {
            "kind": "bundle-catalog",
            "status": "fail",
            "failedBundles": 1,
            "failures": 1,
            "graphDiffPolicyFailures": 0,
            "diffTreePolicyFailures": 0,
            "realDataCoveragePolicyFailures": 0,
            "realDataCoverageDiffPolicyFailures": 0,
            "realDataReplacementPlanPolicyFailures": 0,
            "realDataReplacementPlanDiffPolicyFailures": 0,
            "triageWarn": 1,
            "triageFail": 0,
        }
    ]
    assert report["topFindings"]["bundleCatalog"][0]["diffTreePolicyFailures"] == 0
    assert report["topFindings"]["bundleCatalog"][0]["path"] == "/tmp/reports/tampered"


def test_triage_summary_rolls_up_catalog_diff_tree_policy_failures(tmp_path) -> None:
    catalog = json.loads(Path("tests/fixtures/bundle-catalog.json").read_text())
    catalog["summary"]["failedBundles"] = 0
    catalog["summary"]["failures"] = 0
    catalog["summary"]["triageWarn"] = 0
    catalog["summary"]["triageFail"] = 1
    catalog["summary"]["diffTreePolicyFailures"] = 1
    catalog["bundles"][0]["triageStatus"] = "fail"
    catalog["bundles"][0]["diffTreePolicyFailures"] = 1
    catalog["sourceKinds"][0]["triageFail"] = 1
    catalog["sourceKinds"][0]["diffTreePolicyFailures"] = 1
    path = tmp_path / "bundle-catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")

    report = build_triage_summary_from_paths([path])

    assert report["status"] == "fail"
    assert report["summary"]["diffTreePolicyFailures"] == 1
    assert report["summary"]["catalogTriageFail"] == 1
    assert report["checks"] == [
        {
            "kind": "bundle-catalog",
            "status": "fail",
            "failedBundles": 0,
            "failures": 0,
            "graphDiffPolicyFailures": 0,
            "diffTreePolicyFailures": 1,
            "realDataCoveragePolicyFailures": 0,
            "realDataCoverageDiffPolicyFailures": 0,
            "realDataReplacementPlanPolicyFailures": 0,
            "realDataReplacementPlanDiffPolicyFailures": 0,
            "triageWarn": 0,
            "triageFail": 1,
        }
    ]
    assert report["topFindings"]["bundleCatalog"][0]["diffTreePolicyFailures"] == 1


def test_triage_summary_rolls_up_catalog_real_data_policy_failures(tmp_path) -> None:
    catalog = json.loads(Path("tests/fixtures/bundle-catalog.json").read_text())
    catalog["summary"]["failedBundles"] = 0
    catalog["summary"]["failures"] = 0
    catalog["summary"]["triageWarn"] = 0
    catalog["summary"]["triageFail"] = 1
    catalog["summary"]["realDataCoveragePolicyFailures"] = 1
    catalog["summary"]["realDataCoverageDiffPolicyFailures"] = 1
    catalog["bundles"][0]["triageStatus"] = "fail"
    catalog["bundles"][0]["realDataCoveragePolicyFailures"] = 1
    catalog["bundles"][0]["realDataCoverageDiffPolicyFailures"] = 1
    catalog["bundles"][0]["realDataCoverageFailureCodes"] = [
        "replacementPriorityMatched"
    ]
    catalog["bundles"][0]["realDataCoverageDiffFailureCodes"] = [
        "publicEvidenceCoverageDecreased"
    ]
    catalog["sourceKinds"][0]["triageFail"] = 1
    catalog["sourceKinds"][0]["realDataCoveragePolicyFailures"] = 1
    catalog["sourceKinds"][0]["realDataCoverageDiffPolicyFailures"] = 1
    path = tmp_path / "bundle-catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")

    report = build_triage_summary_from_paths([path])

    assert report["status"] == "fail"
    assert report["summary"]["realDataCoveragePolicyFailures"] == 1
    assert report["summary"]["realDataCoverageDiffPolicyFailures"] == 1
    assert report["summary"]["catalogTriageFail"] == 1
    assert report["checks"] == [
        {
            "kind": "bundle-catalog",
            "status": "fail",
            "failedBundles": 0,
            "failures": 0,
            "graphDiffPolicyFailures": 0,
            "diffTreePolicyFailures": 0,
            "realDataCoveragePolicyFailures": 1,
            "realDataCoverageDiffPolicyFailures": 1,
            "realDataReplacementPlanPolicyFailures": 0,
            "realDataReplacementPlanDiffPolicyFailures": 0,
            "triageWarn": 0,
            "triageFail": 1,
        }
    ]
    finding = report["topFindings"]["bundleCatalog"][0]
    assert finding["realDataCoveragePolicyFailures"] == 1
    assert finding["realDataCoverageDiffPolicyFailures"] == 1
    assert finding["realDataCoverageFailureCodes"] == ["replacementPriorityMatched"]
    assert finding["realDataCoverageDiffFailureCodes"] == [
        "publicEvidenceCoverageDecreased"
    ]


def test_triage_summary_rolls_up_catalog_replacement_plan_policy_failures(
    tmp_path,
) -> None:
    catalog = json.loads(Path("tests/fixtures/bundle-catalog.json").read_text())
    catalog["summary"]["failedBundles"] = 0
    catalog["summary"]["failures"] = 0
    catalog["summary"]["triageWarn"] = 0
    catalog["summary"]["triageFail"] = 1
    catalog["summary"]["realDataReplacementPlanPolicyFailures"] = 1
    catalog["summary"]["realDataReplacementPlanDiffPolicyFailures"] = 1
    catalog["bundles"][0]["triageStatus"] = "fail"
    catalog["bundles"][0]["realDataReplacementPlanPolicyFailures"] = 1
    catalog["bundles"][0]["realDataReplacementPlanDiffPolicyFailures"] = 1
    catalog["bundles"][0]["realDataReplacementPlanFailureCodes"] = [
        "replacementPlanPriorityMatched"
    ]
    catalog["bundles"][0]["realDataReplacementPlanDiffFailureCodes"] = [
        "replacementCandidatesIncreased"
    ]
    catalog["sourceKinds"][0]["triageFail"] = 1
    catalog["sourceKinds"][0]["realDataReplacementPlanPolicyFailures"] = 1
    catalog["sourceKinds"][0]["realDataReplacementPlanDiffPolicyFailures"] = 1
    path = tmp_path / "bundle-catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")

    report = build_triage_summary_from_paths([path])

    assert report["status"] == "fail"
    assert report["summary"]["realDataReplacementPlanPolicyFailures"] == 1
    assert report["summary"]["realDataReplacementPlanDiffPolicyFailures"] == 1
    assert report["summary"]["catalogTriageFail"] == 1
    assert report["checks"] == [
        {
            "kind": "bundle-catalog",
            "status": "fail",
            "failedBundles": 0,
            "failures": 0,
            "graphDiffPolicyFailures": 0,
            "diffTreePolicyFailures": 0,
            "realDataCoveragePolicyFailures": 0,
            "realDataCoverageDiffPolicyFailures": 0,
            "realDataReplacementPlanPolicyFailures": 1,
            "realDataReplacementPlanDiffPolicyFailures": 1,
            "triageWarn": 0,
            "triageFail": 1,
        }
    ]
    finding = report["topFindings"]["bundleCatalog"][0]
    assert finding["realDataReplacementPlanPolicyFailures"] == 1
    assert finding["realDataReplacementPlanDiffPolicyFailures"] == 1
    assert finding["realDataReplacementPlanFailureCodes"] == [
        "replacementPlanPriorityMatched"
    ]
    assert finding["realDataReplacementPlanDiffFailureCodes"] == [
        "replacementCandidatesIncreased"
    ]


def test_triage_summary_preserves_catalog_policy_detail_findings(tmp_path) -> None:
    catalog = json.loads(Path("tests/fixtures/bundle-catalog.json").read_text())
    catalog["summary"]["failedBundles"] = 0
    catalog["summary"]["failures"] = 0
    catalog["summary"]["triageWarn"] = 0
    catalog["summary"]["triageFail"] = 1
    catalog["summary"]["graphDiffPolicyFailures"] = 1
    catalog["summary"]["diffTreePolicyFailures"] = 1
    catalog["bundles"][0]["triageStatus"] = "fail"
    catalog["bundles"][0]["graphDiffPolicyFailures"] = 1
    catalog["bundles"][0]["diffTreePolicyFailures"] = 1
    catalog["bundles"][0]["graphDiffFailOnChanges"] = ["added-node"]
    catalog["bundles"][0]["graphDiffMatchedChanges"] = ["added-node"]
    catalog["bundles"][0]["graphDiffFailOnKinds"] = ["upgrade"]
    catalog["bundles"][0]["graphDiffMatchedKinds"] = ["upgrade"]
    catalog["bundles"][0]["diffTreeFailOnKinds"] = ["replacement"]
    catalog["bundles"][0]["diffTreeMatchedKinds"] = ["replacement"]
    path = tmp_path / "bundle-catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")

    report = build_triage_summary_from_paths([path])

    finding = report["topFindings"]["bundleCatalog"][0]
    assert finding["graphDiffFailOnChanges"] == ["added-node"]
    assert finding["graphDiffMatchedChanges"] == ["added-node"]
    assert finding["graphDiffFailOnKinds"] == ["upgrade"]
    assert finding["graphDiffMatchedKinds"] == ["upgrade"]
    assert finding["diffTreeFailOnKinds"] == ["replacement"]
    assert finding["diffTreeMatchedKinds"] == ["replacement"]


def test_triage_summary_warns_on_catalog_underlying_warns(tmp_path, capsys) -> None:
    graph_bundle = tmp_path / "graph-bundle"
    diagnostics_bundle = tmp_path / "diagnostics-bundle"
    catalog_dir = tmp_path / "catalog"

    assert (
        main(
            [
                "report-bundle",
                "--input",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(graph_bundle),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "npm-diagnostics-bundle",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
                "--output-dir",
                str(diagnostics_bundle),
                "--triage-summary",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "bundle-catalog",
                "--bundle",
                str(graph_bundle),
                "--bundle",
                str(diagnostics_bundle),
                "--output-dir",
                str(catalog_dir),
                "--fail-on-status",
                "warn",
            ]
        )
        == 2
    )

    assert Path(capsys.readouterr().out.strip()) == catalog_dir / "index.html"
    triage = json.loads((catalog_dir / "triage-summary.json").read_text(encoding="utf-8"))
    assert triage["status"] == "warn"
    assert triage["summary"]["catalogTriageWarn"] == 1
    assert triage["checks"][0]["kind"] == "bundle-catalog"
    assert triage["checks"][0]["status"] == "warn"
