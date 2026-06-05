"""CLI tests for local HTML graph snapshot reports."""

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
