"""Parallel query execution helpers for immutable CSR graph runtimes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from time import perf_counter
from typing import Mapping, Sequence

from src.core_graph.accelerators import select_traversal_backend
from src.core_graph.sparse_matrix import FrozenCSRGraph

PARALLEL_QUERY_REPORT_SCHEMA = "edgp.parallel.query.report.v1"


@dataclass(frozen=True)
class ParallelReachabilityQuery:
    """One independent reachability query against a frozen CSR graph."""

    direction: str
    node: str


def run_parallel_reachability_queries(
    graph: FrozenCSRGraph,
    queries: Sequence[ParallelReachabilityQuery | Mapping[str, str]],
    *,
    max_workers: int | None = None,
    backend: str = "python",
) -> dict[str, object]:
    """Execute independent reachability queries concurrently."""

    normalized = [_normalize_query(query) for query in queries]
    selected_backend = select_traversal_backend(backend)
    workers = max_workers or min(32, max(1, len(normalized)))
    start = perf_counter()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(
            executor.map(
                lambda query: _execute_query(
                    graph,
                    query,
                    backend=selected_backend,
                ),
                normalized,
            )
        )

    return {
        "schema": PARALLEL_QUERY_REPORT_SCHEMA,
        "summary": {
            "queries": len(normalized),
            "workers": workers,
            "backend": backend,
            "selectedBackend": selected_backend,
            "durationMs": round((perf_counter() - start) * 1000, 3),
        },
        "results": results,
    }


def _normalize_query(
    query: ParallelReachabilityQuery | Mapping[str, str]
) -> ParallelReachabilityQuery:
    if isinstance(query, ParallelReachabilityQuery):
        normalized = query
    else:
        normalized = ParallelReachabilityQuery(
            direction=str(query.get("direction", "")),
            node=str(query.get("node", "")),
        )
    if normalized.direction not in {"dependencies", "dependents"}:
        raise ValueError("parallel query direction must be dependencies or dependents")
    if not normalized.node:
        raise ValueError("parallel query node must be non-empty")
    return normalized


def _execute_query(
    graph: FrozenCSRGraph,
    query: ParallelReachabilityQuery,
    *,
    backend: str,
) -> dict[str, object]:
    if query.direction == "dependencies":
        nodes = graph.reachable_dependencies(query.node, backend=backend)
    else:
        nodes = graph.reachable_dependents(query.node, backend=backend)
    return {
        "direction": query.direction,
        "node": query.node,
        "resultKind": "nodes",
        "count": len(nodes),
        "nodes": nodes,
    }
