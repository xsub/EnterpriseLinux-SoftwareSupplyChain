"""CLI tests for CycloneDX SBOM graph ingestion."""

import json
from pathlib import Path

from src.cli import main


def test_cli_sbom_snapshot(capsys) -> None:
    assert (
        main(["sbom", "--path", "tests/fixtures/sample-bom.json", "--format", "json"])
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "npm"
    assert payload["stats"] == {"edges": 1, "nodes": 2}


def test_cli_query_sbom_uses_name_selector(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--source",
                "sbom",
                "--path",
                "tests/fixtures/sample-bom.json",
                "--operation",
                "reachable",
                "--node",
                "demo-app",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["node"] == "demo-app==1.0.0"
    assert payload["result"] == ["left-pad==1.3.0"]


def test_cli_sbom_bundle_writes_graph_and_impact_reports(tmp_path, capsys) -> None:
    output_dir = tmp_path / "sbom-bundle"

    assert (
        main(
            [
                "sbom-bundle",
                "--path",
                "tests/fixtures/sample-bom.json",
                "--impact-node",
                "left-pad",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    graph = json.loads((output_dir / "sbom-graph.json").read_text(encoding="utf-8"))
    impact = json.loads(
        (output_dir / "impact-left-pad-1.3.0.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert graph["schema"] == "edgp.graph.snapshot.v1"
    assert graph["ecosystem"] == "npm"
    assert impact["schema"] == "edgp.impact.report.v1"
    assert impact["node"] == "left-pad==1.3.0"
    assert manifest["bundle"]["sourceKind"] == "cyclonedx-sbom"
    assert manifest["bundle"]["command"].startswith("edgp sbom-bundle ")
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.impact.report.v1",
    ]
    graph_html = (output_dir / "001-sbom-graph.html").read_text(encoding="utf-8")
    assert "left-pad==1.3.0" in graph_html
    assert (output_dir / "002-impact-left-pad-1.3.0.html").exists()


def test_cli_sbom_bundle_can_include_license_report(tmp_path, capsys) -> None:
    output_dir = tmp_path / "sbom-bundle"

    assert (
        main(
            [
                "sbom-bundle",
                "--path",
                "tests/fixtures/sample-bom.json",
                "--deny-license",
                "WTFPL",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    license_report = json.loads(
        (output_dir / "license-report.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert license_report["schema"] == "edgp.license.report.v1"
    assert license_report["summary"]["deniedFindings"] == 1
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.license.report.v1",
    ]
    assert (output_dir / "002-license-report.html").exists()


def test_cli_sbom_bundle_can_fail_on_denied_license_after_writing_bundle(
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "sbom-bundle"

    assert (
        main(
            [
                "sbom-bundle",
                "--path",
                "tests/fixtures/sample-bom.json",
                "--deny-license",
                "WTFPL",
                "--fail-on-denied",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 2
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    license_report = json.loads(
        (output_dir / "license-report.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert license_report["summary"]["deniedFindings"] == 1
    assert manifest["reports"][1]["schema"] == "edgp.license.report.v1"
    assert (output_dir / "002-license-report.html").exists()
