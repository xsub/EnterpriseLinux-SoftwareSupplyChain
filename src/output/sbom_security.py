"""CycloneDX SBOM exporter for security ingestion workflows."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from src.core_graph.sparse_matrix import CSRDependencyGraph


class CycloneDXExporter:
    """Build a CycloneDX JSON SBOM from a resolved CSR graph."""

    @staticmethod
    def export_to_json(csr_graph: CSRDependencyGraph, root: str | None = None) -> str:
        components = [
            CycloneDXExporter._component(package_id)
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            "components": components,
            "dependencies": dependencies,
        }
        if root is not None:
            payload["metadata"]["component"] = CycloneDXExporter._component(root)

        return json.dumps(payload, indent=2, sort_keys=True)

    @staticmethod
    def _component(package_id: str) -> dict[str, str]:
        name, separator, version = package_id.partition("==")
        component = {
            "type": "library",
            "name": name,
            "bom-ref": package_id,
        }
        if separator:
            component["version"] = version
            component["purl"] = f"pkg:generic/{name}@{version}"
        return component
