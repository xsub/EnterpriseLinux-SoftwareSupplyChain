"""CLI tests for npm graph and diagnostics report bundles."""

import json
from pathlib import Path

from src.cli import main


def test_cli_npm_bundle_writes_json_html_index_and_manifest(tmp_path, capsys) -> None:
    output_dir = tmp_path / "npm-bundle"

    assert (
        main(
            [
                "npm-bundle",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    index_path = output_dir / "index.html"
    assert Path(capsys.readouterr().out.strip()) == index_path
    graph = json.loads((output_dir / "npm-graph.json").read_text(encoding="utf-8"))
    diagnostics = json.loads(
        (output_dir / "npm-diagnostics.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert graph["schema"] == "edgp.graph.snapshot.v1"
    assert diagnostics["schema"] == "edgp.npm.diagnostics.v1"
    assert manifest["schema"] == "edgp.report.bundle.v1"
    assert manifest["bundle"]["sourceKind"] == "npm-lockfile"
    assert manifest["bundle"]["command"].startswith("edgp npm-bundle ")
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.npm.diagnostics.v1",
    ]
    assert [report["source"] for report in manifest["reports"]] == [
        "npm-graph.json",
        "npm-diagnostics.json",
    ]
    assert (output_dir / "001-npm-graph.html").exists()
    diagnostics_html = (output_dir / "002-npm-diagnostics.html").read_text(
        encoding="utf-8"
    )
    assert 'data-testid="npm-conflicts-panel"' in diagnostics_html


def test_cli_npm_bundle_can_include_impact_and_advisory_reports(
    tmp_path, capsys
) -> None:
    output_dir = tmp_path / "npm-bundle"

    assert (
        main(
            [
                "npm-bundle",
                "--path",
                "tests/fixtures/package-lock.json",
                "--impact-node",
                "left-pad",
                "--advisories",
                "tests/fixtures/advisories.json",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    impact = json.loads(
        (output_dir / "impact-left-pad-1.3.0.json").read_text(encoding="utf-8")
    )
    advisory = json.loads(
        (output_dir / "advisory-report.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert impact["schema"] == "edgp.impact.report.v1"
    assert impact["node"] == "left-pad==1.3.0"
    assert advisory["schema"] == "edgp.advisory.report.v1"
    assert advisory["summary"]["findings"] == 1
    assert manifest["bundle"]["sourceKind"] == "npm-lockfile"
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.npm.diagnostics.v1",
        "edgp.impact.report.v1",
        "edgp.advisory.report.v1",
    ]
    assert (output_dir / "003-impact-left-pad-1.3.0.html").exists()
    advisory_html = (output_dir / "004-advisory-report.html").read_text(
        encoding="utf-8"
    )
    assert 'data-testid="advisory-findings-panel"' in advisory_html
