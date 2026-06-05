"""Local advisory overlay reports for public vulnerability-style analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.impact_report import build_impact_report


def build_advisory_report_from_file(
    advisory_path: Path,
    graph: CSRDependencyGraph,
    *,
    root: str | None = None,
    ecosystem: str = "generic",
    max_paths: int = 20,
) -> dict[str, object]:
    payload = json.loads(advisory_path.read_text(encoding="utf-8"))
    return build_advisory_report(
        payload,
        graph,
        root=root,
        ecosystem=ecosystem,
        max_paths=max_paths,
    )


def build_advisory_report(
    advisory_payload: object,
    graph: CSRDependencyGraph,
    *,
    root: str | None = None,
    ecosystem: str = "generic",
    max_paths: int = 20,
) -> dict[str, object]:
    advisories = _extract_advisories(advisory_payload)
    findings = []
    affected_dependents: set[str] = set()

    for advisory in sorted(advisories, key=_advisory_sort_key):
        for package_id in sorted(graph.vertex_map):
            if not _matches_advisory(advisory, package_id, ecosystem):
                continue
            impact = build_impact_report(
                graph,
                node=package_id,
                root=root,
                ecosystem=ecosystem,
                max_paths=max_paths,
            )
            for affected in impact["affectedDependents"]:
                affected_dependents.add(str(affected["package"]))
            findings.append(
                {
                    "advisory": advisory,
                    "package": package_id,
                    "metadata": graph.get_vertex_metadata(package_id),
                    "impact": impact,
                }
            )

    return {
        "schema": "edgp.advisory.report.v1",
        "ecosystem": ecosystem,
        "root": root,
        "summary": {
            "advisories": len(advisories),
            "findings": len(findings),
            "matchedPackages": len({finding["package"] for finding in findings}),
            "affectedDependents": len(affected_dependents),
        },
        "findings": findings,
    }


def _extract_advisories(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        advisories = payload
    elif isinstance(payload, dict):
        schema = payload.get("schema")
        if schema not in (None, "edgp.advisory.overlay.v1"):
            raise ValueError(f"Unsupported advisory overlay schema: {schema}")
        advisories = payload.get("advisories", [])
    else:
        raise ValueError("Advisory overlay must be an object or list")

    if not isinstance(advisories, list):
        raise ValueError("Advisory overlay must contain an advisories list")

    normalized = []
    for advisory in advisories:
        if not isinstance(advisory, dict):
            raise ValueError("Each advisory must be an object")
        if not _advisory_package(advisory):
            raise ValueError("Each advisory must define package, name, or packageId")
        normalized.append(advisory)
    return normalized


def _matches_advisory(
    advisory: dict[str, Any], package_id: str, ecosystem: str
) -> bool:
    advisory_ecosystem = advisory.get("ecosystem")
    if advisory_ecosystem and str(advisory_ecosystem) != ecosystem:
        return False

    if advisory.get("packageId") == package_id:
        return True

    package_name, _, package_version = package_id.partition("==")
    if str(_advisory_package(advisory)) != package_name:
        return False

    versions = _advisory_versions(advisory)
    if not versions:
        return True
    return package_version in versions


def _advisory_package(advisory: dict[str, Any]) -> object | None:
    return advisory.get("package") or advisory.get("name") or advisory.get("packageId")


def _advisory_versions(advisory: dict[str, Any]) -> set[str]:
    versions = advisory.get("versions")
    if versions is None and advisory.get("version") is not None:
        versions = [advisory["version"]]
    if versions is None:
        return set()
    if isinstance(versions, str):
        return {versions}
    if isinstance(versions, list):
        return {str(version) for version in versions}
    raise ValueError("Advisory versions must be a string or list")


def _advisory_sort_key(advisory: dict[str, Any]) -> tuple[str, str]:
    return (str(advisory.get("id", "")), str(_advisory_package(advisory)))
