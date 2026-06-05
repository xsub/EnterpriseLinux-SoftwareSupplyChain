"""CLI tests for DOT graph export and traversal."""

import json

from src.cli import main


def test_cli_dot_snapshot(capsys) -> None:
    assert (
        main(
            [
                "dot",
                "--path",
                "tests/fixtures/repograph.dot",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "rpm"
    assert payload["stats"] == {"edges": 5, "nodes": 4}


def test_cli_query_dot_dependents(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--source",
                "dot",
                "--path",
                "tests/fixtures/repograph.dot",
                "--ecosystem",
                "rpm",
                "--operation",
                "dependents",
                "--node",
                "glibc",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["direction"] == "dependents"
    assert payload["node"] == "glibc==unknown"
    assert payload["requestedNode"] == "glibc"
    assert payload["result"] == [
        "nginx-core==unknown",
        "openssl-libs==unknown",
        "curl==unknown",
    ]
