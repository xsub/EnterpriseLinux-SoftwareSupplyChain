"""CLI query tests for graph traversal over resolved lockfiles."""

import json

from src.cli import main


def test_cli_query_reachable_dependencies(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--path",
                "tests/fixtures/package-lock.json",
                "--operation",
                "reachable",
                "--node",
                "demo-app==1.0.0",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == [
        "@scope/tool==2.1.0",
        "left-pad==1.3.0",
        "nested==1.0.1",
    ]


def test_cli_query_path(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--path",
                "tests/fixtures/package-lock.json",
                "--operation",
                "path",
                "--node",
                "demo-app==1.0.0",
                "--target",
                "nested==1.0.1",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == [
        "demo-app==1.0.0",
        "@scope/tool==2.1.0",
        "nested==1.0.1",
    ]


def test_cli_query_most_depended_upon_excludes_zero_count_nodes(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--path",
                "tests/fixtures/package-lock.json",
                "--operation",
                "most-depended-upon",
                "--limit",
                "10",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == [
        {"dependents": 2, "package": "left-pad==1.3.0"},
        {"dependents": 1, "package": "@scope/tool==2.1.0"},
        {"dependents": 1, "package": "nested==1.0.1"},
    ]
