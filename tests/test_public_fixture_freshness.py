"""Freshness checks for public-derived report fixtures."""

import json
from pathlib import Path

from scripts.generate_public_fixture_reports import (
    build_public_fixture_reports,
    main,
)


def _fixture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_derived_report_fixtures_match_generators() -> None:
    expected = build_public_fixture_reports()

    for fixture_path, generated in expected.items():
        assert _fixture(fixture_path) == generated, str(fixture_path)


def test_public_fixture_report_generator_check_mode_passes() -> None:
    assert main(["--check"]) == 0
