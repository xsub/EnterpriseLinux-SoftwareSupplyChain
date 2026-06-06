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


def test_validate_target_matches_committed_bundle_failure_fixtures() -> None:
    cases = [
        (
            Path("tests/fixtures/tampered-report-bundle-manifest"),
            Path("tests/fixtures/validation-failure-tampered-bundle-manifest.json"),
        ),
        (
            Path("tests/fixtures/tampered-report-bundle-member"),
            Path("tests/fixtures/validation-failure-tampered-bundle-member.json"),
        ),
        (
            Path("tests/fixtures/missing-html-report-bundle"),
            Path("tests/fixtures/validation-failure-missing-bundle-html.json"),
        ),
        (
            Path("tests/fixtures/missing-source-report-bundle"),
            Path("tests/fixtures/validation-failure-missing-bundle-source.json"),
        ),
        (
            Path("tests/fixtures/invalid-manifest-missing-report-count-bundle"),
            Path(
                "tests/fixtures/"
                "validation-failure-invalid-manifest-missing-report-count.json"
            ),
        ),
        (
            Path("tests/fixtures/invalid-report-missing-title-bundle"),
            Path("tests/fixtures/validation-failure-invalid-report-missing-title.json"),
        ),
        (
            Path("tests/fixtures/invalid-manifest-unknown-field-bundle"),
            Path("tests/fixtures/validation-failure-invalid-manifest-unknown-field.json"),
        ),
        (
            Path("tests/fixtures/invalid-report-unknown-field-bundle"),
            Path("tests/fixtures/validation-failure-invalid-report-unknown-field.json"),
        ),
        (
            Path("tests/fixtures/invalid-bundle-source-kind-bundle"),
            Path("tests/fixtures/validation-failure-invalid-bundle-source-kind.json"),
        ),
        (
            Path("tests/fixtures/invalid-report-digest-bundle"),
            Path("tests/fixtures/validation-failure-invalid-report-digest.json"),
        ),
    ]

    for bundle_dir, fixture_path in cases:
        report = validate_target(bundle_dir)
        expected = json.loads(fixture_path.read_text(encoding="utf-8"))

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
    bundle_verification = normalized.get("bundleVerification")
    bundle_dir = ""
    if isinstance(bundle_verification, dict):
        bundle = dict(bundle_verification)
        bundle_dir = str(bundle.get("bundleDir", ""))
        bundle["bundleDir"] = "<bundle-dir>"
        if bundle.get("bundleSha256") is not None:
            bundle["bundleSha256"] = "<bundleSha256>"
        bundle["failures"] = _normalize_failure_paths(
            bundle.get("failures", []),
            bundle_dir,
        )
        normalized["bundleVerification"] = bundle
    normalized["target"] = "<target>"
    normalized["failures"] = _normalize_failure_paths(
        normalized.get("failures", []),
        bundle_dir,
    )
    return normalized


def _normalize_failure_paths(
    failures: object,
    bundle_dir: str,
) -> list[dict[str, object]]:
    normalized = []
    if not isinstance(failures, list):
        return normalized
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        item = dict(failure)
        if bundle_dir and isinstance(item.get("path"), str):
            item["path"] = item["path"].replace(bundle_dir, "<bundle-dir>", 1)
        normalized.append(item)
    return normalized
