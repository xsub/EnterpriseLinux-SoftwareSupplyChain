"""Tests for top-level Python translation unit descriptions."""

from scripts.smoke_validate import (
    REPO_ROOT,
    _assert_python_translation_unit_docstrings,
    _python_translation_unit_paths,
)


def test_python_translation_units_have_top_level_descriptions() -> None:
    roots = {
        path.relative_to(REPO_ROOT).parts[0]
        for path in _python_translation_unit_paths()
    }

    assert {"src", "scripts", "tests"} <= roots
    _assert_python_translation_unit_docstrings()
