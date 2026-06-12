"""Shared graph bundle helper tests."""

import json

from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.output.graph_bundle import write_graph_report_bundle
from src.output.report_bundle import verify_report_bundle


def test_write_graph_report_bundle_writes_graph_impact_and_manifest(tmp_path) -> None:
    graph = CSRDependencyGraph()
    graph.add_vertex("app==1.0.0", metadata={"ecosystem": "generic"})
    graph.add_vertex("lib==2.0.0", metadata={"ecosystem": "generic"})
    graph.add_dependency_edge("app==1.0.0", "lib==2.0.0")
    resolved = ResolvedProjectGraph(
        root_identifier="app==1.0.0",
        graph=graph,
        ecosystem="generic",
    )

    index_path = write_graph_report_bundle(
        resolved,
        tmp_path,
        graph_name="generic-graph",
        impact_nodes=["lib"],
        node_resolver=lambda graph, selector: "lib==2.0.0",
        bundle_metadata={"sourceKind": "test-graph", "command": "edgp test"},
    )

    assert index_path == tmp_path / "index.html"
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"] == {
        "command": "edgp test",
        "sourceKind": "test-graph",
    }
    assert [report["href"] for report in manifest["reports"]] == [
        "001-generic-graph.html",
        "002-impact-lib-2.0.0.html",
    ]
    impact = json.loads((tmp_path / "impact-lib-2.0.0.json").read_text(encoding="utf-8"))
    assert impact["node"] == "lib==2.0.0"
    assert impact["summary"]["affectedDependents"] == 1


def test_write_graph_report_bundle_can_include_triage_summary(tmp_path) -> None:
    graph = CSRDependencyGraph()
    graph.add_vertex("app==1.0.0", metadata={"ecosystem": "generic"})
    graph.add_vertex("lib==2.0.0", metadata={"ecosystem": "generic"})
    graph.add_dependency_edge("app==1.0.0", "lib==2.0.0")
    resolved = ResolvedProjectGraph(
        root_identifier="app==1.0.0",
        graph=graph,
        ecosystem="generic",
    )

    write_graph_report_bundle(
        resolved,
        tmp_path,
        graph_name="generic-graph",
        bundle_metadata={"sourceKind": "dot", "command": "edgp dot-bundle"},
        include_triage_summary=True,
    )

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reportCount"] == 1
    assert manifest["triageSummary"]["href"] == "triage-summary.html"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    triage = json.loads((tmp_path / "triage-summary.json").read_text(encoding="utf-8"))
    assert triage["schema"] == "edgp.triage.summary.v1"
    assert triage["status"] == "pass"
    assert triage["summary"]["reports"] == 1
    assert verify_report_bundle(tmp_path)["ok"] is True
