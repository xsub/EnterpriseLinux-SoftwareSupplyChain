"""CycloneDX SBOM ingestion for rebuilding dependency graphs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph


class CycloneDXAdapter:
    """Parse CycloneDX JSON components and dependency references into CSR."""

    def parse_graph(self, path: Path) -> ResolvedProjectGraph:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, Mapping):
            raise ValueError(f"Unsupported CycloneDX payload: {path}")
        return self.parse_payload(payload)

    def parse_payload(self, payload: Mapping[str, object]) -> ResolvedProjectGraph:
        graph = CSRDependencyGraph()
        ecosystem = "generic"

        components = payload.get("components", [])
        if isinstance(components, list):
            for raw_component in components:
                if not isinstance(raw_component, Mapping):
                    continue
                package_id = self._component_identifier(raw_component)
                metadata = self._component_metadata(raw_component)
                ecosystem = metadata.get("ecosystem", ecosystem)
                graph.add_vertex(package_id, metadata=metadata)

        dependencies = payload.get("dependencies", [])
        if isinstance(dependencies, list):
            for raw_dependency in dependencies:
                if not isinstance(raw_dependency, Mapping):
                    continue
                source = raw_dependency.get("ref")
                depends_on = raw_dependency.get("dependsOn", [])
                if not isinstance(source, str) or not isinstance(depends_on, list):
                    continue
                graph.add_vertex(source)
                for target in depends_on:
                    if isinstance(target, str):
                        graph.add_dependency_edge(source, target)

        root_identifier = self._root_identifier(payload) or next(
            iter(sorted(graph.vertex_map)), "cyclonedx-bom==unknown"
        )
        graph.add_vertex(root_identifier, metadata={"ecosystem": ecosystem})
        return ResolvedProjectGraph(
            root_identifier=root_identifier,
            graph=graph,
            ecosystem=ecosystem,
        )

    def _component_identifier(self, component: Mapping[str, object]) -> str:
        bom_ref = component.get("bom-ref")
        if isinstance(bom_ref, str) and bom_ref:
            return bom_ref
        name = str(component.get("name", "unknown"))
        version = str(component.get("version", "unknown"))
        return f"{name}=={version}"

    def _component_metadata(self, component: Mapping[str, object]) -> dict[str, str]:
        metadata: dict[str, str] = {}
        purl = component.get("purl")
        if isinstance(purl, str):
            metadata["purl"] = purl
            ecosystem = self._ecosystem_from_purl(purl)
            if ecosystem:
                metadata["ecosystem"] = ecosystem
        component_type = component.get("type")
        if isinstance(component_type, str):
            metadata["component_type"] = component_type
        licenses = component.get("licenses", [])
        if isinstance(licenses, list) and licenses:
            license_name = self._license_name(licenses[0])
            if license_name:
                metadata["license"] = license_name
        properties = component.get("properties", [])
        if isinstance(properties, list):
            for prop in properties:
                if not isinstance(prop, Mapping):
                    continue
                name = prop.get("name")
                value = prop.get("value")
                if isinstance(name, str) and isinstance(value, str):
                    metadata[name.removeprefix("edgp:")] = value
        return metadata

    def _license_name(self, license_entry: object) -> str | None:
        if not isinstance(license_entry, Mapping):
            return None
        license_payload = license_entry.get("license")
        if isinstance(license_payload, Mapping):
            name = license_payload.get("name") or license_payload.get("id")
            return str(name) if name else None
        expression = license_entry.get("expression")
        return str(expression) if expression else None

    def _root_identifier(self, payload: Mapping[str, object]) -> str | None:
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, Mapping):
            return None
        component = metadata.get("component", {})
        if not isinstance(component, Mapping):
            return None
        return self._component_identifier(component)

    def _ecosystem_from_purl(self, purl: str) -> str | None:
        if not purl.startswith("pkg:"):
            return None
        remainder = purl.removeprefix("pkg:")
        return remainder.split("/", 1)[0] or None
