"""Bundle catalog tests for batch report-bundle verification."""

import json
from pathlib import Path

from src.bundle_catalog import build_bundle_catalog_report
from src.output.report_bundle import write_report_bundle


def test_build_bundle_catalog_report_summarizes_verified_bundles(tmp_path) -> None:
    graph_bundle = tmp_path / "graph-bundle"
    diagnostics_bundle = tmp_path / "diagnostics-bundle"
    write_report_bundle(
        [Path("tests/fixtures/snapshot-right.json")],
        graph_bundle,
        bundle_metadata={
            "sourceKind": "edgp-json",
            "command": "edgp report-bundle --input snapshot",
        },
    )
    write_report_bundle(
        [Path("tests/fixtures/npm-diagnostics-report.json")],
        diagnostics_bundle,
        bundle_metadata={
            "sourceKind": "npm-diagnostics",
            "command": "edgp npm-diagnostics-bundle --path package-lock.json",
        },
        include_triage_summary=True,
    )

    report = build_bundle_catalog_report([graph_bundle, diagnostics_bundle])

    assert report["schema"] == "edgp.bundle.catalog.v1"
    assert report["summary"] == {
        "bundles": 2,
        "okBundles": 2,
        "failedBundles": 0,
        "reports": 2,
        "failures": 0,
        "triagePass": 0,
        "triageWarn": 1,
        "triageFail": 0,
        "withoutTriage": 1,
    }
    assert report["sourceKinds"] == [
        {"sourceKind": "edgp-json", "bundles": 1, "reports": 1, "failures": 0},
        {
            "sourceKind": "npm-diagnostics",
            "bundles": 1,
            "reports": 1,
            "failures": 0,
        },
    ]
    assert report["bundles"][0]["reportSchemas"] == ["edgp.graph.snapshot.v1"]
    assert report["bundles"][1]["triageStatus"] == "warn"
    assert report["bundles"][1]["bundleSha256"]


def test_build_bundle_catalog_report_captures_tampered_bundle(tmp_path) -> None:
    bundle_dir = tmp_path / "bundle"
    write_report_bundle([Path("tests/fixtures/snapshot-right.json")], bundle_dir)
    (bundle_dir / "001-snapshot-right.html").write_text(
        "<!doctype html><title>changed</title>",
        encoding="utf-8",
    )

    report = build_bundle_catalog_report([bundle_dir])

    assert report["summary"]["failedBundles"] == 1
    assert report["summary"]["failures"] == 1
    assert report["bundles"][0]["ok"] is False
    assert report["bundles"][0]["failureCodes"] == ["htmlDigestMismatch"]
    assert report["bundles"][0]["bundleSha256"]
