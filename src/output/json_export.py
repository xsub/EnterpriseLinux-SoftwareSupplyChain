"""EDGP JSON snapshot exporter for UI, notebook, and RAG workflows."""

from __future__ import annotations

import json

from src.core_graph.sparse_matrix import CSRDependencyGraph


class GraphJsonExporter:
    """Build a deterministic graph snapshot from a CSR dependency graph."""

    @staticmethod
    def export_to_json(
        csr_graph: CSRDependencyGraph,
        root: str | None = None,
        ecosystem: str = "generic",
    ) -> str:
        edges = [
            {
                "source": edge.source,
                "target": edge.target,
                "relationshipType": edge.relationship_type,
            }
            for edge in csr_graph.edges()
        ]
        nodes = [
            GraphJsonExporter._node(csr_graph, package_id)
            for package_id in sorted(csr_graph.vertex_map)
        ]

        payload: dict[str, object] = {
            "schema": "edgp.graph.snapshot.v1",
            "ecosystem": ecosystem,
            "root": root,
            "stats": {
                "nodes": len(csr_graph),
                "edges": len(edges),
            },
            "nodes": nodes,
            "edges": edges,
            "rankings": {
                "mostDependedUpon": [
                    {"package": package_id, "dependents": count}
                    for package_id, count in csr_graph.most_depended_upon()
                ],
            },
        }
        return json.dumps(payload, indent=2, sort_keys=True)

    @staticmethod
    def _node(csr_graph: CSRDependencyGraph, package_id: str) -> dict[str, object]:
        name, separator, version = package_id.partition("==")
        node: dict[str, object] = {
            "id": package_id,
            "name": name,
            "dependencies": csr_graph.get_dependencies(package_id),
            "dependents": csr_graph.get_dependents(package_id),
            "metadata": csr_graph.get_vertex_metadata(package_id),
        }
        if separator:
            node["version"] = version
        return node
