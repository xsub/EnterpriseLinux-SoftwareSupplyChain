"""Documentation link tests for validation failure example workflows."""

from pathlib import Path

from scripts.smoke_validate import (
    _markdown_heading_anchors,
    _markdown_link_anchors,
    _markdown_links_to_anchor,
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
    readme_text = README_PATH.read_text(encoding="utf-8")
    linked_paths = {
        "docs/validation-failure-example-index.json",
        "docs/validation-failure-example-filters.json",
    }

    for path in linked_paths:
        assert path in readme_text
        assert Path(path).exists()
