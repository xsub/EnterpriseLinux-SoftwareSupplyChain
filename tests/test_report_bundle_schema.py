"""Schema contract tests for EDGP report bundle manifests."""

import json
from pathlib import Path

from src.output.report_bundle import verify_report_bundle, write_report_bundle


MANIFEST_SCHEMA_PATH = Path("docs/schemas/edgp.report.bundle.v1.schema.json")
VERIFICATION_SCHEMA_PATH = Path(
    "docs/schemas/edgp.report.bundle.verification.v1.schema.json"
)


def test_report_bundle_schema_documents_generated_manifest_shape(tmp_path) -> None:
    schema = json.loads(MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))

    write_report_bundle(
        [
            Path("tests/fixtures/snapshot-right.json"),
            Path("tests/fixtures/npm-diagnostics-report.json"),
        ],
        tmp_path,
        bundle_metadata={
            "sourceKind": "edgp-json",
            "command": "edgp report-bundle --input graph.json --output-dir reports",
        },
    )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    required_manifest_keys = set(schema["required"])
    report_schema = schema["properties"]["reports"]["items"]
    required_report_keys = set(report_schema["required"])

    assert required_manifest_keys <= set(manifest)
    assert manifest["schema"] == schema["properties"]["schema"]["const"]
    assert manifest["reportCount"] == len(manifest["reports"])
    assert manifest["bundle"]["sourceKind"] in schema["properties"]["bundle"][
        "properties"
    ]["sourceKind"]["enum"]
    for report in manifest["reports"]:
        assert required_report_keys <= set(report)
        assert set(report) <= set(report_schema["properties"])


def test_report_bundle_verification_schema_documents_verifier_output(tmp_path) -> None:
    schema = json.loads(VERIFICATION_SCHEMA_PATH.read_text(encoding="utf-8"))

    write_report_bundle(
        [
            Path("tests/fixtures/snapshot-right.json"),
            Path("tests/fixtures/npm-diagnostics-report.json"),
        ],
        tmp_path,
    )

    report = verify_report_bundle(tmp_path)
    required_report_keys = set(schema["required"])
    allowed_report_keys = set(schema["properties"])
    summary_schema = schema["properties"]["summary"]
    failure_schema = schema["properties"]["failures"]["items"]

    assert required_report_keys <= set(report)
    assert set(report) <= allowed_report_keys
    assert report["schema"] == schema["properties"]["schema"]["const"]
    assert report["ok"] is True
    assert report["summary"] == {"reports": 2, "failures": 0}
    assert set(report["summary"]) == set(summary_schema["required"])
    assert set(report["summary"]) <= set(summary_schema["properties"])
    assert report["failures"] == []

    (tmp_path / "001-snapshot-right.html").write_text(
        "<!doctype html><title>tampered</title>",
        encoding="utf-8",
    )
    failed_report = verify_report_bundle(tmp_path)
    failure = failed_report["failures"][0]

    assert failed_report["ok"] is False
    assert failure["code"] == "htmlDigestMismatch"
    assert set(failure_schema["required"]) <= set(failure)
    assert set(failure) <= set(failure_schema["properties"])
