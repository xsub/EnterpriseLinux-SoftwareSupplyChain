"""CLI tests for CycloneDX SBOM graph ingestion."""

import json

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
