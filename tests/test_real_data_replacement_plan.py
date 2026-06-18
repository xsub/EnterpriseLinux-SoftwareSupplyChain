"""Real-data replacement plan report tests."""

import json
from pathlib import Path

from scripts.generate_fixture_provenance import build_fixture_provenance
from src.cli import main as cli_main
from src.output.html_report import render_report
from src.real_data_coverage import build_real_data_coverage_report
from src.real_data_replacement_plan import build_real_data_replacement_plan_report
from src.schema_validation import validate_target


FIXTURE_PATH = Path("tests/fixtures/real-data-replacement-plan.json")
COVERAGE_FIXTURE_PATH = Path("tests/fixtures/real-data-coverage.json")


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _coverage() -> dict:
    return build_real_data_coverage_report(build_fixture_provenance())


def test_real_data_replacement_plan_fixture_matches_generator() -> None:
    expected = build_real_data_replacement_plan_report(_coverage())

    assert _fixture() == expected


def test_real_data_replacement_plan_ranks_public_replacement_candidates() -> None:
    report = _fixture()
    candidates = report["replacementCandidates"]

    assert report["schema"] == "edgp.real_data.replacement_plan.v1"
    assert report["status"] == "warn"
    assert report["summary"]["replacementCandidates"] == len(candidates)
    assert report["summary"]["highPriorityGroups"] == 1
    assert candidates[0]["rank"] == 1
    assert candidates[0]["group"] == "Advisory and OSV-shaped samples"
    assert candidates[0]["priority"] == "high"
    assert "tests/fixtures/public-osv.json" in candidates[0]["files"]
    assert report["deferredGroups"]


def test_real_data_replacement_plan_validates_against_schema() -> None:
    report = validate_target(FIXTURE_PATH)

    assert report["ok"] is True
    assert report["contract"] == "edgp.real_data.replacement_plan.v1"
    assert report["reportStatus"] == "warn"


def test_real_data_replacement_plan_renders_static_html() -> None:
    html = render_report(_fixture())

    assert "<!doctype html>" in html
    assert 'data-testid="real-data-replacement-plan-candidates-panel"' in html
    assert 'data-testid="real-data-replacement-plan-deferred-panel"' in html
    assert "Public fixture replacement plan" in html


def test_real_data_replacement_plan_policy_can_fail_on_priority() -> None:
    report = build_real_data_replacement_plan_report(
        _coverage(),
        fail_on_priority="high",
    )

    assert report["status"] == "fail"
    assert report["policy"]["status"] == "fail"
    assert report["policy"]["matchedReplacementGroups"] == 1
    assert report["policy"]["failures"][0]["code"] == (
        "replacementPlanPriorityMatched"
    )


def test_cli_real_data_replacement_plan_outputs_current_report(capsys) -> None:
    assert cli_main(["real-data-replacement-plan", "--fixture-dir", "tests/fixtures"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == build_real_data_replacement_plan_report(_coverage())
    assert payload["schema"] == "edgp.real_data.replacement_plan.v1"


def test_cli_real_data_replacement_plan_outputs_text_summary(capsys) -> None:
    assert (
        cli_main(
            [
                "real-data-replacement-plan",
                "--fixture-dir",
                "tests/fixtures",
                "--format",
                "text",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out.strip()
    assert output.startswith("WARN schema=edgp.real_data.replacement_plan.v1 ")
    assert "replacementCandidates=4" in output
    assert "candidateFiles=17" in output
    assert "coverageStatus=warn" in output
    assert "rank:1 group:Advisory and OSV-shaped samples" in output


def test_cli_real_data_replacement_plan_accepts_coverage_report(capsys) -> None:
    assert (
        cli_main(
            [
                "real-data-replacement-plan",
                "--coverage",
                str(COVERAGE_FIXTURE_PATH),
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == build_real_data_replacement_plan_report(_fixture_coverage())


def test_cli_real_data_replacement_plan_returns_two_when_policy_fails(
    capsys,
) -> None:
    assert (
        cli_main(
            [
                "real-data-replacement-plan",
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


def test_cli_real_data_replacement_plan_text_keeps_policy_exit_code(
    capsys,
) -> None:
    assert (
        cli_main(
            [
                "real-data-replacement-plan",
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
    assert output.startswith("FAIL schema=edgp.real_data.replacement_plan.v1 ")
    assert "policyStatus=fail" in output
    assert "matchedReplacementGroups=1" in output


def test_cli_real_data_replacement_plan_bundle_writes_verifiable_bundle(
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "real-data-replacement-plan-bundle"

    assert (
        cli_main(
            [
                "real-data-replacement-plan-bundle",
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
    assert manifest["bundle"]["sourceKind"] == "real-data-replacement-plan"
    assert manifest["reports"][0]["href"] == "001-real-data-replacement-plan.html"
    assert manifest["reports"][0]["schema"] == "edgp.real_data.replacement_plan.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    assert (output_dir / "001-real-data-replacement-plan.html").exists()

    report = json.loads(
        (output_dir / "real-data-replacement-plan.json").read_text(encoding="utf-8")
    )
    assert report["summary"]["replacementCandidates"] >= 1
    html = (output_dir / "001-real-data-replacement-plan.html").read_text(
        encoding="utf-8"
    )
    assert 'data-testid="real-data-replacement-plan-candidates-panel"' in html

    assert (
        cli_main(["verify-bundle", "--path", str(output_dir), "--format", "text"])
        == 0
    )
    assert capsys.readouterr().out.startswith("OK ")


def test_cli_real_data_replacement_plan_bundle_policy_failure_keeps_artifacts(
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "real-data-replacement-plan-policy-bundle"

    assert (
        cli_main(
            [
                "real-data-replacement-plan-bundle",
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
    report = json.loads(
        (output_dir / "real-data-replacement-plan.json").read_text(encoding="utf-8")
    )
    assert report["policy"]["status"] == "fail"
    assert (output_dir / "001-real-data-replacement-plan.html").exists()


def _fixture_coverage() -> dict:
    return json.loads(COVERAGE_FIXTURE_PATH.read_text(encoding="utf-8"))
