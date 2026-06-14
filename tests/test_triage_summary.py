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
            "triageWarn": 1,
            "triageFail": 0,
        }
    ]
    assert report["topFindings"]["bundleCatalog"][0]["path"] == "/tmp/reports/tampered"


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
