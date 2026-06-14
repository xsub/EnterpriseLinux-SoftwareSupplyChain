"""Schemaed query reports for graph traversal results."""

from __future__ import annotations

from typing import Any

QUERY_REPORT_SCHEMA = "edgp.query.report.v1"


def build_query_report(
    query_result: dict[str, Any],
    *,
    source: str,
    root: str,
    ecosystem: str,
    limit: int,
) -> dict[str, Any]:
    """Wrap raw graph query output in a stable EDGP report contract."""

    operation = str(query_result.get("operation", "unknown"))
    result = query_result.get("result", [])
    report = {
        "schema": QUERY_REPORT_SCHEMA,
        "source": source,
        "root": root,
        "ecosystem": ecosystem,
        "operation": operation,
        "limit": limit,
        "summary": _summary(operation, result),
        "result": result if isinstance(result, list) else [],
    }
    for key in (
        "direction",
        "node",
        "requestedNode",
        "target",
        "requestedTarget",
    ):
        if key in query_result:
            report[key] = query_result[key]
    return report


def _summary(operation: str, result: object) -> dict[str, Any]:
    rows = result if isinstance(result, list) else []
    result_kind = "ranking" if operation == "most-depended-upon" else "nodes"
    if operation == "path":
        result_kind = "path"
    summary = {
        "resultCount": len(rows),
        "resultKind": result_kind,
    }
    if operation == "path":
        summary["pathFound"] = bool(rows)
    return summary
