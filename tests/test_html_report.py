"""HTML report tests for EDGP JSON analysis documents."""

import json
from pathlib import Path

from src.output.html_report import render_report, render_snapshot_report, write_report_file


def test_render_snapshot_report_includes_summary_graph_and_tables() -> None:
    snapshot = json.loads(Path("tests/fixtures/snapshot-right.json").read_text())

    html = render_snapshot_report(snapshot)

    assert "<!doctype html>" in html
    assert "EDGP Snapshot Report - app==1.0.0" in html
    assert 'data-testid="graph-panel"' in html
    assert 'data-testid="edge-filter-panel"' in html
    assert 'data-edge-filter-search' in html
    assert 'data-edge-filter-count' in html
    assert 'data-edge-type="1"' in html
    assert "lib==2.0.0" in html
    assert "Most Depended Upon" in html


def test_render_snapshot_report_labels_maven_relationship_types() -> None:
    snapshot = {
        "schema": "edgp.graph.snapshot.v1",
        "ecosystem": "maven",
        "root": "app==1.0.0",
        "stats": {"nodes": 3, "edges": 2},
        "nodes": [
            {"id": "app==1.0.0", "dependencies": [], "dependents": [], "metadata": {}},
            {
                "id": "optional==1.0.0",
                "dependencies": [],
                "dependents": [],
                "metadata": {"optional": "true"},
            },
            {
                "id": "omitted==1.0.0",
                "dependencies": [],
                "dependents": [],
                "metadata": {"omitted": "true"},
            },
        ],
        "edges": [
            {
                "source": "app==1.0.0",
                "target": "optional==1.0.0",
                "relationshipType": 2,
            },
            {
                "source": "app==1.0.0",
                "target": "omitted==1.0.0",
                "relationshipType": 3,
            },
        ],
        "rankings": {"mostDependedUpon": []},
    }

    html = render_snapshot_report(snapshot)

    assert 'data-testid="edge-relationship-panel"' in html
    assert 'data-testid="edge-filter-panel"' in html
    assert 'data-edge-type="2"' in html
    assert 'data-edge-type="3"' in html
    assert "2 - Maven Optional" in html
    assert "3 - Maven Omitted" in html


def test_write_snapshot_report_file_writes_html(tmp_path) -> None:
    output_path = tmp_path / "report.html"

    returned = write_report_file(
        Path("tests/fixtures/snapshot-right.json"),
        output_path,
    )

    assert returned == output_path
    assert output_path.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_render_report_supports_impact_json() -> None:
    report = json.loads(Path("tests/fixtures/impact-report.json").read_text())

    html = render_report(report)

    assert "EDGP Impact Report - left-pad==1.3.0" in html
    assert 'data-testid="impact-chains-panel"' in html
    assert "@scope/tool==2.1.0 -&gt; left-pad==1.3.0" in html


def test_render_report_supports_advisory_json() -> None:
    report = json.loads(Path("tests/fixtures/advisory-report.json").read_text())

    html = render_report(report)

    assert "EDGP Advisory Report - demo-app==1.0.0" in html
    assert 'data-testid="advisory-findings-panel"' in html
    assert "ADV-LOCAL-0001" in html


def test_render_report_supports_npm_diagnostics_json() -> None:
    report = json.loads(Path("tests/fixtures/npm-diagnostics-report.json").read_text())

    html = render_report(report)

    assert "EDGP npm Diagnostics - conflict-app==1.0.0" in html
    assert 'data-testid="npm-conflicts-panel"' in html
    assert "shared==2.0.0" in html
    assert "node_modules/tool/node_modules/shared" in html
    assert "missing" in html
