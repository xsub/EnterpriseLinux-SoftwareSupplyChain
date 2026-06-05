"""Reverse reachability impact reports for dependency graph investigations."""

from __future__ import annotations

from src.core_graph.sparse_matrix import CSRDependencyGraph


def build_impact_report(
    graph: CSRDependencyGraph,
    *,
    node: str,
    root: str | None = None,
    ecosystem: str = "generic",
    max_paths: int = 20,
) -> dict[str, object]:
    """Return affected dependents and dependency chains for a graph node."""

    direct_dependents = sorted(graph.get_dependents(node))
    direct_dependencies = sorted(graph.get_dependencies(node))
    affected = graph.reachable_dependents(node)
    chains = [_chain_to_node(graph, node, package_id) for package_id in affected]
    chains = sorted(
        (chain for chain in chains if chain),
        key=lambda chain: (int(chain["distance"]), str(chain["package"])),
    )
    rendered_chains = chains[: max(max_paths, 0)]

    return {
        "schema": "edgp.impact.report.v1",
        "ecosystem": ecosystem,
        "root": root,
        "node": node,
        "metadata": graph.get_vertex_metadata(node),
        "summary": {
            "directDependents": len(direct_dependents),
            "affectedDependents": len(chains),
            "directDependencies": len(direct_dependencies),
            "renderedChains": len(rendered_chains),
            "truncatedChains": max(len(chains) - len(rendered_chains), 0),
        },
        "directDependents": direct_dependents,
        "directDependencies": direct_dependencies,
        "affectedDependents": [
            {"package": chain["package"], "distance": chain["distance"]}
            for chain in chains
        ],
        "dependencyChainsToNode": rendered_chains,
    }


def _chain_to_node(
    graph: CSRDependencyGraph, node: str, affected_package: str
) -> dict[str, object] | None:
    path_from_node = graph.shortest_dependency_path(
        node,
        affected_package,
        reverse=True,
    )
    if not path_from_node:
        return None

    chain_to_node = list(reversed(path_from_node))
    return {
        "package": affected_package,
        "distance": len(chain_to_node) - 1,
        "path": chain_to_node,
    }
