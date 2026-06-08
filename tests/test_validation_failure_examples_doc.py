"""Documentation link tests for public workflow guides."""

from pathlib import Path
from urllib.parse import unquote

from scripts.smoke_validate import (
    ARCHITECTURE_DOC_PATH,
    REPORT_SCHEMA_DOC_PATHS,
    _architecture_doc_heading_anchors,
    _markdown_heading_anchors,
    _markdown_link_anchors,
    _markdown_links_to_anchor,
    _markdown_path_links,
)


DOC_PATH = Path("docs/Validation Failure Examples.md")
README_PATH = Path("README.md")


def test_validation_failure_examples_quick_links_target_headings() -> None:
    lines = DOC_PATH.read_text(encoding="utf-8").splitlines()
    heading_anchors = _markdown_heading_anchors(lines)
    quick_link_anchors = set(_markdown_link_anchors(lines))

    assert {
        "cli-index-workflows",
        "missing-required-field",
        "tampered-report-bundle-manifest",
    } <= quick_link_anchors
    assert quick_link_anchors <= heading_anchors


def test_validation_failure_examples_local_links_target_committed_files() -> None:
    guide_paths = set(
        _markdown_path_links(DOC_PATH.read_text(encoding="utf-8").splitlines())
    )

    assert guide_paths
    for path in guide_paths:
        assert (DOC_PATH.parent / unquote(path)).exists()


def test_readme_validation_guide_anchor_links_target_headings() -> None:
    heading_anchors = _markdown_heading_anchors(
        DOC_PATH.read_text(encoding="utf-8").splitlines()
    )
    readme_anchors = set(
        _markdown_links_to_anchor(
            README_PATH.read_text(encoding="utf-8").splitlines(),
            "docs/Validation%20Failure%20Examples.md#",
        )
    )

    assert {"cli-index-workflows", "quick-links"} <= readme_anchors
    assert readme_anchors <= heading_anchors


def test_readme_validation_failure_fixture_links_target_committed_files() -> None:
    readme_paths = set(
        _markdown_path_links(README_PATH.read_text(encoding="utf-8").splitlines())
    )
    linked_paths = {
        "docs/validation-failure-example-index.json",
        "docs/validation-failure-example-filters.json",
    }

    assert linked_paths <= readme_paths
    for path in linked_paths:
        assert Path(path).exists()


def test_readme_architecture_research_link_targets_committed_doc() -> None:
    readme_paths = set(
        _markdown_path_links(README_PATH.read_text(encoding="utf-8").splitlines())
    )
    architecture_path = (
        "docs/Architecture%20and%20Traversal%20of%20Massive-Scale%20"
        "Dependency%20Graphs.md"
    )

    assert architecture_path in readme_paths
    assert Path(unquote(architecture_path)).exists()


def test_readme_architecture_research_anchor_links_target_headings() -> None:
    readme_anchors = set(
        _markdown_links_to_anchor(
            README_PATH.read_text(encoding="utf-8").splitlines(),
            "docs/Architecture%20and%20Traversal%20of%20Massive-Scale%20"
            "Dependency%20Graphs.md#",
        )
    )

    assert {
        "memory-optimization-and-sparse-matrix-representations",
        "algorithmic-resolution-of-software-dependency-graphs",
    } <= readme_anchors
    assert readme_anchors <= _architecture_doc_heading_anchors()


def test_readme_local_documentation_links_target_committed_files() -> None:
    readme_paths = set(
        _markdown_path_links(README_PATH.read_text(encoding="utf-8").splitlines())
    )

    assert readme_paths
    for path in readme_paths:
        assert Path(unquote(path)).exists()


def test_report_schema_docs_local_links_target_committed_files() -> None:
    for doc_path in REPORT_SCHEMA_DOC_PATHS:
        schema_doc_paths = set(
            _markdown_path_links(doc_path.read_text(encoding="utf-8").splitlines())
        )

        assert schema_doc_paths
        for path in schema_doc_paths:
            assert (doc_path.parent / unquote(path)).exists()


def test_architecture_doc_local_links_target_committed_files() -> None:
    architecture_paths = set(
        _markdown_path_links(
            ARCHITECTURE_DOC_PATH.read_text(encoding="utf-8").splitlines()
        )
    )

    assert architecture_paths
    for path in architecture_paths:
        assert (ARCHITECTURE_DOC_PATH.parent / unquote(path)).exists()


def test_architecture_doc_headings_generate_expected_anchors() -> None:
    lines = ARCHITECTURE_DOC_PATH.read_text(encoding="utf-8").splitlines()
    title_anchors = _markdown_heading_anchors(lines, level="# ")
    section_anchors = _markdown_heading_anchors(lines, level="## ")
    subsection_anchors = _markdown_heading_anchors(lines, level="### ")

    assert title_anchors == {
        "architecture-and-traversal-of-massive-scale-dependency-graphs"
    }
    assert {
        "the-imperative-of-massive-scale-graph-architectures",
        "memory-optimization-and-sparse-matrix-representations",
        "algorithmic-resolution-of-software-dependency-graphs",
        "conclusion",
    } <= section_anchors
    assert {
        "compressed-sparse-row-and-compressed-sparse-column-formats",
        "pubgrub-and-conflict-driven-clause-learning",
    } <= subsection_anchors


def test_markdown_path_links_return_local_targets_without_fragments() -> None:
    links = _markdown_path_links(
        [
            "[Guide](docs/Validation%20Failure%20Examples.md#quick-links)",
            "[Anchor](#quick-links)",
            "[External](https://example.invalid/docs)",
            "![Screenshot](docs/report.png)",
            "[Fixture](docs/validation-failure-example-index.json)",
        ]
    )

    assert links == [
        "docs/Validation%20Failure%20Examples.md",
        "docs/validation-failure-example-index.json",
    ]
