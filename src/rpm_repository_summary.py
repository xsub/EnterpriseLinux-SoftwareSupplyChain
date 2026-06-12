"""RPM repository graph summary report for public repository metadata."""

from __future__ import annotations

from collections import Counter
from typing import Any

from src.core_graph.sparse_matrix import CSRDependencyGraph

RPM_REPOSITORY_SUMMARY_SCHEMA = "edgp.rpm.repository_summary.v1"


def build_rpm_repository_summary_report(
    graph: CSRDependencyGraph,
    *,
    root: str,
) -> dict[str, Any]:
    """Summarize package, source RPM, arch, and requirement coverage."""

    package_nodes = []
    capability_nodes = []
    for node_id in sorted(graph.vertex_map):
        metadata = graph.get_vertex_metadata(node_id)
        if metadata.get("source") != "rpm-primary":
            continue
        if metadata.get("node_type") == "package":
            package_nodes.append((node_id, metadata))
        elif metadata.get("node_type") == "unresolved_requirement":
            capability_nodes.append((node_id, metadata))

    arches = Counter(metadata.get("arch", "unknown") for _, metadata in package_nodes)
    source_rpms = Counter(
        metadata.get("source_rpm", "")
        for _, metadata in package_nodes
        if metadata.get("source_rpm")
    )
    requirement_edges = [
        edge
        for edge in graph.edges()
        if edge.source != root and edge.target != root
    ]
    unresolved_targets = {node_id for node_id, _ in capability_nodes}
    unresolved_edges = [
        edge for edge in requirement_edges if edge.target in unresolved_targets
    ]

    return {
        "schema": RPM_REPOSITORY_SUMMARY_SCHEMA,
        "ecosystem": "rpm",
        "root": root,
        "summary": {
            "packages": len(package_nodes),
            "sourceRpms": len(source_rpms),
            "architectures": len(arches),
            "requirementEdges": len(requirement_edges),
            "unresolvedRequirements": len(unresolved_edges),
        },
        "architectures": [
            {"arch": arch, "packages": count}
            for arch, count in sorted(arches.items())
        ],
        "topSourceRpms": [
            {"sourceRpm": source_rpm, "packages": count}
            for source_rpm, count in sorted(
                source_rpms.items(),
                key=lambda item: (-item[1], item[0]),
            )[:20]
        ],
        "unresolvedRequirements": [
            {
                "package": edge.source,
                "capability": graph.get_vertex_metadata(edge.target).get(
                    "capability",
                    edge.target,
                ),
            }
            for edge in sorted(unresolved_edges, key=lambda item: (item.source, item.target))
        ][:100],
    }
