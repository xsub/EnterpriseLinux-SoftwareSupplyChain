"""Real-data coverage report tests."""

import json
from pathlib import Path

from scripts.generate_fixture_provenance import build_fixture_provenance
from src.cli import main as cli_main
from src.output.html_report import render_report
from src.real_data_coverage import build_real_data_coverage_report
from src.schema_validation import validate_target


FIXTURE_PATH = Path("tests/fixtures/real-data-coverage.json")


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_real_data_coverage_fixture_matches_generator() -> None:
    expected = build_real_data_coverage_report(build_fixture_provenance())

    assert _fixture() == expected


def test_real_data_coverage_documents_public_and_synthetic_evidence() -> None:
    report = _fixture()
    summary = report["summary"]
    plans = {entry["group"]: entry for entry in report["replacementPlan"]}

    assert summary["directPublicSources"] == 3
    assert summary["generatedPublicReports"] >= 14
    assert summary["replacementCandidateGroups"] >= 4
    assert summary["publicEvidenceCoveragePercent"] > 0
    assert plans["Advisory and OSV-shaped samples"]["priority"] == "high"
    assert plans["Validation failure examples"]["decision"] == "keep-synthetic"
    assert "policy" not in report


def test_real_data_coverage_validates_against_schema() -> None:
    report = validate_target(FIXTURE_PATH)

    assert report["ok"] is True
    assert report["contract"] == "edgp.real_data.coverage.v1"
    assert report["reportStatus"] == "warn"


def test_real_data_coverage_renders_static_html() -> None:
    html = render_report(_fixture())

    assert "<!doctype html>" in html
    assert 'data-testid="real-data-coverage-public-panel"' in html
    assert 'data-testid="real-data-coverage-plan-panel"' in html
    assert "Fixture data quality coverage" in html


def test_real_data_coverage_policy_can_fail_on_threshold(tmp_path) -> None:
    report = build_real_data_coverage_report(
        build_fixture_provenance(),
        min_public_evidence_percent=99.0,
    )
    report_path = tmp_path / "real-data-policy.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    assert report["status"] == "fail"
    assert report["policy"]["status"] == "fail"
    assert report["policy"]["exitCode"] == 2
    assert report["policy"]["failures"][0]["code"] == (
        "publicEvidenceCoverageBelowThreshold"
    )
    validation = validate_target(report_path)
    assert validation["ok"] is True
    assert validation["reportStatus"] == "fail"


def test_real_data_coverage_policy_can_fail_on_priority() -> None:
    report = build_real_data_coverage_report(
        build_fixture_provenance(),
        fail_on_priority="high",
    )

    assert report["status"] == "fail"
    assert report["policy"]["matchedReplacementGroups"] == 1
    assert report["policy"]["failures"][0]["code"] == "replacementPriorityMatched"


def test_real_data_coverage_policy_renders_static_html() -> None:
    report = build_real_data_coverage_report(
        build_fixture_provenance(),
        fail_on_priority="high",
    )

    html = render_report(report)

    assert 'data-testid="real-data-coverage-policy-panel"' in html
    assert "replacementPriorityMatched" in html


def test_cli_real_data_coverage_outputs_current_report(capsys) -> None:
    assert cli_main(["real-data-coverage", "--fixture-dir", "tests/fixtures"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == build_real_data_coverage_report(build_fixture_provenance())
    assert payload["schema"] == "edgp.real_data.coverage.v1"


def test_cli_real_data_coverage_outputs_text_summary(capsys) -> None:
    assert (
        cli_main(
            [
                "real-data-coverage",
                "--fixture-dir",
                "tests/fixtures",
                "--format",
                "text",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out.strip()
    assert output.startswith("WARN schema=edgp.real_data.coverage.v1 ")
    assert "directPublicSources=3" in output
    assert "generatedPublicReports=14" in output
    assert "topCandidate=" in output
    assert "Advisory and OSV-shaped samples" in output


def test_cli_real_data_coverage_returns_two_when_policy_fails(capsys) -> None:
    assert (
        cli_main(
            [
                "real-data-coverage",
                "--fixture-dir",
                "tests/fixtures",
                "--fail-on-priority",
                "high",
            ]
        )
        == 2
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "fail"
    assert payload["policy"]["status"] == "fail"


def test_cli_real_data_coverage_text_keeps_policy_exit_code(capsys) -> None:
    assert (
        cli_main(
            [
                "real-data-coverage",
                "--fixture-dir",
                "tests/fixtures",
                "--fail-on-priority",
                "high",
                "--format",
                "text",
            ]
        )
        == 2
    )

    output = capsys.readouterr().out.strip()
    assert output.startswith("FAIL schema=edgp.real_data.coverage.v1 ")
    assert "policyStatus=fail" in output
    assert "matchedReplacementGroups=1" in output


def test_cli_real_data_coverage_bundle_writes_verifiable_bundle(
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "real-data-coverage-bundle"

    assert (
        cli_main(
            [
                "real-data-coverage-bundle",
                "--fixture-dir",
                "tests/fixtures",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "real-data-coverage"
    assert manifest["reports"][0]["href"] == "001-real-data-coverage.html"
    assert manifest["reports"][0]["schema"] == "edgp.real_data.coverage.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"

    report = json.loads((output_dir / "real-data-coverage.json").read_text())
    assert report["summary"]["directPublicSources"] == 3
    html = (output_dir / "001-real-data-coverage.html").read_text(encoding="utf-8")
    assert 'data-testid="real-data-coverage-plan-panel"' in html

    assert (
        cli_main(["verify-bundle", "--path", str(output_dir), "--format", "text"])
        == 0
    )
    assert capsys.readouterr().out.startswith("OK ")


def test_cli_real_data_coverage_bundle_policy_failure_keeps_artifacts(
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "real-data-coverage-policy-bundle"

    assert (
        cli_main(
            [
                "real-data-coverage-bundle",
                "--fixture-dir",
                "tests/fixtures",
                "--output-dir",
                str(output_dir),
                "--fail-on-priority",
                "high",
                "--fail-on-status",
                "fail",
            ]
        )
        == 2
    )

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    report = json.loads((output_dir / "real-data-coverage.json").read_text())
    triage = json.loads((output_dir / "triage-summary.json").read_text())
    assert report["policy"]["status"] == "fail"
    assert triage["status"] == "fail"
    assert triage["summary"]["realDataCoveragePolicyFailures"] == 1
    assert triage["checks"][0]["kind"] == "real-data-coverage-policy"
    assert (output_dir / "001-real-data-coverage.html").exists()
