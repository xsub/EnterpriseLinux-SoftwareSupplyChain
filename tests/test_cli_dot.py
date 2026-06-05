"""CLI tests for DOT graph export and traversal."""

import json
from pathlib import Path

from src.cli import main


def test_cli_dot_snapshot(capsys) -> None:
    assert (
        main(
            [
                "dot",
                "--path",
                "tests/fixtures/repograph.dot",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "rpm"
    assert payload["stats"] == {"edges": 5, "nodes": 4}


def test_cli_query_dot_dependents(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--source",
                "dot",
                "--path",
                "tests/fixtures/repograph.dot",
                "--ecosystem",
                "rpm",
                "--operation",
                "dependents",
                "--node",
                "glibc",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["direction"] == "dependents"
    assert payload["node"] == "glibc==unknown"
    assert payload["requestedNode"] == "glibc"
    assert payload["result"] == [
        "nginx-core==unknown",
        "openssl-libs==unknown",
        "curl==unknown",
    ]


def test_cli_dot_bundle_writes_graph_and_impact_reports(tmp_path, capsys) -> None:
    output_dir = tmp_path / "dot-bundle"

    assert (
        main(
            [
                "dot-bundle",
                "--path",
                "tests/fixtures/repograph.dot",
                "--ecosystem",
                "rpm",
                "--impact-node",
                "glibc",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    graph = json.loads((output_dir / "dot-graph.json").read_text(encoding="utf-8"))
    impact = json.loads(
        (output_dir / "impact-glibc-unknown.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert graph["schema"] == "edgp.graph.snapshot.v1"
    assert graph["ecosystem"] == "rpm"
    assert impact["schema"] == "edgp.impact.report.v1"
    assert impact["node"] == "glibc==unknown"
    assert manifest["bundle"]["sourceKind"] == "dot"
    assert manifest["bundle"]["command"].startswith("edgp dot-bundle ")
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.impact.report.v1",
    ]
    graph_html = (output_dir / "001-dot-graph.html").read_text(encoding="utf-8")
    assert "glibc==unknown" in graph_html
    assert (output_dir / "002-impact-glibc-unknown.html").exists()
