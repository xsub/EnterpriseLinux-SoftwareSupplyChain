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
            GraphJsonExporter._edge(edge)
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
        metadata = csr_graph.get_vertex_metadata(package_id)
        node: dict[str, object] = {
            "id": package_id,
            "name": name,
            "dependencies": csr_graph.get_dependencies(package_id),
            "dependents": csr_graph.get_dependents(package_id),
            "metadata": metadata,
        }
        if separator:
            node["version"] = version
        if metadata.get("purl"):
            node["purl"] = metadata["purl"]
            node["package"] = GraphJsonExporter._normalized_package(
                name,
                version if separator else "",
                metadata,
            )
        return node

    @staticmethod
    def _edge(edge) -> dict[str, object]:
        payload: dict[str, object] = {
            "source": edge.source,
            "target": edge.target,
            "relationshipType": edge.relationship_type,
        }
        metadata = dict(getattr(edge, "metadata", {}) or {})
        if metadata:
            payload["metadata"] = metadata
        for metadata_key, output_key in (
            ("scope", "scope"),
            ("constraint", "constraint"),
            ("resolved_version", "resolvedVersion"),
            ("source_file", "sourceFile"),
            ("source_line", "sourceLine"),
            ("direct", "direct"),
        ):
            if metadata_key not in metadata:
                continue
            value: object = metadata[metadata_key]
            if output_key == "sourceLine":
                try:
                    value = int(str(value))
                except ValueError:
                    pass
            if output_key == "direct":
                value = str(value).lower() == "true"
            payload[output_key] = value
        return payload

    @staticmethod
    def _normalized_package(
        name: str,
        version: str,
        metadata: dict[str, str],
    ) -> dict[str, object]:
        package: dict[str, object] = {
            "ecosystem": metadata.get("ecosystem", "generic"),
            "name": metadata.get("name", name),
            "version": metadata.get("version", version),
            "purl": metadata["purl"],
        }
        for metadata_key, output_key in (
            ("source_url", "sourceUrl"),
            ("license", "license"),
            ("checksum", "checksum"),
            ("signature", "signature"),
            ("provenance", "provenance"),
        ):
            if metadata.get(metadata_key):
                package[output_key] = metadata[metadata_key]
        return package
