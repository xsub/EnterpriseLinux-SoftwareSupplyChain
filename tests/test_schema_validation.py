"""Validation tests for documented EDGP JSON contracts."""

import json
from pathlib import Path

from src.output.report_bundle import write_report_bundle
from src.schema_validation import validate_target


def test_validate_target_accepts_documented_report_fixture() -> None:
    report = validate_target(Path("tests/fixtures/snapshot-right.json"))

    assert report["schema"] == "edgp.validation.report.v1"
    assert report["ok"] is True
    assert report["targetType"] == "json-file"
    assert report["contract"] == "edgp.graph.snapshot.v1"
    assert report["summary"] == {"failures": 0}
    assert report["failures"] == []


def test_validate_target_reports_contract_mismatch(tmp_path) -> None:
    payload = json.loads(Path("tests/fixtures/snapshot-right.json").read_text())
    payload["stats"].pop("edges")
    path = tmp_path / "bad-snapshot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_target(path)

    assert report["ok"] is False
    assert report["summary"]["failures"] >= 1
    assert {
        "code": "requiredMissing",
        "message": "Missing required field edges",
        "path": "$.stats.edges",
    } in report["failures"]


def test_validate_target_matches_committed_failure_fixture() -> None:
    report = validate_target(Path("tests/fixtures/invalid-snapshot-missing-edge-count.json"))
    expected = json.loads(
        Path("tests/fixtures/validation-failure-missing-edge-count.json").read_text(
            encoding="utf-8"
        )
    )

    assert _normalize_validation_report(report) == expected


def test_validate_target_accepts_report_bundle_directory(tmp_path) -> None:
    write_report_bundle(
        [
            Path("tests/fixtures/snapshot-right.json"),
            Path("tests/fixtures/npm-diagnostics-report.json"),
        ],
        tmp_path,
    )

    report = validate_target(tmp_path)

    assert report["ok"] is True
    assert report["targetType"] == "report-bundle"
    assert report["contract"] == "edgp.report.bundle.v1"
    assert report["summary"] == {"failures": 0}
    assert report["bundleVerification"]["ok"] is True


def _normalize_validation_report(report: dict[str, object]) -> dict[str, object]:
    normalized = dict(report)
    normalized["target"] = "<target>"
    return normalized
