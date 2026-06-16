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
            "exitCode": 2,
        }
    ]
    assert payload["topFindings"]["graphDiffPolicies"][0]["matchedChanges"] == [
        "added-node"
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
    assert triage["checks"][0]["kind"] == "diff-tree-policy"
    assert triage["checks"][0]["status"] == "fail"
    triage_html = (output_dir / "triage-summary.html").read_text(encoding="utf-8")
    assert 'data-testid="triage-diff-tree-policy-panel"' in triage_html


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
            "triageWarn": 0,
            "triageFail": 1,
        }
    ]
    assert report["topFindings"]["bundleCatalog"][0]["diffTreePolicyFailures"] == 1


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
