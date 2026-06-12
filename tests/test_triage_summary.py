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
