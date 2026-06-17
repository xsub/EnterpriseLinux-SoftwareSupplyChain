"""RPM repository snapshot comparison report for public metadata."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

from src.core_graph.sparse_matrix import CSRDependencyGraph

RPM_REPOSITORY_DIFF_SCHEMA = "edgp.rpm.repository_diff.v1"


def build_rpm_repository_diff_report(
    left_graph: CSRDependencyGraph,
    right_graph: CSRDependencyGraph,
    *,
    left_root: str = "",
    right_root: str = "",
) -> dict[str, Any]:
    """Compare two public RPM repository graphs by package name and architecture."""

    left_packages = _package_index(left_graph)
    right_packages = _package_index(right_graph)
    left_keys = set(left_packages)
    right_keys = set(right_packages)
    common_keys = left_keys & right_keys

    added = [right_packages[key] for key in sorted(right_keys - left_keys)]
    removed = [left_packages[key] for key in sorted(left_keys - right_keys)]
    changed = [
        _package_change(left_packages[key], right_packages[key])
        for key in sorted(common_keys)
        if _package_changed(left_packages[key], right_packages[key])
    ]
    unchanged = len(common_keys) - len(changed)
    left_source_rpms = _source_rpms(left_packages.values())
    right_source_rpms = _source_rpms(right_packages.values())

    return {
        "schema": RPM_REPOSITORY_DIFF_SCHEMA,
        "ecosystem": "rpm",
        "left": _repo_summary(left_graph, left_packages, left_root),
        "right": _repo_summary(right_graph, right_packages, right_root),
        "summary": {
            "leftPackages": len(left_packages),
            "rightPackages": len(right_packages),
            "addedPackages": len(added),
            "removedPackages": len(removed),
            "changedPackages": len(changed),
            "unchangedPackages": unchanged,
            "addedSourceRpms": len(right_source_rpms - left_source_rpms),
            "removedSourceRpms": len(left_source_rpms - right_source_rpms),
        },
        "addedPackages": added,
        "removedPackages": removed,
        "changedPackages": changed,
        "topFindings": _top_findings(
            added=added,
            removed=removed,
            changed=changed,
            source_delta={
                "added": sorted(right_source_rpms - left_source_rpms),
                "removed": sorted(left_source_rpms - right_source_rpms),
            },
        ),
        "sourceRpmDelta": {
            "added": sorted(right_source_rpms - left_source_rpms),
            "removed": sorted(left_source_rpms - right_source_rpms),
        },
    }


def _package_index(graph: CSRDependencyGraph) -> dict[str, dict[str, str]]:
    packages: dict[str, dict[str, str]] = {}
    for node_id in sorted(graph.vertex_map):
        metadata = graph.get_vertex_metadata(node_id)
        if metadata.get("node_type") != "package":
            continue
        name = metadata.get("name", "")
        arch = metadata.get("arch", "")
        if not name or not arch:
            continue
        key = f"{name}|{arch}"
        packages[key] = {
            "key": key,
            "nodeId": node_id,
            "name": name,
            "epoch": metadata.get("epoch", "0"),
            "version": metadata.get("version", ""),
            "release": metadata.get("release", ""),
            "arch": arch,
            "sourceRpm": metadata.get("source_rpm", ""),
            "summary": metadata.get("summary", ""),
        }
    return packages


def _repo_summary(
    graph: CSRDependencyGraph,
    packages: dict[str, dict[str, str]],
    root: str,
) -> dict[str, Any]:
    root_metadata = graph.get_vertex_metadata(root) if root else {}
    arches = Counter(package["arch"] for package in packages.values())
    source_rpms = _source_rpms(packages.values())
    return {
        "root": root,
        "sourceLabel": root_metadata.get("source_label", ""),
        "primaryLocation": root_metadata.get("primary_location", ""),
        "packages": len(packages),
        "architectures": sorted(arches),
        "sourceRpms": len(source_rpms),
    }


def _package_changed(left: dict[str, str], right: dict[str, str]) -> bool:
    return any(left.get(field, "") != right.get(field, "") for field in _CHANGE_FIELDS)


def _package_change(left: dict[str, str], right: dict[str, str]) -> dict[str, Any]:
    changed_fields = [
        field
        for field in _CHANGE_FIELDS
        if left.get(field, "") != right.get(field, "")
    ]
    return {
        "key": left["key"],
        "name": left["name"] or right["name"],
        "arch": left["arch"] or right["arch"],
        "changedFields": changed_fields,
        "left": left,
        "right": right,
    }


def _top_findings(
    *,
    added: list[dict[str, str]],
    removed: list[dict[str, str]],
    changed: list[dict[str, Any]],
    source_delta: dict[str, list[str]],
    limit: int = 10,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "changedPackages": sorted(
            changed,
            key=lambda item: (
                -len(item.get("changedFields", [])),
                str(item.get("name", "")),
                str(item.get("arch", "")),
            ),
        )[:limit],
        "addedPackages": _rank_packages(added)[:limit],
        "removedPackages": _rank_packages(removed)[:limit],
        "sourceRpmDelta": _source_rpm_delta_findings(source_delta)[:limit],
    }


def _rank_packages(packages: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        packages,
        key=lambda item: (
            str(item.get("name", "")),
            str(item.get("arch", "")),
            str(item.get("version", "")),
            str(item.get("release", "")),
        ),
    )


def _source_rpm_delta_findings(
    source_delta: dict[str, list[str]],
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for status in ("added", "removed"):
        for source_rpm in source_delta.get(status, []):
            findings.append({"status": status, "sourceRpm": source_rpm})
    return findings


def _source_rpms(packages: Iterable[Mapping[str, str]]) -> set[str]:
    return {
        str(package.get("sourceRpm", ""))
        for package in packages
        if package.get("sourceRpm")
    }


_CHANGE_FIELDS = ("epoch", "version", "release", "sourceRpm", "summary", "nodeId")
