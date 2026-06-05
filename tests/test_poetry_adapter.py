"""Poetry lockfile adapter tests for Python dependency graph ingestion."""

from pathlib import Path

from src.adapters.poetry import PoetryAdapter


def test_poetry_lockfile_builds_resolved_graph() -> None:
    resolved = PoetryAdapter().parse_lockfile_graph(Path("tests/fixtures/poetry.lock"))

    assert resolved.root_identifier == "poetry-lock==resolved"
    assert resolved.ecosystem == "pypi"
    assert resolved.graph.get_dependencies("poetry-lock==resolved") == [
        "demo-lib==1.0.0"
    ]
    assert resolved.graph.get_dependencies("demo-lib==1.0.0") == [
        "requests==2.31.0"
    ]
    assert resolved.graph.get_dependencies("requests==2.31.0") == [
        "certifi==2024.2.2",
        "urllib3==2.2.1",
    ]
    assert resolved.graph.get_vertex_metadata("requests==2.31.0") == {
        "ecosystem": "pypi",
        "source": "poetry.lock",
        "category": "main",
        "groups": "['main']",
        "optional": "False",
        "python_versions": ">=3.7",
    }
