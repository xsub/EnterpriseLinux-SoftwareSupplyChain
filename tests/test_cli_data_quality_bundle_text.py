"""CLI text-output coverage for data-quality report bundles."""

import json
from pathlib import Path

import pytest

from src.cli import main as cli_main


@pytest.mark.parametrize(
    ("command_args", "output_name", "source_kind"),
    [
        (
            ["fixture-provenance-bundle", "--fixture-dir", "tests/fixtures"],
            "fixture-provenance-bundle",
            "fixture-provenance",
        ),
        (
            ["real-data-coverage-bundle", "--fixture-dir", "tests/fixtures"],
            "real-data-coverage-bundle",
            "real-data-coverage",
        ),
        (
            ["real-data-replacement-plan-bundle", "--fixture-dir", "tests/fixtures"],
            "real-data-replacement-plan-bundle",
            "real-data-replacement-plan",
        ),
        (
            [
                "real-data-replacement-plan-diff-bundle",
                "--left",
                "tests/fixtures/real-data-replacement-plan.json",
                "--right",
                "tests/fixtures/real-data-replacement-plan.json",
            ],
            "real-data-replacement-plan-diff-bundle",
            "real-data-replacement-plan-diff",
        ),
        (
            [
                "real-data-coverage-diff-bundle",
                "--left",
                "tests/fixtures/real-data-coverage.json",
                "--right",
                "tests/fixtures/real-data-coverage.json",
            ],
            "real-data-coverage-diff-bundle",
            "real-data-coverage-diff",
        ),
    ],
)
def test_data_quality_bundle_commands_emit_text_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    command_args: list[str],
    output_name: str,
    source_kind: str,
) -> None:
    output_dir = tmp_path / output_name

    assert (
        cli_main(
            [
                *command_args,
                "--output-dir",
                str(output_dir),
                "--triage-summary",
                "--format",
                "text",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out.strip()
    assert output.startswith("BUNDLE ")
    assert f"index={output_dir / 'index.html'}" in output
    assert f"sourceKind={source_kind}" in output
    assert "reports=1" in output
    assert "bundleSha256=" in output
    assert "triageStatus=pass" in output

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == source_kind
    assert manifest["reportCount"] == 1
    assert (output_dir / "triage-summary.json").exists()
