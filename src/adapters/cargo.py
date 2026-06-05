"""Cargo.lock ingestion for Rust dependency graph construction."""

from __future__ import annotations

import tomllib
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph


class CargoAdapter:
    """Build resolved CSR graphs from Cargo.lock package sections."""

    ecosystem = "cargo"

    def supports(self, path: Path) -> bool:
        return path.name == "Cargo.lock"

    def parse_lockfile_graph(self, path: Path) -> ResolvedProjectGraph:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)

        raw_packages = payload.get("package", [])
        if not isinstance(raw_packages, list):
            raise ValueError(f"Unsupported Cargo lockfile shape: {path}")

        graph = CSRDependencyGraph()
        records: list[Mapping[str, object]] = []
        package_by_name: dict[str, list[str]] = defaultdict(list)
        package_by_name_version: dict[tuple[str, str], str] = {}

        for raw_package in raw_packages:
            if not isinstance(raw_package, Mapping):
                continue
            package_id = self._package_identifier(raw_package)
            if package_id is None:
                continue
            records.append(raw_package)
            name = self._normalize_name(str(raw_package["name"]))
            version = str(raw_package["version"])
            package_by_name[name].append(package_id)
            package_by_name_version[(name, version)] = package_id
            graph.add_vertex(package_id, metadata=self._component_metadata(raw_package))

        for raw_package in records:
            source_id = self._package_identifier(raw_package)
            if source_id is None:
                continue
            raw_dependencies = raw_package.get("dependencies", [])
            if not isinstance(raw_dependencies, list):
                continue
            for raw_dependency in sorted(raw_dependencies):
                target_id = self._resolve_dependency(
                    str(raw_dependency),
                    package_by_name=package_by_name,
                    package_by_name_version=package_by_name_version,
                )
                if target_id is not None:
                    graph.add_dependency_edge(source_id, target_id)

        root_identifier = "cargo-lock==resolved"
        graph.add_vertex(
            root_identifier,
            metadata={
                "ecosystem": self.ecosystem,
                "source": "Cargo.lock",
                "node_type": "root",
            },
        )
        for package_id in sorted(package_by_name_version.values()):
            if not graph.get_dependents(package_id):
                graph.add_dependency_edge(root_identifier, package_id)

        return ResolvedProjectGraph(
            root_identifier=root_identifier,
            graph=graph,
            ecosystem=self.ecosystem,
        )

    def _resolve_dependency(
        self,
        dependency: str,
        *,
        package_by_name: dict[str, list[str]],
        package_by_name_version: dict[tuple[str, str], str],
    ) -> str | None:
        pieces = dependency.split()
        if not pieces:
            return None
        name = self._normalize_name(pieces[0])
        if len(pieces) >= 2:
            version_match = package_by_name_version.get((name, pieces[1]))
            if version_match is not None:
                return version_match

        candidates = package_by_name.get(name, [])
        if len(candidates) == 1:
            return candidates[0]
        return None

    def _package_identifier(self, record: Mapping[str, object]) -> str | None:
        name = record.get("name")
        version = record.get("version")
        if name is None or version is None:
            return None
        return f"{name}=={version}"

    def _component_metadata(self, record: Mapping[str, object]) -> dict[str, object]:
        metadata: dict[str, object] = {
            "ecosystem": self.ecosystem,
            "source": "Cargo.lock",
        }
        for key in ("checksum", "source"):
            value = record.get(key)
            if value is not None:
                metadata[f"cargo_{key}"] = value
        return metadata

    def _normalize_name(self, name: str) -> str:
        return name.lower().replace("_", "-")
