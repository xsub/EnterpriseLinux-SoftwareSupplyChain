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

    assert summary["directPublicSources"] == 2
    assert summary["generatedPublicReports"] >= 10
    assert summary["replacementCandidateGroups"] >= 4
    assert summary["publicEvidenceCoveragePercent"] > 0
    assert plans["Advisory and OSV-shaped samples"]["priority"] == "high"
    assert plans["Validation failure examples"]["decision"] == "keep-synthetic"


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


def test_cli_real_data_coverage_outputs_current_report(capsys) -> None:
    assert cli_main(["real-data-coverage", "--fixture-dir", "tests/fixtures"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == build_real_data_coverage_report(build_fixture_provenance())
    assert payload["schema"] == "edgp.real_data.coverage.v1"


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
    assert report["summary"]["directPublicSources"] == 2
    html = (output_dir / "001-real-data-coverage.html").read_text(encoding="utf-8")
    assert 'data-testid="real-data-coverage-plan-panel"' in html

    assert (
        cli_main(["verify-bundle", "--path", str(output_dir), "--format", "text"])
        == 0
    )
    assert capsys.readouterr().out.startswith("OK ")
