"""Synthetic CSR graph benchmarks for dependency traversal smoke checks."""

from __future__ import annotations

from time import perf_counter

from src.core_graph.sparse_matrix import CSRDependencyGraph


def run_synthetic_benchmark(*, nodes: int = 1000, fanout: int = 3) -> dict[str, object]:
    if nodes < 1:
        raise ValueError("nodes must be at least 1")
    if fanout < 0:
        raise ValueError("fanout must be non-negative")

    build_start = perf_counter()
    graph, edge_count = _build_synthetic_graph(nodes=nodes, fanout=fanout)
    build_ms = _elapsed_ms(build_start)

    reachable_start = perf_counter()
    reachable = graph.reachable_dependencies("pkg0==1.0.0")
    reachable_ms = _elapsed_ms(reachable_start)

    reverse_reachable_start = perf_counter()
    reverse_reachable = graph.reachable_dependents(f"pkg{nodes - 1}==1.0.0")
    reverse_reachable_ms = _elapsed_ms(reverse_reachable_start)

    ranking_start = perf_counter()
    ranking = graph.most_depended_upon(limit=10)
    ranking_ms = _elapsed_ms(ranking_start)

    return {
        "schema": "edgp.benchmark.v1",
        "parameters": {
            "nodes": nodes,
            "fanout": fanout,
        },
        "stats": {
            "nodes": len(graph),
            "edges": edge_count,
            "reachableFromRoot": len(reachable),
            "reverseReachableFromTail": len(reverse_reachable),
        },
        "timingsMs": {
            "build": build_ms,
            "reachable": reachable_ms,
            "reverseReachable": reverse_reachable_ms,
            "mostDependedUpon": ranking_ms,
        },
        "storage": graph.storage_profile(),
        "mostDependedUpon": [
            {"package": package_id, "dependents": count}
            for package_id, count in ranking
        ],
    }


def _build_synthetic_graph(
    *, nodes: int, fanout: int
) -> tuple[CSRDependencyGraph, int]:
    graph = CSRDependencyGraph()
    for index in range(nodes):
        graph.add_vertex(f"pkg{index}==1.0.0", metadata={"ecosystem": "synthetic"})

    edge_count = 0
    for source in range(nodes):
        for offset in range(1, fanout + 1):
            target = source + offset
            if target >= nodes:
                break
            graph.add_dependency_edge(
                f"pkg{source}==1.0.0",
                f"pkg{target}==1.0.0",
            )
            edge_count += 1
    return graph, edge_count


def _elapsed_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 3)
