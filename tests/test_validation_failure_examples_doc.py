"""Documentation link tests for validation failure example workflows."""

from pathlib import Path
from urllib.parse import unquote

from scripts.smoke_validate import (
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


def test_readme_local_documentation_links_target_committed_files() -> None:
    readme_paths = set(
        _markdown_path_links(README_PATH.read_text(encoding="utf-8").splitlines())
    )

    assert readme_paths
    for path in readme_paths:
        assert Path(unquote(path)).exists()


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
