"""Submission plan index tests for offline egress readiness summaries."""

import json
from pathlib import Path

from src.cli import main
from src.submission_plan_index import build_submission_plan_index


def test_build_submission_plan_index_summarizes_supported_plans(tmp_path) -> None:
    export_plan = _copy_fixture(
        "tests/fixtures/export-batch-submission-plan.json",
        tmp_path / "export-plan.json",
    )
    bundle_plan = _copy_fixture(
        "tests/fixtures/report-bundle-submission-plan.json",
        tmp_path / "bundle-plan.json",
    )

    index = build_submission_plan_index([export_plan, bundle_plan])

    assert index["schema"] == "edgp.submission.plan.index.v1"
    assert index["ok"] is True
    assert index["summary"] == {
        "plans": 2,
        "okPlans": 2,
        "failedPlans": 0,
        "artifacts": 4,
        "bytes": 7517,
        "failures": 0,
        "targets": ["dependency-track", "workbench"],
        "schemas": [
            "edgp.export.batch.submission_plan.v1",
            "edgp.report.bundle.submission_plan.v1",
        ],
    }
    assert [plan["schema"] for plan in index["plans"]] == [
        "edgp.export.batch.submission_plan.v1",
        "edgp.report.bundle.submission_plan.v1",
    ]
    assert index["plans"][0]["path"].endswith("export-plan.json")
    assert index["failures"] == []


def test_cli_submission_plan_index_writes_output_and_text_summary(
    tmp_path,
    capsys,
) -> None:
    export_plan = _copy_fixture(
        "tests/fixtures/export-batch-submission-plan.json",
        tmp_path / "export-plan.json",
    )
    bundle_plan = _copy_fixture(
        "tests/fixtures/report-bundle-submission-plan.json",
        tmp_path / "bundle-plan.json",
    )
    output_path = tmp_path / "submission-plan-index.json"

    assert (
        main(
            [
                "submission-plan-index",
                "--input",
                str(export_plan),
                "--input",
                str(bundle_plan),
                "--output",
                str(output_path),
                "--format",
                "text",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out.startswith(
        "OK plans=2 failedPlans=0 artifacts=4 bytes=7517 failures=0 "
    )
    index = json.loads(output_path.read_text(encoding="utf-8"))
    assert index["schema"] == "edgp.submission.plan.index.v1"
    assert index["ok"] is True


def test_cli_submission_plan_index_can_gate_on_triage_status(
    tmp_path,
    capsys,
) -> None:
    bundle_plan_payload = json.loads(
        Path("tests/fixtures/report-bundle-submission-plan.json").read_text(
            encoding="utf-8"
        )
    )
    bundle_plan_payload["triageSummary"] = {
        "status": "warn",
        "summary": {
            "failedChecks": 0,
            "npmDuplicatePackageNames": 1,
        },
    }
    bundle_plan = tmp_path / "bundle-plan.json"
    bundle_plan.write_text(
        json.dumps(bundle_plan_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    output_path = tmp_path / "submission-plan-index.json"

    assert (
        main(
            [
                "submission-plan-index",
                "--input",
                str(bundle_plan),
                "--output",
                str(output_path),
                "--format",
                "text",
                "--fail-on-status",
                "warn",
            ]
        )
        == 2
    )

    text = capsys.readouterr().out.strip()
    assert text.startswith(
        "OK plans=1 failedPlans=0 artifacts=3 bytes=6656 failures=0 "
    )
    assert text.endswith("targets=workbench triageWarn=1 triageFail=0")
    index = json.loads(output_path.read_text(encoding="utf-8"))
    assert index["summary"]["triageWarn"] == 1
    assert index["summary"]["triageFail"] == 0
    assert index["plans"][0]["triageStatus"] == "warn"


def test_submission_plan_index_reports_failed_plan(tmp_path) -> None:
    failed_plan = json.loads(
        Path("tests/fixtures/export-batch-submission-plan.json").read_text(
            encoding="utf-8"
        )
    )
    failed_plan["ok"] = False
    failed_plan["summary"]["artifacts"] = 0
    failed_plan["summary"]["bytes"] = 0
    failed_plan["summary"]["failures"] = 1
    failed_plan["artifacts"] = []
    failed_plan["failures"] = [
        {
            "code": "targetArtifactMissing",
            "message": "No export artifacts match submission target dependency-track",
            "path": "$.exports",
        }
    ]
    failed_path = tmp_path / "failed-plan.json"
    failed_path.write_text(
        json.dumps(failed_plan, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    index = build_submission_plan_index([failed_path])

    assert index["ok"] is False
    assert index["summary"]["failedPlans"] == 1
    assert index["summary"]["failures"] == 1
    assert index["plans"][0]["ok"] is False
    assert index["failures"] == []


def test_submission_plan_index_rejects_unsupported_plan_schema(tmp_path) -> None:
    unsupported_path = tmp_path / "unsupported.json"
    unsupported_path.write_text(
        json.dumps(
            {
                "schema": "edgp.unknown.v1",
                "ok": True,
                "summary": {"artifacts": 1, "bytes": 10, "failures": 0},
                "target": {"kind": "unknown", "endpoint": "https://example.invalid"},
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    index = build_submission_plan_index([unsupported_path])

    assert index["ok"] is False
    assert index["summary"]["failedPlans"] == 1
    assert index["summary"]["failures"] == 1
    assert index["plans"][0]["schema"] == "edgp.unknown.v1"
    assert index["failures"] == [
        {
            "code": "planSchemaUnsupported",
            "message": "Unsupported submission plan schema edgp.unknown.v1",
            "path": str(unsupported_path.resolve()),
        }
    ]


def _copy_fixture(source: str, destination: Path) -> Path:
    destination.write_text(Path(source).read_text(encoding="utf-8"), encoding="utf-8")
    return destination
