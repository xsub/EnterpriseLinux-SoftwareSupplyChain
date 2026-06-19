"""Real-data replacement plan diff report tests."""

import json
from pathlib import Path

from scripts.generate_fixture_provenance import build_fixture_provenance
from src.cli import main as cli_main
from src.output.html_report import render_report
from src.real_data_coverage import build_real_data_coverage_report
from src.real_data_replacement_plan import build_real_data_replacement_plan_report
from src.real_data_replacement_plan_diff import (
    build_real_data_replacement_plan_diff_report,
)
from src.schema_validation import validate_target


PLAN_FIXTURE_PATH = Path("tests/fixtures/real-data-replacement-plan.json")
DIFF_FIXTURE_PATH = Path("tests/fixtures/real-data-replacement-plan-diff.json")
COVERAGE_FIXTURE_PATH = Path("tests/fixtures/real-data-coverage.json")


def _fixture() -> dict:
    return json.loads(DIFF_FIXTURE_PATH.read_text(encoding="utf-8"))


def _plan_fixture() -> dict:
    return json.loads(PLAN_FIXTURE_PATH.read_text(encoding="utf-8"))


def _generated_plan() -> dict:
    return build_real_data_replacement_plan_report(
        build_real_data_coverage_report(build_fixture_provenance())
    )


def test_real_data_replacement_plan_diff_fixture_matches_generator() -> None:
    plan = _generated_plan()
    expected = build_real_data_replacement_plan_diff_report(
        plan,
        plan,
        left_label="baseline",
        right_label="current",
    )

    assert _fixture() == expected


def test_real_data_replacement_plan_diff_documents_stable_baseline() -> None:
    report = _fixture()

    assert report["schema"] == "edgp.real_data.replacement_plan_diff.v1"
    assert report["left"]["label"] == "baseline"
    assert report["right"]["label"] == "current"
    assert report["summary"]["replacementCandidatesDelta"] == 0
    assert report["summary"]["candidateFilesDelta"] == 0
    assert report["summary"]["regressions"] == 0
    assert report["regressions"] == []


def test_real_data_replacement_plan_diff_validates_against_schema() -> None:
    report = validate_target(DIFF_FIXTURE_PATH)

    assert report["ok"] is True
    assert report["contract"] == "edgp.real_data.replacement_plan_diff.v1"
    assert report["reportStatus"] == "pass"


def test_real_data_replacement_plan_diff_renders_static_html() -> None:
    html = render_report(_fixture())

    assert "<!doctype html>" in html
    assert 'data-testid="real-data-replacement-plan-diff-sides-panel"' in html
    assert 'data-testid="real-data-replacement-plan-diff-regressions-panel"' in html
    assert "Replacement backlog trend" in html


def test_real_data_replacement_plan_diff_policy_detects_regression() -> None:
    left = _plan_fixture()
    right = _regressed_plan(left)

    report = build_real_data_replacement_plan_diff_report(
        left,
        right,
        fail_on_regression=True,
    )

    assert report["status"] == "fail"
    assert report["policy"]["status"] == "fail"
    assert report["summary"]["replacementCandidatesDelta"] == 1
    assert report["regressions"][0]["code"] == "replacementCandidatesIncreased"


def test_cli_real_data_replacement_plan_diff_outputs_current_baseline(
    capsys,
) -> None:
    assert (
        cli_main(
            [
                "real-data-replacement-plan-diff",
                "--left",
                str(PLAN_FIXTURE_PATH),
                "--right",
                str(PLAN_FIXTURE_PATH),
                "--left-label",
                "baseline",
                "--right-label",
                "current",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == _fixture()


def test_cli_real_data_replacement_plan_diff_outputs_text_summary(
    capsys,
) -> None:
    assert (
        cli_main(
            [
                "real-data-replacement-plan-diff",
                "--left",
                str(PLAN_FIXTURE_PATH),
                "--right",
                str(PLAN_FIXTURE_PATH),
                "--left-label",
                "baseline",
                "--right-label",
                "current",
                "--format",
                "text",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out.strip()
    assert output.startswith("PASS schema=edgp.real_data.replacement_plan_diff.v1 ")
    assert "left=baseline" in output
    assert "right=current" in output
    assert "replacementCandidatesDelta=0" in output
    assert "regressions=0" in output


def test_cli_real_data_replacement_plan_diff_can_compare_fixture_dirs(
    capsys,
) -> None:
    assert (
        cli_main(
            [
                "real-data-replacement-plan-diff",
                "--left-fixture-dir",
                "tests/fixtures",
                "--right-fixture-dir",
                "tests/fixtures",
                "--left-label",
                "baseline",
                "--right-label",
                "current",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload == _fixture()


def test_cli_real_data_replacement_plan_diff_can_compare_coverage_reports(
    capsys,
) -> None:
    assert (
        cli_main(
            [
                "real-data-replacement-plan-diff",
                "--left-coverage",
                str(COVERAGE_FIXTURE_PATH),
                "--right-coverage",
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
    assert payload == _fixture()


def test_cli_real_data_replacement_plan_diff_returns_two_on_regression(
    tmp_path,
    capsys,
) -> None:
    right_path = tmp_path / "real-data-replacement-plan-regressed.json"
    right_path.write_text(json.dumps(_regressed_plan(_plan_fixture())), encoding="utf-8")

    assert (
        cli_main(
            [
                "real-data-replacement-plan-diff",
                "--left",
                str(PLAN_FIXTURE_PATH),
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
    assert payload["summary"]["addedCandidates"] == 1


def test_cli_real_data_replacement_plan_diff_text_keeps_policy_exit_code(
    tmp_path,
    capsys,
) -> None:
    right_path = tmp_path / "real-data-replacement-plan-regressed.json"
    right_path.write_text(json.dumps(_regressed_plan(_plan_fixture())), encoding="utf-8")

    assert (
        cli_main(
            [
                "real-data-replacement-plan-diff",
                "--left",
                str(PLAN_FIXTURE_PATH),
                "--right",
                str(right_path),
                "--fail-on-regression",
                "--format",
                "text",
            ]
        )
        == 2
    )

    output = capsys.readouterr().out.strip()
    assert output.startswith("FAIL schema=edgp.real_data.replacement_plan_diff.v1 ")
    assert "addedCandidates=1" in output
    assert "policyStatus=fail" in output
    assert "policyFailures=" in output


def test_cli_real_data_replacement_plan_diff_bundle_writes_verifiable_bundle(
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "real-data-replacement-plan-diff-bundle"

    assert (
        cli_main(
            [
                "real-data-replacement-plan-diff-bundle",
                "--left",
                str(PLAN_FIXTURE_PATH),
                "--right",
                str(PLAN_FIXTURE_PATH),
                "--left-label",
                "baseline",
                "--right-label",
                "current",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "real-data-replacement-plan-diff"
    assert manifest["reports"][0]["href"] == "001-real-data-replacement-plan-diff.html"
    assert manifest["reports"][0]["schema"] == (
        "edgp.real_data.replacement_plan_diff.v1"
    )
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    assert (output_dir / "001-real-data-replacement-plan-diff.html").exists()

    report = json.loads(
        (output_dir / "real-data-replacement-plan-diff.json").read_text(
            encoding="utf-8"
        )
    )
    assert report == _fixture()

    assert (
        cli_main(["verify-bundle", "--path", str(output_dir), "--format", "text"])
        == 0
    )
    assert capsys.readouterr().out.startswith("OK ")


def test_cli_real_data_replacement_plan_diff_bundle_policy_failure_keeps_artifacts(
    tmp_path,
    capsys,
) -> None:
    right_path = tmp_path / "real-data-replacement-plan-regressed.json"
    right_path.write_text(json.dumps(_regressed_plan(_plan_fixture())), encoding="utf-8")
    output_dir = tmp_path / "real-data-replacement-plan-diff-policy-bundle"

    assert (
        cli_main(
            [
                "real-data-replacement-plan-diff-bundle",
                "--left",
                str(PLAN_FIXTURE_PATH),
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
    report = json.loads(
        (output_dir / "real-data-replacement-plan-diff.json").read_text(
            encoding="utf-8"
        )
    )
    triage = json.loads((output_dir / "triage-summary.json").read_text())
    assert report["policy"]["status"] == "fail"
    assert triage["status"] == "fail"
    assert triage["summary"]["realDataReplacementPlanDiffPolicyFailures"] == 1
    assert (output_dir / "001-real-data-replacement-plan-diff.html").exists()


def _regressed_plan(plan: dict) -> dict:
    regressed = json.loads(json.dumps(plan))
    candidate = {
        "rank": len(regressed["replacementCandidates"]) + 1,
        "group": "New public-data gap",
        "kind": "synthetic-public-shape",
        "fileCount": 2,
        "decision": "replace-where-practical",
        "priority": "high",
        "nextStep": "Add a stable public source for this newly covered fixture group.",
        "files": ["tests/fixtures/new-public-gap.json"],
    }
    regressed["replacementCandidates"].append(candidate)
    summary = regressed["summary"]
    summary["totalGroups"] += 1
    summary["replacementCandidates"] += 1
    summary["candidateFiles"] += candidate["fileCount"]
    summary["highPriorityGroups"] += 1
    return regressed
