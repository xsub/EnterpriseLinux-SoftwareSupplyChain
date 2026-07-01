"""Cargo.lock ingestion for Rust dependency graph construction."""

from __future__ import annotations

import tomllib
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path

from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.core.model import DependencyEdge, Package


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
            graph.add_vertex(
                package_id,
                metadata=self._component_metadata(raw_package, source_file=path),
            )

        for raw_package in records:
            source_id = self._package_identifier(raw_package)
            if source_id is None:
                continue
            raw_dependencies = raw_package.get("dependencies", [])
            if not isinstance(raw_dependencies, list):
                continue
            for raw_dependency in sorted(raw_dependencies):
                dependency_name, dependency_constraint = self._dependency_request(
                    str(raw_dependency)
                )
                target_id = self._resolve_dependency(
                    str(raw_dependency),
                    package_by_name=package_by_name,
                    package_by_name_version=package_by_name_version,
                )
                if target_id is not None:
                    graph.add_dependency_edge(
                        source_id,
                        target_id,
                        metadata=DependencyEdge(
                            from_package=source_id,
                            to_package=target_id,
                            constraint=dependency_constraint,
                            resolved_version=graph.get_vertex_metadata(target_id).get(
                                "version",
                                "",
                            ),
                            scope="runtime",
                            source_file=str(path),
                            metadata={
                                "ecosystem": self.ecosystem,
                                "package_manager": "cargo",
                                "dependency_name": dependency_name,
                                "lockfile": path.name,
                                "direct": False,
                            },
                        ).graph_metadata(),
                    )

        root_identifier = "cargo-lock==resolved"
        graph.add_vertex(
            root_identifier,
            metadata=self._root_metadata(source_file=path),
        )
        for package_id in sorted(package_by_name_version.values()):
            if not graph.get_dependents(package_id):
                graph.set_vertex_metadata(
                    package_id,
                    {
                        "classification": "direct",
                        "direct_dependency": True,
                        "transitive_dependency": False,
                    },
                )
                graph.add_dependency_edge(
                    root_identifier,
                    package_id,
                    metadata=DependencyEdge(
                        from_package=root_identifier,
                        to_package=package_id,
                        resolved_version=graph.get_vertex_metadata(package_id).get(
                            "version",
                            "",
                        ),
                        scope="runtime",
                        source_file=str(path),
                        metadata={
                            "ecosystem": self.ecosystem,
                            "package_manager": "cargo",
                            "lockfile": path.name,
                            "direct": True,
                        },
                    ).graph_metadata(),
                )

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

    def _component_metadata(
        self,
        record: Mapping[str, object],
        *,
        source_file: Path,
    ) -> dict[str, object]:
        name = str(record.get("name") or "")
        version = str(record.get("version") or "")
        checksum = str(record.get("checksum") or "")
        cargo_source = str(record.get("source") or "")
        metadata: dict[str, object] = Package(
            ecosystem=self.ecosystem,
            name=name,
            version=version,
            source_url=self._source_url(cargo_source),
            checksum=checksum,
            provenance=cargo_source,
            metadata={
                "source": source_file.name,
                "node_type": "package",
                "package_manager": "cargo",
                "classification": "transitive",
                "direct_dependency": False,
                "transitive_dependency": True,
                "dependency_scope": "runtime",
                "cargo_source": cargo_source,
                "cargo_checksum": checksum,
            },
        ).graph_metadata()
        if self._is_git_source(cargo_source):
            metadata["git_dependency"] = True
        return metadata

    def _root_metadata(self, *, source_file: Path) -> dict[str, object]:
        return Package(
            ecosystem=self.ecosystem,
            name="cargo-lock",
            version="resolved",
            metadata={
                "source": source_file.name,
                "node_type": "root",
                "package_manager": "cargo",
                "classification": "root",
                "direct_dependency": False,
                "transitive_dependency": False,
                "dependency_scope": "runtime",
            },
        ).graph_metadata()

    def _dependency_request(self, dependency: str) -> tuple[str, str]:
        pieces = dependency.split()
        if not pieces:
            return "", ""
        name = self._normalize_name(pieces[0])
        version = pieces[1] if len(pieces) >= 2 else ""
        return name, version

    def _source_url(self, cargo_source: str) -> str:
        if cargo_source.startswith("registry+"):
            return cargo_source.removeprefix("registry+")
        if cargo_source.startswith("git+"):
            return cargo_source.removeprefix("git+")
        return cargo_source

    def _is_git_source(self, cargo_source: str) -> bool:
        return cargo_source.startswith("git+") or ".git" in cargo_source

    def _normalize_name(self, name: str) -> str:
        return name.lower().replace("_", "-")
