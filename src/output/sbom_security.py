"""CycloneDX SBOM exporter for security ingestion workflows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from urllib.parse import quote, urlencode

from src.core_graph.sparse_matrix import CSRDependencyGraph


class CycloneDXExporter:
    """Build a CycloneDX JSON SBOM from a resolved CSR graph."""

    @staticmethod
    def export_to_json(
        csr_graph: CSRDependencyGraph,
        root: str | None = None,
        ecosystem: str = "generic",
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
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
        metadata = metadata or {}
        if ecosystem == "npm":
            if name.startswith("@") and "/" in name:
                namespace, package_name = name.split("/", 1)
                return (
                    "pkg:npm/"
                    f"{quote(namespace, safe='')}/"
                    f"{quote(package_name, safe='')}@{quote(version, safe='')}"
                )
            return f"pkg:npm/{quote(name, safe='')}@{quote(version, safe='')}"
        if ecosystem == "pypi":
            return f"pkg:pypi/{quote(name.lower(), safe='')}@{quote(version, safe='')}"
        if ecosystem == "cargo":
            return f"pkg:cargo/{quote(name.lower(), safe='')}@{quote(version, safe='')}"
        if ecosystem == "rpm":
            vendor = metadata.get("vendor")
            if vendor:
                path = f"{quote(vendor.lower(), safe='')}/{quote(name, safe='')}"
            else:
                path = quote(name, safe='')
            qualifiers = {
                key: metadata[key]
                for key in ("arch", "distro", "epoch")
                if key in metadata
            }
            suffix = f"?{urlencode(sorted(qualifiers.items()))}" if qualifiers else ""
            return f"pkg:rpm/{path}@{quote(version, safe='')}{suffix}"
        return f"pkg:generic/{quote(name, safe='')}@{quote(version, safe='')}"
