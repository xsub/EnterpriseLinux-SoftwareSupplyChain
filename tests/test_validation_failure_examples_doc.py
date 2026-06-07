"""Documentation link tests for validation failure example workflows."""

from pathlib import Path

from scripts.smoke_validate import _markdown_anchor


DOC_PATH = Path("docs/Validation Failure Examples.md")


def test_validation_failure_examples_quick_links_target_headings() -> None:
    lines = DOC_PATH.read_text(encoding="utf-8").splitlines()
    heading_anchors = {
        _markdown_anchor(line.removeprefix("## "))
        for line in lines
        if line.startswith("## ")
    }
    quick_link_anchors = _quick_link_anchors(lines)

    assert {
        "cli-index-workflows",
        "missing-required-field",
        "tampered-report-bundle-manifest",
    } <= quick_link_anchors
    assert quick_link_anchors <= heading_anchors


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
