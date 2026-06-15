"""Validation tests for documented EDGP JSON contracts."""

import json
from pathlib import Path

from src.output.report_bundle import write_report_bundle, write_report_bundle_archive
from src.schema_validation import validate_target


def test_validate_target_accepts_documented_report_fixture() -> None:
    report = validate_target(Path("tests/fixtures/snapshot-right.json"))

    assert report["schema"] == "edgp.validation.report.v1"
    assert report["ok"] is True
    assert report["targetType"] == "json-file"
    assert report["contract"] == "edgp.graph.snapshot.v1"
    assert report["summary"] == {"failures": 0}
    assert report["failures"] == []


def test_validate_target_accepts_bundle_catalog_nullable_fingerprint() -> None:
    report = validate_target(Path("tests/fixtures/bundle-catalog.json"))

    assert report["ok"] is True
    assert report["targetType"] == "json-file"
    assert report["contract"] == "edgp.bundle.catalog.v1"


def test_validate_target_accepts_schema_index() -> None:
    report = validate_target(Path("docs/schemas/index.json"))

    assert report["schema"] == "edgp.validation.report.v1"
    assert report["ok"] is True
    assert report["targetType"] == "json-file"
    assert report["contract"] == "edgp.schema.index.v1"
    assert report["schemaFile"] == "edgp.schema.index.v1.schema.json"


def test_validate_target_accepts_committed_validation_report() -> None:
    report = validate_target(
        Path("tests/fixtures/validation-failure-missing-edge-count.json")
    )

    assert report["schema"] == "edgp.validation.report.v1"
    assert report["ok"] is True
    assert report["targetType"] == "json-file"
    assert report["contract"] == "edgp.validation.report.v1"
    assert report["schemaFile"] == "edgp.validation.report.v1.schema.json"


def test_validate_target_enforces_any_of_schema_options(tmp_path) -> None:
    payload = json.loads(Path("tests/fixtures/bundle-catalog.json").read_text())
    payload["bundles"][0]["bundleSha256"] = 42
    path = tmp_path / "invalid-bundle-catalog.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_target(path)

    assert report["ok"] is False
    assert {
        "code": "anyOfMismatch",
        "message": "Value must match at least one schema",
        "path": "$.bundles[0].bundleSha256",
    } in report["failures"]


def test_validate_target_accepts_documented_one_of_nullable_fields(
    tmp_path,
) -> None:
    payload = json.loads(Path("tests/fixtures/impact-report.json").read_text())
    payload["root"] = None
    path = tmp_path / "impact-report-null-root.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_target(path)

    assert report["ok"] is True
    assert report["targetType"] == "json-file"
    assert report["contract"] == "edgp.impact.report.v1"


def test_validate_target_enforces_documented_one_of_fields(tmp_path) -> None:
    payload = json.loads(Path("tests/fixtures/impact-report.json").read_text())
    payload["root"] = 42
    path = tmp_path / "impact-report-invalid-root.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = validate_target(path)

    assert report["ok"] is False
    assert {
        "code": "oneOfMismatch",
        "message": "Value must match exactly one schema",
        "path": "$.root",
    } in report["failures"]


def test_validate_target_accepts_schema_typed_additional_properties(tmp_path) -> None:
    bundle_dir = tmp_path / "bundle"
    write_report_bundle(
        [Path("tests/fixtures/snapshot-right.json")],
        bundle_dir,
        bundle_metadata={
            "sourceKind": "edgp-json",
            "command": "edgp report-bundle --input snapshot",
        },
    )
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["bundle"]["ciRun"] = "local"
    path = tmp_path / "manifest-with-extra-metadata.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    report = validate_target(path)

    assert report["ok"] is True
    assert report["targetType"] == "json-file"
    assert report["contract"] == "edgp.report.bundle.v1"


def test_validate_target_enforces_schema_typed_additional_properties(tmp_path) -> None:
    bundle_dir = tmp_path / "bundle"
    write_report_bundle(
        [Path("tests/fixtures/snapshot-right.json")],
        bundle_dir,
        bundle_metadata={
            "sourceKind": "edgp-json",
            "command": "edgp report-bundle --input snapshot",
        },
    )
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["bundle"]["ciRun"] = {"not": "string"}
    path = tmp_path / "manifest-with-invalid-extra-metadata.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")

    report = validate_target(path)

    assert report["ok"] is False
    assert {
        "code": "typeMismatch",
        "message": "Expected type string",
        "path": "$.bundle.ciRun",
    } in report["failures"]


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
        (
            Path("tests/fixtures/invalid-bundle-metadata-bundle"),
            Path("tests/fixtures/validation-failure-invalid-bundle-metadata.json"),
        ),
        (
            Path("tests/fixtures/invalid-index-path-bundle"),
            Path("tests/fixtures/validation-failure-invalid-index-path.json"),
        ),
        (
            Path("tests/fixtures/invalid-manifest-schema-bundle"),
            Path("tests/fixtures/validation-failure-invalid-manifest-schema.json"),
        ),
        (
            Path("tests/fixtures/invalid-bundle-digest-bundle"),
            Path("tests/fixtures/validation-failure-invalid-bundle-digest.json"),
        ),
        (
            Path("tests/fixtures/invalid-reports-list-bundle"),
            Path("tests/fixtures/validation-failure-invalid-reports-list.json"),
        ),
        (
            Path("tests/fixtures/invalid-report-entry-bundle"),
            Path("tests/fixtures/validation-failure-invalid-report-entry.json"),
        ),
        (
            Path("tests/fixtures/invalid-report-field-bundle"),
            Path("tests/fixtures/validation-failure-invalid-report-field.json"),
        ),
        (
            Path("tests/fixtures/invalid-report-summary-bundle"),
            Path("tests/fixtures/validation-failure-invalid-report-summary.json"),
        ),
        (
            Path("tests/fixtures/invalid-report-count-bundle"),
            Path("tests/fixtures/validation-failure-invalid-report-count.json"),
        ),
        (
            Path("tests/fixtures/invalid-report-href-bundle"),
            Path("tests/fixtures/validation-failure-invalid-report-href.json"),
        ),
        (
            Path("tests/fixtures/missing-index-report-bundle"),
            Path("tests/fixtures/validation-failure-missing-index.json"),
        ),
        (
            Path("tests/fixtures/source-digest-mismatch-bundle"),
            Path("tests/fixtures/validation-failure-source-digest-mismatch.json"),
        ),
        (
            Path("tests/fixtures/missing-manifest-report-bundle"),
            Path("tests/fixtures/validation-failure-missing-manifest.json"),
        ),
        (
            Path("tests/fixtures/invalid-json-manifest-bundle"),
            Path("tests/fixtures/validation-failure-invalid-json-manifest.json"),
        ),
        (
            Path("tests/fixtures/invalid-manifest-type-bundle"),
            Path("tests/fixtures/validation-failure-invalid-manifest-type.json"),
        ),
    ]

    for bundle_dir, fixture_path in cases:
        report = validate_target(bundle_dir)
        expected = json.loads(fixture_path.read_text(encoding="utf-8"))

        assert _normalize_validation_report(report) == expected


def test_validate_target_matches_committed_bundle_archive_failure_fixture() -> None:
    report = validate_target(Path("tests/fixtures/missing-report-bundle.tar.gz"))
    expected = json.loads(
        Path("tests/fixtures/validation-failure-missing-bundle-archive.json").read_text(
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


def test_validate_target_accepts_report_bundle_archive(tmp_path) -> None:
    write_report_bundle(
        [
            Path("tests/fixtures/snapshot-right.json"),
            Path("tests/fixtures/npm-diagnostics-report.json"),
        ],
        tmp_path,
        include_triage_summary=True,
    )
    archive_path = tmp_path / "bundle.tar.gz"
    archive_report = write_report_bundle_archive(tmp_path, archive_path)

    report = validate_target(archive_path)

    assert report["ok"] is True
    assert report["targetType"] == "report-bundle-archive"
    assert report["contract"] == "edgp.report.bundle.archive.v1"
    assert report["summary"] == {"failures": 0}
    assert report["failures"] == []
    assert report["bundleArchiveVerification"]["ok"] is True
    assert (
        report["bundleArchiveVerification"]["archiveSha256"]
        == archive_report["archiveSha256"]
    )
    assert report["bundleArchiveVerification"]["verification"]["ok"] is True
    assert report["triageSummary"]["schema"] == "edgp.triage.summary.v1"
    assert report["triageSummary"]["source"] == "triage-summary.json"
    assert report["triageSummary"]["status"] == "warn"


def test_validate_target_reports_bundle_triage_summary(tmp_path) -> None:
    write_report_bundle(
        [Path("tests/fixtures/npm-diagnostics-report.json")],
        tmp_path,
        include_triage_summary=True,
    )

    report = validate_target(tmp_path)

    assert report["ok"] is True
    assert report["triageSummary"]["schema"] == "edgp.triage.summary.v1"
    assert report["triageSummary"]["source"] == "triage-summary.json"
    assert report["triageSummary"]["status"] == "warn"
    assert report["triageSummary"]["summary"]["reports"] == 1


def _normalize_validation_report(report: dict[str, object]) -> dict[str, object]:
    normalized = dict(report)
    bundle_verification = normalized.get("bundleVerification")
    bundle_dir = ""
    archive_path = ""
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
    bundle_archive_verification = normalized.get("bundleArchiveVerification")
    if isinstance(bundle_archive_verification, dict):
        archive = _normalize_archive_verification_report(bundle_archive_verification)
        archive_path = str(bundle_archive_verification.get("archive", ""))
        bundle_dir = str(bundle_archive_verification.get("bundleDir", ""))
        normalized["bundleArchiveVerification"] = archive
    normalized["target"] = "<target>"
    normalized["failures"] = _normalize_failure_paths(
        normalized.get("failures", []),
        bundle_dir,
        archive_path=archive_path,
    )
    return normalized


def _normalize_archive_verification_report(report: dict[str, object]) -> dict[str, object]:
    normalized = dict(report)
    archive_path = str(normalized.get("archive", ""))
    bundle_dir = str(normalized.get("bundleDir", ""))
    normalized["archive"] = "<archive>"
    normalized["bundleDir"] = "<bundle-dir>"
    if normalized.get("archiveSha256") is not None:
        normalized["archiveSha256"] = "<archiveSha256>"
    if normalized.get("bundleSha256") is not None:
        normalized["bundleSha256"] = "<bundleSha256>"
    verification = normalized.get("verification")
    if isinstance(verification, dict):
        nested = dict(verification)
        nested_bundle_dir = str(nested.get("bundleDir", bundle_dir))
        nested["bundleDir"] = "<bundle-dir>"
        if nested.get("bundleSha256") is not None:
            nested["bundleSha256"] = "<bundleSha256>"
        nested["failures"] = _normalize_failure_paths(
            nested.get("failures", []),
            nested_bundle_dir,
            archive_path=archive_path,
        )
        normalized["verification"] = nested
    return normalized


def _normalize_failure_paths(
    failures: object,
    bundle_dir: str,
    *,
    archive_path: str = "",
) -> list[dict[str, object]]:
    normalized = []
    if not isinstance(failures, list):
        return normalized
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        item = dict(failure)
        path = item.get("path")
        if isinstance(path, str):
            if archive_path:
                path = path.replace(archive_path, "<archive>", 1)
            if bundle_dir:
                path = path.replace(bundle_dir, "<bundle-dir>", 1)
            item["path"] = path
        normalized.append(item)
    return normalized
