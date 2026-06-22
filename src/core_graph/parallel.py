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
    """One independent query against a frozen CSR graph."""

    direction: str
    node: str
    target: str | None = None
    result_kind: str = "nodes"


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
            "nodeQueries": sum(
                1 for query in normalized if query.result_kind == "nodes"
            ),
            "pathQueries": sum(
                1 for query in normalized if query.result_kind == "path"
            ),
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
            target=(
                str(query.get("target"))
                if query.get("target") is not None
                else None
            ),
            result_kind=str(query.get("resultKind", "nodes")),
        )
    if normalized.result_kind not in {"nodes", "path"}:
        raise ValueError("parallel query resultKind must be nodes or path")
    if normalized.direction not in {"dependencies", "dependents"}:
        raise ValueError("parallel query direction must be dependencies or dependents")
    if not normalized.node:
        raise ValueError("parallel query node must be non-empty")
    if normalized.result_kind == "path" and not normalized.target:
        raise ValueError("parallel path query target must be non-empty")
    return normalized


def _execute_query(
    graph: FrozenCSRGraph,
    query: ParallelReachabilityQuery,
    *,
    backend: str,
) -> dict[str, object]:
    if query.result_kind == "path":
        path = graph.shortest_dependency_path(
            query.node,
            query.target or "",
            reverse=query.direction == "dependents",
        )
        return {
            "direction": query.direction,
            "node": query.node,
            "target": query.target or "",
            "resultKind": "path",
            "count": len(path),
            "nodes": path,
        }
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
