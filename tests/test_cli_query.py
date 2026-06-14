"""CLI query tests for graph traversal over resolved lockfiles."""

import json

import pytest

from src.cli import _resolve_node_selector, main
from src.core_graph.sparse_matrix import CSRDependencyGraph


def test_cli_query_reachable_dependencies(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--path",
                "tests/fixtures/package-lock.json",
                "--operation",
                "reachable",
                "--node",
                "demo-app==1.0.0",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == [
        "@scope/tool==2.1.0",
        "left-pad==1.3.0",
        "nested==1.0.1",
    ]


def test_cli_query_path(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--path",
                "tests/fixtures/package-lock.json",
                "--operation",
                "path",
                "--node",
                "demo-app",
                "--target",
                "nested",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["node"] == "demo-app==1.0.0"
    assert payload["requestedNode"] == "demo-app"
    assert payload["target"] == "nested==1.0.1"
    assert payload["requestedTarget"] == "nested"
    assert payload["result"] == [
        "demo-app==1.0.0",
        "@scope/tool==2.1.0",
        "nested==1.0.1",
    ]


def test_cli_query_bundle_writes_report_bundle(tmp_path, capsys) -> None:
    output_dir = tmp_path / "query-bundle"

    assert (
        main(
            [
                "query-bundle",
                "--path",
                "tests/fixtures/package-lock.json",
                "--operation",
                "reachable",
                "--node",
                "demo-app",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "query-report.json").read_text(encoding="utf-8"))
    html = (output_dir / "001-query-report.html").read_text(encoding="utf-8")

    assert manifest["bundle"]["sourceKind"] == "query-report"
    assert manifest["reports"][0]["schema"] == "edgp.query.report.v1"
    assert manifest["reports"][0]["href"] == "001-query-report.html"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    assert report["summary"] == {"resultCount": 3, "resultKind": "nodes"}
    assert report["requestedNode"] == "demo-app"
    assert 'data-testid="query-result-panel"' in html

    assert main(["verify-bundle", "--path", str(output_dir)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["ok"] is True


def test_cli_query_most_depended_upon_excludes_zero_count_nodes(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--path",
                "tests/fixtures/package-lock.json",
                "--operation",
                "most-depended-upon",
                "--limit",
                "10",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == [
        {"dependents": 2, "package": "left-pad==1.3.0"},
        {"dependents": 1, "package": "@scope/tool==2.1.0"},
        {"dependents": 1, "package": "nested==1.0.1"},
    ]


def test_query_selector_rejects_ambiguous_names() -> None:
    graph = CSRDependencyGraph()
    graph.add_vertex("lib==1.0.0")
    graph.add_vertex("lib==2.0.0")

    with pytest.raises(ValueError, match="Ambiguous node selector"):
        _resolve_node_selector(graph, "lib", role="node")
