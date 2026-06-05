"""Schema contract tests for EDGP report bundle manifests."""

import json
from pathlib import Path

from src.output.report_bundle import write_report_bundle


SCHEMA_PATH = Path("docs/schemas/edgp.report.bundle.v1.schema.json")


def test_report_bundle_schema_documents_generated_manifest_shape(tmp_path) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

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
