"""Real-data coverage diff report tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path

from src.cli import main as cli_main
from src.output.html_report import render_report
from src.real_data_coverage_diff import build_real_data_coverage_diff_report
from src.schema_validation import validate_target


COVERAGE_FIXTURE_PATH = Path("tests/fixtures/real-data-coverage.json")
DIFF_FIXTURE_PATH = Path("tests/fixtures/real-data-coverage-diff.json")


def _coverage_fixture() -> dict:
    return json.loads(COVERAGE_FIXTURE_PATH.read_text(encoding="utf-8"))


def _diff_fixture() -> dict:
    return json.loads(DIFF_FIXTURE_PATH.read_text(encoding="utf-8"))


def _regressed_coverage_fixture() -> dict:
    report = copy.deepcopy(_coverage_fixture())
    removed = report["publicEvidence"].pop()
    summary = report["summary"]
    summary["publicEvidenceFiles"] = len(report["publicEvidence"])
    summary["publicEvidenceCoveragePercent"] = round(
        summary["publicEvidenceFiles"] / summary["catalogedFiles"] * 100,
        2,
    )
    if removed.get("kind") == "generated-public-report":
        summary["generatedPublicReports"] -= 1
    return report


def test_real_data_coverage_diff_fixture_matches_generator() -> None:
    coverage = _coverage_fixture()
    expected = build_real_data_coverage_diff_report(
        coverage,
        coverage,
        left_label="baseline",
        right_label="current",
    )

    assert _diff_fixture() == expected


def test_real_data_coverage_diff_documents_stable_baseline() -> None:
    report = _diff_fixture()

    assert report["status"] == "pass"
    assert report["left"]["label"] == "baseline"
    assert report["right"]["label"] == "current"
    assert report["summary"]["publicEvidenceCoveragePercentDelta"] == 0.0
    assert report["summary"]["publicEvidenceFilesDelta"] == 0
    assert report["summary"]["regressions"] == 0
    assert report["regressions"] == []


def test_real_data_coverage_diff_validates_against_schema() -> None:
    report = validate_target(DIFF_FIXTURE_PATH)

    assert report["ok"] is True
    assert report["contract"] == "edgp.real_data.coverage_diff.v1"
    assert report["reportStatus"] == "pass"


def test_real_data_coverage_diff_renders_static_html() -> None:
    html = render_report(_diff_fixture())

    assert "<!doctype html>" in html
    assert 'data-testid="real-data-coverage-diff-sides-panel"' in html
    assert 'data-testid="real-data-coverage-diff-plan-panel"' in html
    assert "Real-data coverage trend" in html


def test_real_data_coverage_diff_policy_detects_regression() -> None:
    report = build_real_data_coverage_diff_report(
        _coverage_fixture(),
        _regressed_coverage_fixture(),
        left_label="baseline",
        right_label="current",
        fail_on_regression=True,
    )

    assert report["status"] == "fail"
    assert report["summary"]["regressions"] >= 1
    assert report["policy"]["status"] == "fail"
    assert report["policy"]["exitCode"] == 2
    assert report["policy"]["failures"][0]["code"] == (
        "publicEvidenceCoverageDecreased"
    )


def test_cli_real_data_coverage_diff_outputs_current_baseline(capsys) -> None:
    assert (
        cli_main(
            [
                "real-data-coverage-diff",
                "--left",
                str(COVERAGE_FIXTURE_PATH),
                "--right",
                str(COVERAGE_FIXTURE_PATH),
                "--left-label",
                "baseline",
                "--right-label",
                "current",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == _diff_fixture()
    assert payload["schema"] == "edgp.real_data.coverage_diff.v1"


def test_cli_real_data_coverage_diff_returns_two_on_regression(
    tmp_path,
    capsys,
) -> None:
    right_path = tmp_path / "real-data-coverage-regressed.json"
    right_path.write_text(json.dumps(_regressed_coverage_fixture()), encoding="utf-8")

    assert (
        cli_main(
            [
                "real-data-coverage-diff",
                "--left",
                str(COVERAGE_FIXTURE_PATH),
                "--right",
                str(right_path),
                "--fail-on-regression",
            ]
        )
        == 2
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "fail"
    assert payload["policy"]["status"] == "fail"
    assert payload["summary"]["removedPublicEvidence"] == 1


def test_cli_real_data_coverage_diff_bundle_policy_failure_keeps_artifacts(
    tmp_path,
    capsys,
) -> None:
    right_path = tmp_path / "real-data-coverage-regressed.json"
    right_path.write_text(json.dumps(_regressed_coverage_fixture()), encoding="utf-8")
    output_dir = tmp_path / "real-data-coverage-diff-bundle"

    assert (
        cli_main(
            [
                "real-data-coverage-diff-bundle",
                "--left",
                str(COVERAGE_FIXTURE_PATH),
                "--right",
                str(right_path),
                "--output-dir",
                str(output_dir),
                "--fail-on-regression",
                "--fail-on-status",
                "fail",
            ]
        )
        == 2
    )

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "real-data-coverage-diff.json").read_text())
    triage = json.loads((output_dir / "triage-summary.json").read_text())
    assert manifest["bundle"]["sourceKind"] == "real-data-coverage-diff"
    assert manifest["reports"][0]["schema"] == "edgp.real_data.coverage_diff.v1"
    assert report["policy"]["status"] == "fail"
    assert triage["status"] == "fail"
    assert triage["summary"]["realDataCoverageDiffPolicyFailures"] == 1
    assert triage["checks"][0]["kind"] == "real-data-coverage-diff-policy"
    assert (output_dir / "001-real-data-coverage-diff.html").exists()

    assert (
        cli_main(["verify-bundle", "--path", str(output_dir), "--format", "text"])
        == 0
    )
    assert capsys.readouterr().out.startswith("OK ")
