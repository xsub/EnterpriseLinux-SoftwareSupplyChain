"""CLI tests for local HTML EDGP JSON reports."""

from pathlib import Path

from src.cli import main


def test_cli_report_writes_html_snapshot_report(tmp_path, capsys) -> None:
    output_path = tmp_path / "snapshot-report.html"

    assert (
        main(
            [
                "report",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_path
    html = output_path.read_text(encoding="utf-8")
    assert 'data-testid="report-hero"' in html
    assert "core==1.0.0" in html


def test_cli_report_writes_html_impact_report_from_input(tmp_path, capsys) -> None:
    output_path = tmp_path / "impact-report.html"

    assert (
        main(
            [
                "report",
                "--input",
                "tests/fixtures/impact-report.json",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_path
    html = output_path.read_text(encoding="utf-8")
    assert 'data-testid="impact-chains-panel"' in html
    assert "left-pad==1.3.0" in html


def test_cli_report_writes_html_advisory_report_from_input(tmp_path, capsys) -> None:
    output_path = tmp_path / "advisory-report.html"

    assert (
        main(
            [
                "report",
                "--input",
                "tests/fixtures/advisory-report.json",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_path
    html = output_path.read_text(encoding="utf-8")
    assert 'data-testid="advisory-findings-panel"' in html
    assert "ADV-LOCAL-0001" in html


def test_cli_report_writes_html_npm_diagnostics_report_from_input(
    tmp_path, capsys
) -> None:
    output_path = tmp_path / "npm-diagnostics-report.html"

    assert (
        main(
            [
                "report",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_path
    html = output_path.read_text(encoding="utf-8")
    assert 'data-testid="npm-conflicts-panel"' in html
    assert 'data-testid="npm-unresolved-panel"' in html
    assert "missing" in html
