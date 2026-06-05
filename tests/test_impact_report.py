"""Impact report tests for reverse dependency reachability."""

from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.impact_report import build_impact_report


def test_build_impact_report_returns_reverse_chains_to_node() -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "tool==2.0.0")
    graph.add_dependency_edge("tool==2.0.0", "vulnerable==1.2.3")
    graph.add_dependency_edge("sidecar==1.0.0", "vulnerable==1.2.3")

    payload = build_impact_report(
        graph,
        node="vulnerable==1.2.3",
        root="app==1.0.0",
        ecosystem="generic",
    )

    assert payload["schema"] == "edgp.impact.report.v1"
    assert payload["summary"] == {
        "directDependents": 2,
        "affectedDependents": 3,
        "directDependencies": 0,
        "renderedChains": 3,
        "truncatedChains": 0,
    }
    assert payload["directDependents"] == ["sidecar==1.0.0", "tool==2.0.0"]
    assert payload["affectedDependents"] == [
        {"distance": 1, "package": "sidecar==1.0.0"},
        {"distance": 1, "package": "tool==2.0.0"},
        {"distance": 2, "package": "app==1.0.0"},
    ]
    assert payload["dependencyChainsToNode"][2]["path"] == [
        "app==1.0.0",
        "tool==2.0.0",
        "vulnerable==1.2.3",
    ]


def test_build_impact_report_limits_rendered_chains() -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    graph.add_dependency_edge("tool==1.0.0", "lib==1.0.0")

    payload = build_impact_report(graph, node="lib==1.0.0", max_paths=1)

    assert payload["summary"]["affectedDependents"] == 2
    assert payload["summary"]["renderedChains"] == 1
    assert payload["summary"]["truncatedChains"] == 1
