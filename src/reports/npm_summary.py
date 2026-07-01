"""npm supply-chain summary reports over normalized dependency graphs."""

from __future__ import annotations

from collections import Counter
from typing import Any

from src.core_graph.sparse_matrix import CSRDependencyGraph

NPM_SUMMARY_SCHEMA = "edgp.npm.summary.v1"
DEPENDENCY_PATH_SCHEMA = "edgp.dependency_path.v1"
VULNERABLE_SURFACE_SCHEMA = "edgp.vulnerable_surface.v1"


def build_npm_summary_report(
    graph: CSRDependencyGraph,
    *,
    root: str,
    source_file: str = "",
) -> dict[str, Any]:
    packages = _npm_packages(graph)
    edges = _npm_edges(graph)

    direct = [package for package in packages if package["classification"] == "direct"]
    transitive = [
        package for package in packages if package["classification"] == "transitive"
    ]
    missing_integrity = [
        package
        for package in packages
        if not package["metadata"].get("integrity")
        and package["metadata"].get("node_type") == "package"
        and not _truthy(package["metadata"].get("local_file_dependency"))
    ]
    remote_tarballs = [
        package for package in packages if package["metadata"].get("remote_tarball_url")
    ]
    dev_only = [
        package for package in packages if package["metadata"].get("dependency_scope") == "dev"
    ]
    optional = [
        package
        for package in packages
        if package["metadata"].get("dependency_scope") == "optional"
        or _truthy(package["metadata"].get("optional"))
    ]
    peer_warnings = _peer_warnings(packages, edges)
    git_dependencies = [
        package for package in packages if _truthy(package["metadata"].get("git_dependency"))
    ]
    local_file_dependencies = [
        package
        for package in packages
        if _truthy(package["metadata"].get("local_file_dependency"))
    ]
    lifecycle_script_packages = [
        package for package in packages if package["metadata"].get("lifecycle_scripts")
    ]
    install_script_packages = [
        package
        for package in packages
        if _truthy(package["metadata"].get("has_install_script"))
        or package["metadata"].get("install_scripts")
    ]
    confusion = _dependency_confusion_indicators(packages)
    typosquatting = _typosquatting_indicators(packages)
    domains = Counter(
        str(package["metadata"].get("remote_tarball_domain"))
        for package in remote_tarballs
        if package["metadata"].get("remote_tarball_domain")
    )

    return {
        "schema": NPM_SUMMARY_SCHEMA,
        "ecosystem": "npm",
        "root": root,
        "sourceFile": source_file,
        "summary": {
            "packages": len(packages),
            "dependencies": len(edges),
            "directDependencies": len(direct),
            "transitiveDependencies": len(transitive),
            "packagesWithoutIntegrity": len(missing_integrity),
            "packagesWithRemoteTarballUrls": len(remote_tarballs),
            "devOnlyPackages": len(dev_only),
            "optionalPackages": len(optional),
            "peerDependencyWarnings": len(peer_warnings),
            "gitBasedDependencies": len(git_dependencies),
            "localFileDependencies": len(local_file_dependencies),
            "lifecycleScriptPackages": len(lifecycle_script_packages),
            "installScriptPackages": len(install_script_packages),
            "dependencyConfusionRiskIndicators": len(confusion),
            "typosquattingFriendlyNames": len(typosquatting),
        },
        "directDependencies": direct,
        "transitiveDependencies": transitive,
        "packagesWithoutIntegrity": missing_integrity,
        "packagesWithRemoteTarballUrls": remote_tarballs,
        "remoteTarballDomains": [
            {"domain": domain, "packages": count}
            for domain, count in sorted(domains.items())
        ],
        "devOnlyPackages": dev_only,
        "optionalPackages": optional,
        "peerDependencyWarnings": peer_warnings,
        "gitBasedDependencies": git_dependencies,
        "localFileDependencies": local_file_dependencies,
        "lifecycleScriptPackages": lifecycle_script_packages,
        "installScriptPackages": install_script_packages,
        "dependencyConfusionRiskIndicators": confusion,
        "typosquattingFriendlyNames": typosquatting,
    }


def build_dependency_path_report(
    graph: CSRDependencyGraph,
    *,
    root: str,
    package: str,
) -> dict[str, Any]:
    resolved = resolve_package_selector(graph, package)
    path = graph.shortest_dependency_path(root, resolved)
    dependents = graph.get_dependents(resolved)
    reachable_dependents = graph.reachable_dependents(resolved)
    return {
        "schema": DEPENDENCY_PATH_SCHEMA,
        "root": root,
        "requestedPackage": package,
        "package": resolved,
        "purl": graph.get_vertex_metadata(resolved).get("purl", ""),
        "pathFound": bool(path),
        "path": path,
        "dependents": dependents,
        "reachableDependents": reachable_dependents,
        "summary": {
            "pathLength": len(path),
            "directDependents": len(dependents),
            "reachableDependents": len(reachable_dependents),
            "crossEcosystemEdges": len(_cross_ecosystem_edges(graph, path)),
        },
        "crossEcosystemEdges": _cross_ecosystem_edges(graph, path),
    }


def build_vulnerable_surface_report(
    graph: CSRDependencyGraph,
    *,
    root: str,
    ecosystem: str,
    source_file: str = "",
) -> dict[str, Any]:
    if ecosystem == "npm":
        summary = build_npm_summary_report(graph, root=root, source_file=source_file)
        findings = []
        for key in (
            "packagesWithoutIntegrity",
            "gitBasedDependencies",
            "localFileDependencies",
            "lifecycleScriptPackages",
            "installScriptPackages",
            "dependencyConfusionRiskIndicators",
            "typosquattingFriendlyNames",
        ):
            findings.extend(
                {
                    "type": key,
                    "package": item.get("id", item.get("package", "")),
                    "purl": item.get("purl", ""),
                    "details": item,
                }
                for item in summary.get(key, [])
                if isinstance(item, dict)
            )
        return {
            "schema": VULNERABLE_SURFACE_SCHEMA,
            "ecosystem": ecosystem,
            "root": root,
            "sourceFile": source_file,
            "summary": summary["summary"],
            "findings": findings,
        }
    packages = [
        _package_row(graph, package_id)
        for package_id in sorted(graph.vertex_map)
        if graph.get_vertex_metadata(package_id).get("ecosystem") == ecosystem
    ]
    return {
        "schema": VULNERABLE_SURFACE_SCHEMA,
        "ecosystem": ecosystem,
        "root": root,
        "sourceFile": source_file,
        "summary": {"packages": len(packages), "findings": 0},
        "findings": [],
    }


def resolve_package_selector(graph: CSRDependencyGraph, selector: str) -> str:
    if selector in graph.vertex_map:
        return selector
    purl_matches = [
        package_id
        for package_id in sorted(graph.vertex_map)
        if graph.get_vertex_metadata(package_id).get("purl") == selector
    ]
    if len(purl_matches) == 1:
        return purl_matches[0]
    name_matches = [
        package_id
        for package_id in sorted(graph.vertex_map)
        if package_id.partition("==")[0] == selector
        or graph.get_vertex_metadata(package_id).get("name") == selector
    ]
    if len(name_matches) == 1:
        return name_matches[0]
    if len(purl_matches) > 1 or len(name_matches) > 1:
        candidates = purl_matches or name_matches
        raise ValueError(
            f"Ambiguous package selector {selector!r}; candidates: {', '.join(candidates)}"
        )
    return selector


def _npm_packages(graph: CSRDependencyGraph) -> list[dict[str, Any]]:
    return [
        _package_row(graph, package_id)
        for package_id in sorted(graph.vertex_map)
        if graph.get_vertex_metadata(package_id).get("ecosystem") == "npm"
        and graph.get_vertex_metadata(package_id).get("node_type") != "root"
    ]


def _npm_edges(graph: CSRDependencyGraph) -> list[dict[str, Any]]:
    edges = []
    for edge in graph.edges():
        metadata = dict(edge.metadata)
        source_metadata = graph.get_vertex_metadata(edge.source)
        target_metadata = graph.get_vertex_metadata(edge.target)
        if (
            source_metadata.get("ecosystem") != "npm"
            and target_metadata.get("ecosystem") != "npm"
        ):
            continue
        edges.append(
            {
                "source": edge.source,
                "target": edge.target,
                "scope": metadata.get("scope", "runtime"),
                "constraint": metadata.get("constraint", ""),
                "resolvedVersion": metadata.get("resolved_version", ""),
                "sourceFile": metadata.get("source_file", ""),
                "sourcePath": metadata.get("source_path", ""),
                "targetPath": metadata.get("target_path", ""),
                "direct": _truthy(metadata.get("direct")),
            }
        )
    return edges


def _package_row(graph: CSRDependencyGraph, package_id: str) -> dict[str, Any]:
    metadata = graph.get_vertex_metadata(package_id)
    name, _, version = package_id.partition("==")
    return {
        "id": package_id,
        "name": metadata.get("name", name),
        "version": metadata.get("version", version),
        "purl": metadata.get("purl", ""),
        "classification": metadata.get("classification", ""),
        "scope": metadata.get("dependency_scope", ""),
        "sourceUrl": metadata.get("source_url") or metadata.get("resolved", ""),
        "integrity": metadata.get("integrity", ""),
        "license": metadata.get("license", ""),
        "metadata": metadata,
    }


def _peer_warnings(
    packages: list[dict[str, Any]],
    edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    warnings = [
        {
            "package": edge["source"],
            "dependency": edge["target"],
            "constraint": edge["constraint"],
            "sourceFile": edge["sourceFile"],
            "warning": "peer dependency must be provided by the consuming project",
        }
        for edge in edges
        if edge.get("scope") == "peer"
    ]
    for package in packages:
        peer_dependencies = str(package["metadata"].get("peer_dependencies", ""))
        for dependency in [item for item in peer_dependencies.split(",") if item]:
            warnings.append(
                {
                    "package": package["id"],
                    "dependency": dependency,
                    "constraint": "",
                    "sourceFile": package["metadata"].get("source", ""),
                    "warning": "package declares a peer dependency",
                }
            )
    return sorted(warnings, key=lambda item: (item["package"], item["dependency"]))


def _dependency_confusion_indicators(
    packages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    indicators = []
    for package in packages:
        name = str(package["name"])
        metadata = package["metadata"]
        if name.startswith("@"):
            continue
        domain = str(metadata.get("remote_tarball_domain", ""))
        if domain == "registry.npmjs.org":
            indicators.append(
                {
                    "id": package["id"],
                    "name": name,
                    "purl": package["purl"],
                    "indicator": "unscoped package resolved from the public npm registry",
                }
            )
    return indicators


def _typosquatting_indicators(
    packages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    popular = {
        "react",
        "lodash",
        "express",
        "webpack",
        "typescript",
        "eslint",
        "axios",
        "next",
        "vite",
    }
    indicators = []
    seen_names = {str(package["name"]).lower() for package in packages}
    for package in packages:
        name = str(package["name"]).lower()
        if name in popular:
            continue
        for target in popular & seen_names | popular:
            if _edit_distance_at_most_one(name, target):
                indicators.append(
                    {
                        "id": package["id"],
                        "name": package["name"],
                        "purl": package["purl"],
                        "indicator": f"name is one edit away from {target}",
                    }
                )
                break
    return indicators


def _cross_ecosystem_edges(
    graph: CSRDependencyGraph,
    path: list[str],
) -> list[dict[str, str]]:
    crossings = []
    for source, target in zip(path, path[1:]):
        source_ecosystem = graph.get_vertex_metadata(source).get("ecosystem", "")
        target_ecosystem = graph.get_vertex_metadata(target).get("ecosystem", "")
        if source_ecosystem and target_ecosystem and source_ecosystem != target_ecosystem:
            crossings.append(
                {
                    "source": source,
                    "target": target,
                    "sourceEcosystem": source_ecosystem,
                    "targetEcosystem": target_ecosystem,
                }
            )
    return crossings


def _truthy(value: object) -> bool:
    return str(value).lower() in {"1", "true", "yes"}


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if left == right:
        return True
    if len(left) == len(right):
        return sum(1 for a, b in zip(left, right) if a != b) == 1
    if len(left) > len(right):
        left, right = right, left
    index_left = index_right = differences = 0
    while index_left < len(left) and index_right < len(right):
        if left[index_left] == right[index_right]:
            index_left += 1
            index_right += 1
            continue
        differences += 1
        if differences > 1:
            return False
        index_right += 1
    return True

