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


def test_cli_ingest_requirements_outputs_pypi_graph(capsys) -> None:
    assert (
        main(
            [
                "ingest",
                "requirements",
                "tests/fixtures/pypi/requirements.txt",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["ecosystem"] == "pypi"
    assert payload["root"] == "requirements==resolved"
    assert any(node.get("purl") == "pkg:pypi/requests@2.31.0" for node in payload["nodes"])


def test_cli_ingest_pyproject_outputs_scoped_dependencies(capsys) -> None:
    assert (
        main(
            [
                "ingest",
                "pyproject",
                "tests/fixtures/pypi/pyproject.toml",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["root"] == "python-demo==1.0.0"
    edge = next(
        edge
        for edge in payload["edges"]
        if edge["source"] == "python-demo==1.0.0"
        and edge["target"] == "pytest==8.2.0"
    )
    assert edge["scope"] == "dev"


def test_cli_export_cyclonedx_from_requirements(capsys) -> None:
    assert (
        main(
            [
                "export",
                "cyclonedx",
                "--source",
                "requirements",
                "--path",
                "tests/fixtures/pypi/requirements.txt",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["bomFormat"] == "CycloneDX"
    assert any(
        component.get("purl") == "pkg:pypi/requests@2.31.0"
        for component in payload["components"]
    )
