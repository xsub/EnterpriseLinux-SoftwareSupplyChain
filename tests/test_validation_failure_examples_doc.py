"""Documentation link tests for validation failure example workflows."""

from pathlib import Path

from scripts.smoke_validate import _markdown_anchor


DOC_PATH = Path("docs/Validation Failure Examples.md")
README_PATH = Path("README.md")


def test_validation_failure_examples_quick_links_target_headings() -> None:
    lines = DOC_PATH.read_text(encoding="utf-8").splitlines()
    heading_anchors = _validation_failure_example_heading_anchors()
    quick_link_anchors = _quick_link_anchors(lines)

    assert {
        "cli-index-workflows",
        "missing-required-field",
        "tampered-report-bundle-manifest",
    } <= quick_link_anchors
    assert quick_link_anchors <= heading_anchors


def test_readme_validation_guide_anchor_links_target_headings() -> None:
    heading_anchors = _validation_failure_example_heading_anchors()
    readme_anchors = _readme_validation_guide_anchors()

    assert {"cli-index-workflows", "quick-links"} <= readme_anchors
    assert readme_anchors <= heading_anchors


def _validation_failure_example_heading_anchors() -> set[str]:
    return {
        _markdown_anchor(line.removeprefix("## "))
        for line in DOC_PATH.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    }


def _quick_link_anchors(lines: list[str]) -> set[str]:
    anchors = set()
    for line in lines:
        marker = "](#"
        if not line.startswith("- [") or marker not in line:
            continue
        anchor_start = line.index(marker) + len(marker)
        anchor_end = line.find(")", anchor_start)
        if anchor_end != -1:
            anchors.add(line[anchor_start:anchor_end])
    return anchors


def _readme_validation_guide_anchors() -> set[str]:
    anchors = set()
    for line in README_PATH.read_text(encoding="utf-8").splitlines():
        marker = "docs/Validation%20Failure%20Examples.md#"
        if marker not in line:
            continue
        anchor_start = line.index(marker) + len(marker)
        anchor_end = line.find(")", anchor_start)
        if anchor_end != -1:
            anchors.add(line[anchor_start:anchor_end])
    return anchors
