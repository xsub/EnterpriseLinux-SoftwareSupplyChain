"""ALBS artifact inventory report builder for build provenance graphs."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from src.core_graph.sparse_matrix import CSRDependencyGraph

ALBS_ARTIFACT_INVENTORY_SCHEMA = "edgp.albs.artifact_inventory.v1"
_ARCH_PREFERENCE = ("x86_64", "aarch64", "ppc64le", "s390x", "i686", "noarch", "src")


@dataclass(frozen=True)
class RpmFilename:
    name: str = ""
    version: str = ""
    release: str = ""
    arch: str = "unknown"


def build_albs_artifact_inventory(
    graph: CSRDependencyGraph,
    *,
    root: str,
) -> dict[str, Any]:
    """Build a deterministic inventory report from ALBS graph artifact nodes."""

    items = _artifact_items(graph)
    build_arches = sorted(
        {item["buildArch"] for item in items if item["buildArch"]},
        key=_arch_sort_key,
    )
    package_names = sorted({item["packageName"] for item in items if item["packageName"]})
    by_build_arch = _summaries_by_build_arch(items)
    return {
        "schema": ALBS_ARTIFACT_INVENTORY_SCHEMA,
        "ecosystem": "albs",
        "root": root,
        "summary": {
            "artifacts": len(items),
            "buildTasks": len({item["buildTaskId"] for item in items if item["buildTaskId"]}),
            "binaryRpms": sum(1 for item in items if item["artifactKind"] == "binary"),
            "sourceRpms": sum(1 for item in items if item["artifactKind"] == "srpm"),
            "debugArtifacts": sum(1 for item in items if item["artifactKind"] == "debug"),
            "buildLogs": sum(1 for item in items if item["artifactKind"] == "build-log"),
            "architectures": len(build_arches),
            "packages": len(package_names),
        },
        "buildArchitectures": build_arches,
        "packages": package_names,
        "byBuildArch": by_build_arch,
        "items": items,
    }


def _artifact_items(graph: CSRDependencyGraph) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for task_id in sorted(graph.vertex_map):
        task_metadata = graph.get_vertex_metadata(task_id)
        if task_metadata.get("node_type") != "build_task":
            continue
        build_arch = task_metadata.get("arch", "unknown")
        for artifact_id in graph.get_dependencies(task_id):
            artifact_metadata = graph.get_vertex_metadata(artifact_id)
            if artifact_metadata.get("node_type") not in {
                "binary_rpm",
                "source_rpm",
                "build_log",
            }:
                continue
            filename = artifact_metadata.get("artifact_name", artifact_id)
            rpm = _parse_rpm_filename(filename)
            package_name = rpm.name or filename.removesuffix(".rpm")
            artifact_arch = rpm.arch
            items.append(
                {
                    "artifactNodeId": artifact_id,
                    "artifactId": artifact_metadata.get("artifact_id", ""),
                    "filename": filename,
                    "artifactType": artifact_metadata.get("artifact_type", ""),
                    "artifactKind": _artifact_kind(artifact_metadata, rpm),
                    "packageName": package_name,
                    "version": rpm.version,
                    "release": rpm.release,
                    "artifactArch": artifact_arch,
                    "buildTaskId": task_id,
                    "buildArch": build_arch,
                    "href": artifact_metadata.get("href", ""),
                    "casHash": artifact_metadata.get("cas_hash", ""),
                }
            )

    return sorted(
        items,
        key=lambda item: (
            _arch_sort_key(item["buildArch"]),
            _arch_sort_key(item["artifactArch"]),
            item["artifactKind"],
            item["packageName"],
            item["filename"],
            item["artifactNodeId"],
        ),
    )


def _summaries_by_build_arch(items: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for item in items:
        grouped[item["buildArch"]].append(item)

    summaries = []
    for build_arch, group in grouped.items():
        artifact_arches = Counter(item["artifactArch"] for item in group)
        summaries.append(
            {
                "buildArch": build_arch,
                "totalArtifacts": len(group),
                "artifactArches": {
                    arch: artifact_arches[arch]
                    for arch in sorted(artifact_arches, key=_arch_sort_key)
                },
                "packages": sorted({item["packageName"] for item in group if item["packageName"]}),
            }
        )
    return sorted(summaries, key=lambda summary: _arch_sort_key(summary["buildArch"]))


def _artifact_kind(metadata: dict[str, str], rpm: RpmFilename) -> str:
    node_type = metadata.get("node_type")
    if node_type == "source_rpm":
        return "srpm"
    if node_type == "build_log":
        return "build-log"
    if _is_debug_artifact(rpm.name or metadata.get("artifact_name", "")):
        return "debug"
    if rpm.arch == "noarch":
        return "noarch"
    return "binary"


def _parse_rpm_filename(filename: str) -> RpmFilename:
    if not filename.endswith(".rpm"):
        return RpmFilename(name=filename, arch="unknown")
    stem = filename.removesuffix(".rpm")
    parts = stem.rsplit(".", 1)
    if len(parts) != 2:
        return RpmFilename(name=stem)
    nevr, arch = parts
    name_version_release = nevr.rsplit("-", 2)
    if len(name_version_release) != 3:
        return RpmFilename(name=nevr, arch=arch)
    name, version, release = name_version_release
    return RpmFilename(name=name, version=version, release=release, arch=arch)


def _is_debug_artifact(name: str) -> bool:
    return (
        name.endswith("-debuginfo")
        or name.endswith("-debugsource")
        or "-debuginfo-" in name
        or "-debugsource-" in name
    )


def _arch_sort_key(value: str) -> tuple[int, str]:
    try:
        return (_ARCH_PREFERENCE.index(value), value)
    except ValueError:
        return (len(_ARCH_PREFERENCE), value)
