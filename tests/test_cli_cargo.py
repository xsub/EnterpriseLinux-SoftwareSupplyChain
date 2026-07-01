"""CLI tests for Cargo lockfile graph ingestion."""

import json

from src.cli import main


def test_cli_lockfile_exports_cargo_graph(capsys) -> None:
    assert (
        main(
            [
                "lockfile",
                "--ecosystem",
                "cargo",
                "--path",
                "tests/fixtures/Cargo.lock",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["ecosystem"] == "cargo"
    assert payload["root"] == "cargo-lock==resolved"
    assert payload["stats"] == {"edges": 4, "nodes": 5}


def test_cli_query_cargo_lockfile_path(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--source",
                "lockfile",
                "--ecosystem",
                "cargo",
                "--path",
                "tests/fixtures/Cargo.lock",
                "--operation",
                "path",
                "--node",
                "demo-crate",
                "--target",
                "pin-project-lite",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["node"] == "demo-crate==0.1.0"
    assert payload["target"] == "pin-project-lite==0.2.13"
    assert payload["result"] == [
        "demo-crate==0.1.0",
        "tokio==1.36.0",
        "pin-project-lite==0.2.13",
    ]


def test_cli_ingest_cargo_lock_outputs_normalized_graph(capsys) -> None:
    assert main(["ingest", "cargo-lock", "tests/fixtures/Cargo.lock"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ecosystem"] == "cargo"
    assert payload["root"] == "cargo-lock==resolved"
    assert any(node.get("purl") == "pkg:cargo/tokio@1.36.0" for node in payload["nodes"])


def test_cli_export_cyclonedx_from_cargo_lock(capsys) -> None:
    assert (
        main(
            [
                "export",
                "cyclonedx",
                "--source",
                "cargo-lock",
                "--path",
                "tests/fixtures/Cargo.lock",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["bomFormat"] == "CycloneDX"
    assert any(
        component.get("purl") == "pkg:cargo/tokio@1.36.0"
        for component in payload["components"]
    )
