"""Synthetic CSR performance report builder for public validation runs."""

from __future__ import annotations

from typing import Any, Sequence

from src.benchmark import run_synthetic_benchmark

PERFORMANCE_REPORT_SCHEMA = "edgp.performance.report.v1"


def build_performance_report(
    scenarios: Sequence[tuple[int, int]], *, backend: str = "python"
) -> dict[str, Any]:
    """Run deterministic benchmark scenarios and summarize CSR layout evidence."""

    results = [_result_row(nodes, fanout, backend=backend) for nodes, fanout in scenarios]
    return {
        "schema": PERFORMANCE_REPORT_SCHEMA,
        "ecosystem": "generic",
        "summary": {
            "scenarios": len(results),
            "maxNodes": max((result["nodes"] for result in results), default=0),
            "maxEdges": max((result["edges"] for result in results), default=0),
            "allContiguous": all(
                bool(result.get("storage", {}).get("cContiguous")) for result in results
            ),
            "layout": "numpy.int32.c_contiguous",
            "backend": backend,
            "selectedBackends": sorted(
                {
                    str(result.get("accelerators", {}).get("selectedBackend", "python"))
                    for result in results
                }
            ),
        },
        "results": results,
    }


def _result_row(nodes: int, fanout: int, *, backend: str) -> dict[str, Any]:
    benchmark = run_synthetic_benchmark(nodes=nodes, fanout=fanout, backend=backend)
    stats = benchmark["stats"]
    timings = benchmark["timingsMs"]
    parameters = benchmark["parameters"]
    return {
        "nodes": parameters["nodes"],
        "fanout": parameters["fanout"],
        "edges": stats["edges"],
        "reachableFromRoot": stats["reachableFromRoot"],
        "reverseReachableFromTail": stats["reverseReachableFromTail"],
        "buildMs": timings["build"],
        "freezeMs": timings["freeze"],
        "reachableMs": timings["reachable"],
        "reverseReachableMs": timings["reverseReachable"],
        "mostDependedUponMs": timings["mostDependedUpon"],
        "storage": benchmark["storage"],
        "accelerators": benchmark["accelerators"],
        "backend": parameters["backend"],
    }
