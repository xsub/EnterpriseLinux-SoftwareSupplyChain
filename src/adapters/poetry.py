"""Poetry pyproject and lockfile ingestion for Python dependency graphs."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path

from src.adapters.base import LockfileAdapter, ProjectManifest, ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.models.package import DependencyRequirement


class PoetryAdapter(LockfileAdapter):
    ecosystem = "pypi"

    def supports(self, path: Path) -> bool:
        return path.name in {"pyproject.toml", "poetry.lock"}

    def parse(self, path: Path) -> ProjectManifest:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)

        project = payload.get("project", {})
        poetry = payload.get("tool", {}).get("poetry", {})
        dependency_table = poetry.get("dependencies", {})

        dependencies: list[DependencyRequirement] = []
        for name, constraint in dependency_table.items():
            if name.lower() == "python":
                continue
            if isinstance(constraint, dict):
                constraint = constraint.get("version", "*")
            dependencies.append(DependencyRequirement(str(name), str(constraint)))

        return ProjectManifest(
            root_name=str(poetry.get("name") or project.get("name") or "poetry-project"),
            root_version=str(poetry.get("version") or project.get("version") or "0.0.0"),
            direct_dependencies=tuple(sorted(dependencies, key=lambda dep: dep.name)),
        )

    def parse_lockfile_graph(self, path: Path) -> ResolvedProjectGraph:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)

        raw_packages = payload.get("package", [])
        if not isinstance(raw_packages, list):
            raise ValueError(f"Unsupported Poetry lockfile shape: {path}")

        graph = CSRDependencyGraph()
        package_ids: dict[str, str] = {}
        package_records: list[Mapping[str, object]] = []

        for raw_package in raw_packages:
            if not isinstance(raw_package, Mapping):
                continue
            package_id = self._package_identifier(raw_package)
            if package_id is None:
                continue
            package_records.append(raw_package)
            package_ids[self._normalize_name(str(raw_package["name"]))] = package_id
            graph.add_vertex(package_id, metadata=self._component_metadata(raw_package))

        for raw_package in package_records:
            source_id = package_ids[self._normalize_name(str(raw_package["name"]))]
            dependencies = raw_package.get("dependencies", {})
            if not isinstance(dependencies, Mapping):
                continue
            for dependency_name in sorted(dependencies):
                target_id = package_ids.get(self._normalize_name(str(dependency_name)))
                if target_id is not None:
                    graph.add_dependency_edge(source_id, target_id)

        root_identifier = "poetry-lock==resolved"
        graph.add_vertex(
            root_identifier,
            metadata={
                "ecosystem": self.ecosystem,
                "source": "poetry.lock",
                "node_type": "root",
            },
        )
        for package_id in sorted(package_ids.values()):
            if not graph.get_dependents(package_id):
                graph.add_dependency_edge(root_identifier, package_id)

        return ResolvedProjectGraph(
            root_identifier=root_identifier,
            graph=graph,
            ecosystem=self.ecosystem,
        )

    def _package_identifier(self, record: Mapping[str, object]) -> str | None:
        name = record.get("name")
        version = record.get("version")
        if name is None or version is None:
            return None
        return f"{name}=={version}"

    def _component_metadata(self, record: Mapping[str, object]) -> dict[str, object]:
        metadata: dict[str, object] = {
            "ecosystem": self.ecosystem,
            "source": "poetry.lock",
        }
        optional_fields = {
            "category": record.get("category"),
            "groups": record.get("groups"),
            "optional": record.get("optional"),
            "python_versions": record.get("python-versions"),
        }
        for key, value in optional_fields.items():
            if value is not None:
                metadata[key] = value
        return metadata

    def _normalize_name(self, name: str) -> str:
        return name.lower().replace("_", "-").replace(".", "-")
