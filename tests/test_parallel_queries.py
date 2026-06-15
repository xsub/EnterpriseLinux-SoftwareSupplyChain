"""Parallel reachability query tests for frozen CSR graph runtimes."""

import pytest

from src.core_graph.parallel import (
    ParallelReachabilityQuery,
    run_parallel_reachability_queries,
)
from src.core_graph.sparse_matrix import CSRDependencyGraph


def test_parallel_reachability_queries_preserve_input_order() -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    graph.add_dependency_edge("lib==1.0.0", "base==1.0.0")
    frozen = graph.freeze()

    report = run_parallel_reachability_queries(
        frozen,
        [
            ParallelReachabilityQuery("dependencies", "app==1.0.0"),
            ParallelReachabilityQuery("dependents", "base==1.0.0"),
        ],
        max_workers=2,
        backend="auto",
    )

    assert report["schema"] == "edgp.parallel.query.report.v1"
    assert report["summary"]["queries"] == 2
    assert report["summary"]["workers"] == 2
    assert report["summary"]["backend"] == "auto"
    assert report["results"] == [
        {
            "direction": "dependencies",
            "node": "app==1.0.0",
            "resultKind": "nodes",
            "count": 2,
            "nodes": ["lib==1.0.0", "base==1.0.0"],
        },
        {
            "direction": "dependents",
            "node": "base==1.0.0",
            "resultKind": "nodes",
            "count": 2,
            "nodes": ["lib==1.0.0", "app==1.0.0"],
        },
    ]


def test_parallel_reachability_rejects_unknown_direction() -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")

    with pytest.raises(ValueError, match="direction"):
        run_parallel_reachability_queries(
            graph.freeze(),
            [{"direction": "sideways", "node": "app==1.0.0"}],
        )
