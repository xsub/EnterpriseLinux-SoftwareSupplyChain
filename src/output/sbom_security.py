"""CycloneDX SBOM exporter for security ingestion workflows."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.core.model import package_purl


class CycloneDXExporter:
    """Build a CycloneDX JSON SBOM from a resolved CSR graph."""

    @staticmethod
    def export_to_json(
        csr_graph: CSRDependencyGraph,
        root: str | None = None,
        ecosystem: str = "generic",
        timestamp: str | None = None,
    ) -> str:
        components = [
            CycloneDXExporter._component(
                package_id,
                metadata=csr_graph.get_vertex_metadata(package_id),
                ecosystem=ecosystem,
            )
            for package_id in sorted(csr_graph.vertex_map)
        ]
        dependencies = [
            {
                "ref": package_id,
                "dependsOn": csr_graph.get_dependencies(package_id),
            }
            for package_id in sorted(csr_graph.vertex_map)
        ]

        payload: dict[str, object] = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "version": 1,
            "metadata": {
                "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
            },
            "components": components,
            "dependencies": dependencies,
        }
        if root is not None:
            payload["metadata"]["component"] = CycloneDXExporter._component(
                root,
                metadata=csr_graph.get_vertex_metadata(root),
                ecosystem=ecosystem,
            )

        return json.dumps(payload, indent=2, sort_keys=True)

    @staticmethod
    def _component(
        package_id: str,
        *,
        metadata: dict[str, str] | None = None,
        ecosystem: str = "generic",
    ) -> dict[str, object]:
        metadata = metadata or {}
        name, separator, version = package_id.partition("==")
        component: dict[str, object] = {
            "type": metadata.get("component_type", "library"),
            "name": name,
            "bom-ref": package_id,
        }
        if separator:
            component["version"] = version
            component["purl"] = metadata.get("purl") or CycloneDXExporter._purl(
                metadata.get("ecosystem", ecosystem),
                name,
                version,
                metadata=metadata,
            )
        if "license" in metadata:
            component["licenses"] = [{"license": {"name": metadata["license"]}}]
        if "resolved" in metadata:
            component["externalReferences"] = [
                {"type": "distribution", "url": metadata["resolved"]}
            ]

        properties = [
            {"name": f"edgp:{key}", "value": value}
            for key, value in sorted(metadata.items())
            if key not in {"component_type", "license", "purl", "resolved"}
        ]
        if properties:
            component["properties"] = properties
        return component

    @staticmethod
    def _purl(
        ecosystem: str,
        name: str,
        version: str,
        *,
        metadata: dict[str, str] | None = None,
    ) -> str:
        return package_purl(ecosystem, name, version, metadata=metadata or {})
