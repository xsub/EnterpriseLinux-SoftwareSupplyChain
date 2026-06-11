"""Join installed RPM graph nodes to public ALBS build artifacts."""

from __future__ import annotations

from typing import Any, Mapping

from src.albs_build_diff import _artifact_index
from src.core_graph.sparse_matrix import CSRDependencyGraph

RPM_ALBS_PROVENANCE_SCHEMA = "edgp.rpm.albs_provenance.v1"


def build_rpm_albs_provenance_report(
    installed_graph: CSRDependencyGraph,
    albs_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Match installed RPM nodes to artifacts from one public ALBS build."""

    installed = _installed_packages(installed_graph)
    artifacts = list(_artifact_index(albs_payload).values())
    artifact_index = {
        _match_key(artifact["packageName"], artifact["version"], artifact["release"], artifact["artifactArch"]): artifact
        for artifact in artifacts
        if artifact["artifactKind"] == "rpm"
    }
    matches = []
    unmatched = []
    for package in installed:
        artifact = artifact_index.get(
            _match_key(
                package["name"],
                package["version"],
                package["release"],
                package["arch"],
            )
        )
        if artifact is None:
            unmatched.append(package)
            continue
        matches.append(
            {
                "installedPackage": package,
                "albsArtifact": artifact,
                "buildId": str(albs_payload.get("id") or albs_payload.get("build_id") or "unknown"),
                "releaseId": str(albs_payload.get("release_id") or ""),
            }
        )
    return {
        "schema": RPM_ALBS_PROVENANCE_SCHEMA,
        "ecosystem": "rpm",
        "root": "rpm-installed==local",
        "summary": {
            "installedPackages": len(installed),
            "albsArtifacts": len(artifact_index),
            "matchedPackages": len(matches),
            "unmatchedPackages": len(unmatched),
        },
        "matches": matches,
        "unmatchedInstalledPackages": unmatched,
    }


def _installed_packages(graph: CSRDependencyGraph) -> list[dict[str, str]]:
    packages = []
    for package_id in sorted(graph.vertex_map):
        metadata = graph.get_vertex_metadata(package_id)
        if metadata.get("source") != "rpmdb":
            continue
        if metadata.get("node_type") == "root" or package_id == "rpm-installed==local":
            continue
        name, _, version_release = package_id.partition("==")
        version, release = _split_version_release(version_release)
        packages.append(
            {
                "nodeId": package_id,
                "name": name,
                "version": version,
                "release": release,
                "arch": metadata.get("arch", ""),
                "sourceRpm": metadata.get("source_rpm", ""),
                "vendor": metadata.get("vendor", ""),
            }
        )
    return packages


def _split_version_release(value: str) -> tuple[str, str]:
    parts = value.rsplit("-", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return value, ""


def _match_key(name: str, version: str, release: str, arch: str) -> str:
    return f"{name}|{version}|{release}|{arch}"
