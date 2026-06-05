from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from src.adapters.base import LockfileAdapter, ProjectManifest, ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.models.package import DependencyRequirement


class NpmAdapter(LockfileAdapter):
    ecosystem = "npm"

    def supports(self, path: Path) -> bool:
        return path.name in {"package.json", "package-lock.json"}

    def parse(self, path: Path) -> ProjectManifest:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        if path.name == "package-lock.json":
            root_record = payload.get("packages", {}).get("", payload)
        else:
            root_record = payload

        dependencies: dict[str, str] = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            value = root_record.get(key, {})
            if isinstance(value, dict):
                dependencies.update({str(name): str(constraint) for name, constraint in value.items()})

        return ProjectManifest(
            root_name=str(root_record.get("name", payload.get("name", "npm-project"))),
            root_version=str(root_record.get("version", payload.get("version", "0.0.0"))),
            direct_dependencies=tuple(
                DependencyRequirement(name, constraint)
                for name, constraint in sorted(dependencies.items())
            ),
        )

    def parse_lockfile_graph(self, path: Path) -> ResolvedProjectGraph:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        packages = payload.get("packages")
        if isinstance(packages, Mapping):
            return self._parse_packages_lockfile(payload, packages)

        dependencies = payload.get("dependencies")
        if isinstance(dependencies, Mapping):
            return self._parse_legacy_lockfile(payload, dependencies)

        raise ValueError(f"Unsupported npm lockfile shape: {path}")

    def _parse_packages_lockfile(
        self, payload: Mapping[str, object], packages: Mapping[str, object]
    ) -> ResolvedProjectGraph:
        graph = CSRDependencyGraph()
        package_ids: dict[str, str] = {}

        for package_path, raw_record in packages.items():
            if not isinstance(raw_record, Mapping):
                continue
            package_id = self._package_identifier(str(package_path), raw_record, payload)
            if package_id is None:
                continue
            package_ids[str(package_path)] = package_id
            graph.add_vertex(package_id)

        root_identifier = package_ids.get(
            "",
            self._package_identifier("", {}, payload) or "npm-project==0.0.0",
        )
        graph.add_vertex(root_identifier)

        for package_path, raw_record in packages.items():
            if not isinstance(raw_record, Mapping):
                continue
            source_id = package_ids.get(str(package_path))
            if source_id is None:
                continue

            for dependency_name in self._dependency_names(raw_record):
                dependency_path = self._resolve_dependency_path(
                    str(package_path), dependency_name, packages
                )
                if dependency_path is None:
                    continue
                target_id = package_ids.get(dependency_path)
                if target_id is not None:
                    graph.add_dependency_edge(source_id, target_id)

        return ResolvedProjectGraph(
            root_identifier=root_identifier,
            graph=graph,
            ecosystem=self.ecosystem,
        )

    def _parse_legacy_lockfile(
        self, payload: Mapping[str, object], dependencies: Mapping[str, object]
    ) -> ResolvedProjectGraph:
        graph = CSRDependencyGraph()
        root_identifier = self._package_identifier("", {}, payload) or "npm-project==0.0.0"
        graph.add_vertex(root_identifier)

        for name, raw_record in dependencies.items():
            if not isinstance(raw_record, Mapping):
                continue
            self._add_legacy_dependency(graph, root_identifier, str(name), raw_record)

        return ResolvedProjectGraph(
            root_identifier=root_identifier,
            graph=graph,
            ecosystem=self.ecosystem,
        )

    def _add_legacy_dependency(
        self,
        graph: CSRDependencyGraph,
        parent_id: str,
        name: str,
        record: Mapping[str, object],
    ) -> str:
        version = str(record.get("version", "0.0.0"))
        package_id = f"{name}=={version}"
        graph.add_dependency_edge(parent_id, package_id)

        nested = record.get("dependencies", {})
        if isinstance(nested, Mapping):
            for nested_name, nested_record in nested.items():
                if isinstance(nested_record, Mapping):
                    self._add_legacy_dependency(
                        graph, package_id, str(nested_name), nested_record
                    )

        return package_id

    def _package_identifier(
        self,
        package_path: str,
        record: Mapping[str, object],
        root_payload: Mapping[str, object],
    ) -> str | None:
        if package_path == "":
            name = str(record.get("name") or root_payload.get("name") or "npm-project")
            version = str(record.get("version") or root_payload.get("version") or "0.0.0")
            return f"{name}=={version}"

        version = record.get("version")
        if version is None:
            return None
        name = record.get("name") or self._package_name_from_path(package_path)
        if not name:
            return None
        return f"{name}=={version}"

    def _dependency_names(self, record: Mapping[str, object]) -> tuple[str, ...]:
        names: set[str] = set()
        for key in (
            "dependencies",
            "optionalDependencies",
            "peerDependencies",
            "devDependencies",
        ):
            dependencies = record.get(key, {})
            if isinstance(dependencies, Mapping):
                names.update(str(name) for name in dependencies)
        return tuple(sorted(names))

    def _resolve_dependency_path(
        self,
        source_path: str,
        dependency_name: str,
        packages: Mapping[str, object],
    ) -> str | None:
        search_paths = self._node_resolution_search_paths(source_path, dependency_name)
        for candidate in search_paths:
            if candidate in packages:
                return candidate
        return None

    def _node_resolution_search_paths(
        self, source_path: str, dependency_name: str
    ) -> tuple[str, ...]:
        candidate_paths: list[str] = []
        current = source_path

        while True:
            if current:
                candidate_paths.append(f"{current}/node_modules/{dependency_name}")
            else:
                candidate_paths.append(f"node_modules/{dependency_name}")

            if not current:
                break

            marker = "/node_modules/"
            if marker not in current:
                current = ""
                continue
            current = current.rsplit(marker, 1)[0]

        return tuple(dict.fromkeys(candidate_paths))

    def _package_name_from_path(self, package_path: str) -> str | None:
        pieces = package_path.split("/")
        for index in range(len(pieces) - 1, -1, -1):
            if pieces[index] != "node_modules" or index + 1 >= len(pieces):
                continue
            name = pieces[index + 1]
            if name.startswith("@") and index + 2 < len(pieces):
                return f"{name}/{pieces[index + 2]}"
            return name
        return None
