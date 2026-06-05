"""HTML report tests for EDGP graph snapshots."""

import json
from pathlib import Path

from src.output.html_report import render_snapshot_report, write_snapshot_report_file


def test_render_snapshot_report_includes_summary_graph_and_tables() -> None:
    snapshot = json.loads(Path("tests/fixtures/snapshot-right.json").read_text())

    html = render_snapshot_report(snapshot)

    assert "<!doctype html>" in html
    assert "EDGP Snapshot Report - app==1.0.0" in html
    assert 'data-testid="graph-panel"' in html
    assert "lib==2.0.0" in html
    assert "Most Depended Upon" in html


def test_write_snapshot_report_file_writes_html(tmp_path) -> None:
    output_path = tmp_path / "report.html"

    returned = write_snapshot_report_file(
        Path("tests/fixtures/snapshot-right.json"),
        output_path,
    )

    assert returned == output_path
    assert output_path.read_text(encoding="utf-8").startswith("<!doctype html>")
