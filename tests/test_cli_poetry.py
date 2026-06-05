"""CLI tests for Poetry lockfile graph ingestion."""

import json

from src.cli import main


def test_cli_lockfile_exports_poetry_graph(capsys) -> None:
    assert (
        main(
            [
                "lockfile",
                "--ecosystem",
                "poetry",
                "--path",
                "tests/fixtures/poetry.lock",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["ecosystem"] == "pypi"
    assert payload["root"] == "poetry-lock==resolved"
    assert payload["stats"] == {"edges": 4, "nodes": 5}


def test_cli_query_poetry_lockfile_path(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--source",
                "lockfile",
                "--ecosystem",
                "poetry",
                "--path",
                "tests/fixtures/poetry.lock",
                "--operation",
                "path",
                "--node",
                "demo-lib",
                "--target",
                "urllib3",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["node"] == "demo-lib==1.0.0"
    assert payload["target"] == "urllib3==2.2.1"
    assert payload["result"] == [
        "demo-lib==1.0.0",
        "requests==2.31.0",
        "urllib3==2.2.1",
    ]
