"""CLI tests for ALBS build metadata graph ingestion."""

import json
from pathlib import Path

from src.cli import main


def test_cli_albs_build_exports_json(capsys) -> None:
    assert (
        main(
            [
                "albs-build",
                "--path",
                "tests/fixtures/albs-build.json",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "albs"
    assert payload["root"] == "albs-build:17812"
    assert payload["stats"] == {"edges": 20, "nodes": 15}
    assert {
        "source": "albs-task:188080:ppc64le",
        "target": "rpm:3237086:nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm",
        "relationshipType": 25,
    } in payload["edges"]


def test_cli_albs_build_bundle_writes_graph_and_impact_reports(tmp_path, capsys) -> None:
    output_dir = tmp_path / "albs-build-bundle"
    impact_node = "rpm:3237086:nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm"

    assert (
        main(
            [
                "albs-build-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
                "--impact-node",
                impact_node,
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    graph = json.loads((output_dir / "albs-build-graph.json").read_text(encoding="utf-8"))
    inventory = json.loads(
        (output_dir / "albs-artifact-inventory.json").read_text(encoding="utf-8")
    )
    timing = json.loads((output_dir / "albs-build-timing.json").read_text(encoding="utf-8"))
    impact = json.loads(
        (
            output_dir
            / "impact-rpm-3237086-nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm.json"
        ).read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert graph["root"] == "albs-build:17812"
    assert inventory["schema"] == "edgp.albs.artifact_inventory.v1"
    assert inventory["summary"]["artifacts"] == 4
    assert inventory["packages"] == ["nginx", "nginx-core"]
    assert timing["schema"] == "edgp.albs.build_timing.v1"
    assert timing["summary"]["criticalBuildTaskWallSeconds"] == 371.070048
    assert impact["node"] == impact_node
    assert impact["summary"]["affectedDependents"] == 2
    assert manifest["bundle"]["sourceKind"] == "albs-build"
    assert manifest["bundle"]["command"].startswith("edgp albs-build-bundle ")
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.albs.artifact_inventory.v1",
        "edgp.albs.build_timing.v1",
        "edgp.impact.report.v1",
    ]
    graph_html = (output_dir / "001-albs-build-graph.html").read_text(encoding="utf-8")
    inventory_html = (output_dir / "002-albs-artifact-inventory.html").read_text(
        encoding="utf-8"
    )
    timing_html = (output_dir / "003-albs-build-timing.html").read_text(
        encoding="utf-8"
    )
    assert "25 - ALBS Produces Artifact" in graph_html
    assert "EDGP ALBS Artifact Inventory" in inventory_html
    assert "nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm" in inventory_html
    assert "EDGP ALBS Build Timing" in timing_html
    assert "371.070048" in timing_html
    assert (
        output_dir
        / "004-impact-rpm-3237086-nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm.html"
    ).exists()


def test_cli_albs_artifact_inventory_exports_json(capsys) -> None:
    assert (
        main(
            [
                "albs-artifact-inventory",
                "--path",
                "tests/fixtures/albs-build.json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.albs.artifact_inventory.v1"
    assert payload["summary"] == {
        "architectures": 2,
        "artifacts": 4,
        "binaryRpms": 3,
        "buildLogs": 0,
        "buildTasks": 2,
        "debugArtifacts": 0,
        "packages": 2,
        "sourceRpms": 1,
    }


def test_cli_albs_build_timing_exports_json(capsys) -> None:
    assert (
        main(
            [
                "albs-build-timing",
                "--path",
                "tests/fixtures/albs-build.json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.albs.build_timing.v1"
    assert payload["summary"]["buildTasks"] == 2
    assert payload["summary"]["criticalBuildTaskWallSeconds"] == 371.070048
    assert payload["signStepTotalsSeconds"] == {
        "sign_packages_time": 22.0,
        "upload_packages_time": 187.0,
    }


def test_cli_query_albs_build_source(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--source",
                "albs-build",
                "--path",
                "tests/fixtures/albs-build.json",
                "--operation",
                "most-depended-upon",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["operation"] == "most-depended-upon"
    assert payload["result"][0] == {
        "package": "albs-release:7396",
        "dependents": 6,
    }
