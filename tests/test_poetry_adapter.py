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
    metadata = resolved.graph.get_vertex_metadata("requests==2.31.0")
    assert metadata["ecosystem"] == "pypi"
    assert metadata["source"] == "poetry.lock"
    assert metadata["package_manager"] == "poetry"
    assert metadata["purl"] == "pkg:pypi/requests@2.31.0"
    assert metadata["dependency_scope"] == "runtime"
    assert metadata["category"] == "main"
    assert metadata["groups"] == "['main']"
    assert metadata["optional"] == "False"
    assert metadata["python_versions"] == ">=3.7"
    assert resolved.graph.get_edge_metadata("requests==2.31.0", "urllib3==2.2.1")[
        "constraint"
    ] == ">=1.21.1,<3"


def test_requirements_txt_builds_normalized_pypi_graph() -> None:
    resolved = PoetryAdapter().parse_lockfile_graph(
        Path("tests/fixtures/pypi/requirements.txt")
    )

    assert resolved.root_identifier == "requirements==resolved"
    assert resolved.ecosystem == "pypi"
    assert resolved.graph.get_dependencies("requirements==resolved") == [
        "requests==2.31.0",
        "urllib3==>=2.2",
        "demo-wheel==https://example.com/packages/demo_wheel-1.0.0-py3-none-any.whl",
    ]
    requests = resolved.graph.get_vertex_metadata("requests==2.31.0")
    assert requests["purl"] == "pkg:pypi/requests@2.31.0"
    assert requests["checksum"] == "sha256:requirements-requests"
    assert requests["package_manager"] == "pip"
    urllib3_edge = resolved.graph.get_edge_metadata(
        "requirements==resolved",
        "urllib3==>=2.2",
    )
    assert urllib3_edge["constraint"] == ">=2.2"
    assert urllib3_edge["scope"] == "runtime"
    demo = resolved.graph.get_vertex_metadata(
        "demo-wheel==https://example.com/packages/demo_wheel-1.0.0-py3-none-any.whl"
    )
    assert demo["source_url"] == (
        "https://example.com/packages/demo_wheel-1.0.0-py3-none-any.whl"
    )
    assert demo["artifact_type"] == "wheel"


def test_requirements_filename_classifies_dev_scope() -> None:
    resolved = PoetryAdapter().parse_lockfile_graph(
        Path("tests/fixtures/pypi/requirements-dev.txt")
    )

    assert resolved.graph.get_vertex_metadata("pytest==8.2.0")[
        "dependency_scope"
    ] == "dev"
    assert resolved.graph.get_edge_metadata("requirements-dev==resolved", "pytest==8.2.0")[
        "scope"
    ] == "dev"


def test_pyproject_builds_project_and_optional_dependency_graph() -> None:
    resolved = PoetryAdapter().parse_lockfile_graph(
        Path("tests/fixtures/pypi/pyproject.toml")
    )

    assert resolved.root_identifier == "python-demo==1.0.0"
    assert resolved.graph.get_dependencies("python-demo==1.0.0") == [
        "pytest==8.2.0",
        "requests==2.31.0",
        "urllib3==>=2.2",
        "responses==0.25.0",
    ]
    pytest = resolved.graph.get_vertex_metadata("pytest==8.2.0")
    assert pytest["purl"] == "pkg:pypi/pytest@8.2.0"
    assert pytest["dependency_scope"] == "dev"
    responses_edge = resolved.graph.get_edge_metadata(
        "python-demo==1.0.0",
        "responses==0.25.0",
    )
    assert responses_edge["scope"] == "test"
    assert responses_edge["dependency_group"] == "test"
