"""npm manifest and package-lock ingestion for dependency graph construction."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlparse

from src.adapters.base import LockfileAdapter, ProjectManifest, ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.core.model import DependencyEdge, Package
from src.models.package import DependencyRequirement

NPM_LOCKFILE_NAMES = {"package-lock.json", "npm-shrinkwrap.json"}
NPM_MANIFEST_NAMES = {"package.json"}
NPM_SUPPORTED_NAMES = NPM_LOCKFILE_NAMES | NPM_MANIFEST_NAMES
NPM_DEPENDENCY_FIELDS = (
    ("peerDependencies", "peer"),
    ("optionalDependencies", "optional"),
    ("devDependencies", "dev"),
    ("dependencies", "runtime"),
)


class NpmAdapter(LockfileAdapter):
    ecosystem = "npm"

    def supports(self, path: Path) -> bool:
        return path.name in NPM_SUPPORTED_NAMES

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
        text = path.read_text(encoding="utf-8")
        payload = json.loads(text)

        packages = payload.get("packages")
        if isinstance(packages, Mapping):
            return self._parse_packages_lockfile(
                payload,
                packages,
                source_file=path,
                line_numbers=self._line_numbers(text, packages.keys()),
            )

        dependencies = payload.get("dependencies")
        if isinstance(dependencies, Mapping):
            return self._parse_legacy_lockfile(payload, dependencies, source_file=path)

        raise ValueError(f"Unsupported npm lockfile shape: {path}")

    def parse_package_json_graph(self, path: Path) -> ResolvedProjectGraph:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        graph = CSRDependencyGraph()
        name = str(payload.get("name") or "npm-project")
        version = str(payload.get("version") or "0.0.0")
        root = f"{name}=={version}"
        graph.add_vertex(
            root,
            metadata=self._root_metadata(name, version, payload, source_file=path),
        )
        for dependency_name in self._dependency_names(payload):
            constraint = self._dependency_constraint(payload, dependency_name)
            scope = self._dependency_scope(payload, dependency_name)
            target_id = f"{dependency_name}=={constraint or 'unresolved'}"
            graph.add_vertex(
                target_id,
                metadata=Package(
                    ecosystem=self.ecosystem,
                    name=dependency_name,
                    version=constraint or "",
                    metadata={
                        "node_type": "dependency_requirement",
                        "source": "package.json",
                        "package_manager": "npm",
                        "constraint": constraint,
                    },
                ).graph_metadata(),
            )
            edge = DependencyEdge(
                from_package=root,
                to_package=target_id,
                constraint=constraint,
                scope=scope,
                source_file=str(path),
                metadata={
                    "ecosystem": self.ecosystem,
                    "package_manager": "npm",
                    "direct": True,
                    "lockfile": path.name,
                },
            )
            graph.add_dependency_edge(root, target_id, metadata=edge.graph_metadata())

        return ResolvedProjectGraph(
            root_identifier=root,
            graph=graph,
            ecosystem=self.ecosystem,
        )

    def diagnose_lockfile(self, path: Path) -> dict[str, object]:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        packages = payload.get("packages")
        if not isinstance(packages, Mapping):
            raise ValueError(f"Unsupported npm diagnostic lockfile shape: {path}")

        package_records = self._package_records(payload, packages)
        root_identifier = package_records.get("", {}).get("id") or "npm-project==0.0.0"
        resolutions = []
        unresolved = []

        for package_path, raw_record in packages.items():
            if not isinstance(raw_record, Mapping):
                continue
            source_record = package_records.get(str(package_path))
            if source_record is None:
                continue
            for dependency_name in self._dependency_names(raw_record):
                dependency_path = self._resolve_dependency_path(
                    str(package_path), dependency_name, packages
                )
                requested = self._dependency_constraint(raw_record, dependency_name)
                if dependency_path is None:
                    unresolved.append(
                        {
                            "dependency": dependency_name,
                            "requested": requested,
                            "source": source_record["id"],
                            "sourcePath": str(package_path),
                            "searchedPaths": list(
                                self._node_resolution_search_paths(
                                    str(package_path), dependency_name
                                )
                            ),
                        }
                    )
                    continue
                target_record = package_records.get(dependency_path)
                if target_record is None:
                    continue
                resolutions.append(
                    {
                        "dependency": dependency_name,
                        "requested": requested,
                        "resolved": target_record["id"],
                        "resolvedPath": dependency_path,
                        "source": source_record["id"],
                        "sourcePath": str(package_path),
                    }
                )

        duplicates = self._duplicate_package_names(package_records)
        conflicts = self._nested_resolution_conflicts(resolutions)
        return {
            "schema": "edgp.npm.diagnostics.v1",
            "ecosystem": self.ecosystem,
            "root": root_identifier,
            "summary": {
                "packages": len(package_records),
                "duplicatePackageNames": len(duplicates),
                "nestedResolutionConflicts": len(conflicts),
                "unresolvedDependencies": len(unresolved),
            },
            "duplicatePackageNames": duplicates,
            "nestedResolutionConflicts": conflicts,
            "unresolvedDependencies": sorted(
                unresolved,
                key=lambda item: (item["sourcePath"], item["dependency"]),
            ),
        }

    def _parse_packages_lockfile(
        self,
        payload: Mapping[str, object],
        packages: Mapping[str, object],
        *,
        source_file: Path,
        line_numbers: Mapping[str, int],
    ) -> ResolvedProjectGraph:
        graph = CSRDependencyGraph()
        package_ids: dict[str, str] = {}
        direct_paths = self._direct_dependency_paths(packages)

        for package_path, raw_record in packages.items():
            if not isinstance(raw_record, Mapping):
                continue
            package_id = self._package_identifier(str(package_path), raw_record, payload)
            if package_id is None:
                continue
            package_ids[str(package_path)] = package_id
            graph.add_vertex(
                package_id,
                metadata=self._component_metadata(
                    str(package_path),
                    raw_record,
                    payload,
                    source_file=source_file,
                    source_line=line_numbers.get(str(package_path)),
                    direct_paths=direct_paths,
                ),
            )

        root_identifier = package_ids.get(
            "",
            self._package_identifier("", {}, payload) or "npm-project==0.0.0",
        )
        graph.add_vertex(
            root_identifier,
            metadata=self._root_metadata(
                *self._package_name_version_from_identifier(root_identifier),
                payload,
                source_file=source_file,
            ),
        )

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
                    target_metadata = graph.get_vertex_metadata(target_id)
                    edge = DependencyEdge(
                        from_package=source_id,
                        to_package=target_id,
                        constraint=self._dependency_constraint(
                            raw_record,
                            dependency_name,
                        ),
                        resolved_version=target_metadata.get("version", ""),
                        scope=self._dependency_scope(raw_record, dependency_name),
                        source_file=str(source_file),
                        source_line=line_numbers.get(str(package_path)),
                        metadata={
                            "ecosystem": self.ecosystem,
                            "package_manager": "npm",
                            "lockfile": source_file.name,
                            "source_path": str(package_path),
                            "target_path": dependency_path,
                            "direct": str(package_path) == "",
                        },
                    )
                    graph.add_dependency_edge(
                        source_id,
                        target_id,
                        metadata=edge.graph_metadata(),
                    )

        return ResolvedProjectGraph(
            root_identifier=root_identifier,
            graph=graph,
            ecosystem=self.ecosystem,
        )

    def _package_records(
        self,
        payload: Mapping[str, object],
        packages: Mapping[str, object],
    ) -> dict[str, dict[str, str]]:
        records = {}
        for package_path, raw_record in packages.items():
            if not isinstance(raw_record, Mapping):
                continue
            package_id = self._package_identifier(str(package_path), raw_record, payload)
            if package_id is None:
                continue
            name, _, version = package_id.partition("==")
            records[str(package_path)] = {
                "id": package_id,
                "name": name,
                "path": str(package_path),
                "version": version,
            }
        return records

    def _duplicate_package_names(
        self, package_records: Mapping[str, Mapping[str, str]]
    ) -> list[dict[str, object]]:
        by_name: dict[str, dict[str, list[str]]] = {}
        for record in package_records.values():
            by_version = by_name.setdefault(record["name"], {})
            by_version.setdefault(record["version"], []).append(record["path"])

        duplicates = []
        for name, versions in sorted(by_name.items()):
            if len(versions) <= 1:
                continue
            duplicates.append(
                {
                    "package": name,
                    "versions": [
                        {"version": version, "paths": sorted(paths)}
                        for version, paths in sorted(versions.items())
                    ],
                }
            )
        return duplicates

    def _nested_resolution_conflicts(
        self, resolutions: list[dict[str, str]]
    ) -> list[dict[str, object]]:
        by_dependency: dict[str, list[dict[str, str]]] = {}
        for resolution in resolutions:
            by_dependency.setdefault(resolution["dependency"], []).append(resolution)

        conflicts = []
        for dependency_name, entries in sorted(by_dependency.items()):
            versions = sorted(
                {
                    entry["resolved"].partition("==")[2]
                    for entry in entries
                    if "==" in entry["resolved"]
                }
            )
            if len(versions) <= 1:
                continue
            conflicts.append(
                {
                    "dependency": dependency_name,
                    "versions": versions,
                    "consumers": sorted(
                        entries,
                        key=lambda item: (item["sourcePath"], item["resolvedPath"]),
                    ),
                }
            )
        return conflicts

    def _parse_legacy_lockfile(
        self,
        payload: Mapping[str, object],
        dependencies: Mapping[str, object],
        *,
        source_file: Path,
    ) -> ResolvedProjectGraph:
        graph = CSRDependencyGraph()
        root_identifier = self._package_identifier("", {}, payload) or "npm-project==0.0.0"
        graph.add_vertex(
            root_identifier,
            metadata=self._root_metadata(
                *self._package_name_version_from_identifier(root_identifier),
                payload,
                source_file=source_file,
            ),
        )

        for name, raw_record in dependencies.items():
            if not isinstance(raw_record, Mapping):
                continue
            self._add_legacy_dependency(
                graph,
                root_identifier,
                str(name),
                raw_record,
                source_file=source_file,
                direct=True,
            )

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
        *,
        source_file: Path,
        direct: bool = False,
    ) -> str:
        version = str(record.get("version", "0.0.0"))
        package_id = f"{name}=={version}"
        graph.add_vertex(
            package_id,
            metadata=self._component_metadata(
                f"legacy:{name}",
                record,
                {},
                source_file=source_file,
                direct_paths={f"legacy:{name}"} if direct else set(),
            ),
        )
        graph.add_dependency_edge(
            parent_id,
            package_id,
            metadata=DependencyEdge(
                from_package=parent_id,
                to_package=package_id,
                constraint=str(record.get("version", "")),
                resolved_version=version,
                scope=self._package_scope(record),
                source_file=str(source_file),
                metadata={
                    "ecosystem": self.ecosystem,
                    "package_manager": "npm",
                    "lockfile": source_file.name,
                    "source_path": "legacy",
                    "target_path": f"legacy:{name}",
                    "direct": direct,
                },
            ).graph_metadata(),
        )

        nested = record.get("dependencies", {})
        if isinstance(nested, Mapping):
            for nested_name, nested_record in nested.items():
                if isinstance(nested_record, Mapping):
                    self._add_legacy_dependency(
                        graph,
                        package_id,
                        str(nested_name),
                        nested_record,
                        source_file=source_file,
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
        for key, _scope in NPM_DEPENDENCY_FIELDS:
            dependencies = record.get(key, {})
            if isinstance(dependencies, Mapping):
                names.update(str(name) for name in dependencies)
        return tuple(sorted(names))

    def _dependency_constraint(
        self, record: Mapping[str, object], dependency_name: str
    ) -> str:
        for key, _scope in NPM_DEPENDENCY_FIELDS:
            dependencies = record.get(key, {})
            if isinstance(dependencies, Mapping) and dependency_name in dependencies:
                return str(dependencies[dependency_name])
        return ""

    def _dependency_scope(
        self, record: Mapping[str, object], dependency_name: str
    ) -> str:
        for key, scope in NPM_DEPENDENCY_FIELDS:
            dependencies = record.get(key, {})
            if isinstance(dependencies, Mapping) and dependency_name in dependencies:
                return scope
        return "runtime"

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

    def _component_metadata(
        self,
        package_path: str,
        record: Mapping[str, object],
        root_payload: Mapping[str, object],
        *,
        source_file: Path,
        source_line: int | None = None,
        direct_paths: set[str] | None = None,
    ) -> dict[str, object]:
        package_id = self._package_identifier(package_path, record, root_payload)
        name, version = self._package_name_version_from_identifier(package_id or "")
        direct_paths = direct_paths or set()
        node_type = "root" if package_path == "" else "package"
        classification = (
            "root"
            if package_path == ""
            else "direct"
            if package_path in direct_paths
            else "transitive"
        )

        source_url = str(record.get("resolved") or "")
        checksum = str(record.get("integrity") or "")
        metadata: dict[str, object] = Package(
            ecosystem=self.ecosystem,
            name=name or str(record.get("name") or "npm-project"),
            version=version,
            source_url=source_url,
            license=str(record.get("license") or ""),
            checksum=checksum,
            provenance=str(record.get("provenance") or ""),
            metadata={
                "source": source_file.name,
                "node_type": node_type,
                "package_manager": "npm",
                "lockfile_format": self._lockfile_format(source_file),
                "package_path": package_path,
                "classification": classification,
                "direct_dependency": package_path in direct_paths,
                "transitive_dependency": (
                    package_path not in direct_paths and package_path != ""
                ),
                "dependency_scope": self._package_scope(record),
            },
        ).graph_metadata()
        if source_line is not None:
            metadata["source_line"] = source_line
        if package_path:
            metadata["package_path"] = package_path
        for key in (
            "resolved",
            "integrity",
            "license",
            "dev",
            "optional",
            "inBundle",
        ):
            if key in record:
                metadata[key] = record[key]
        if checksum and "integrity" not in metadata:
            metadata["integrity"] = checksum
        if source_url and "resolved" not in metadata:
            metadata["resolved"] = source_url
        if self._is_remote_tarball(source_url):
            metadata["remote_tarball_url"] = True
            metadata["remote_tarball_domain"] = urlparse(source_url).netloc
        if self._is_git_dependency(record):
            metadata["git_dependency"] = True
        if self._is_local_file_dependency(record):
            metadata["local_file_dependency"] = True
        if record.get("hasInstallScript"):
            metadata["has_install_script"] = True
        peer_dependencies = record.get("peerDependencies")
        if isinstance(peer_dependencies, Mapping) and peer_dependencies:
            metadata["peer_dependencies"] = ",".join(
                sorted(str(name) for name in peer_dependencies)
            )
        bundled = record.get("bundled")
        if bundled is not None:
            metadata["bundled"] = bundled
        return metadata

    def _root_metadata(
        self,
        name: str,
        version: str,
        payload: Mapping[str, object],
        *,
        source_file: Path,
    ) -> dict[str, object]:
        metadata = Package(
            ecosystem=self.ecosystem,
            name=name or "npm-project",
            version=version or "0.0.0",
            license=str(payload.get("license") or ""),
            metadata={
                "source": source_file.name,
                "node_type": "root",
                "package_manager": "npm",
                "lockfile_format": self._lockfile_format(source_file),
                "package_path": "",
                "classification": "root",
                "direct_dependency": False,
                "transitive_dependency": False,
                "dependency_scope": "runtime",
            },
        ).graph_metadata()
        scripts = payload.get("scripts")
        if isinstance(scripts, Mapping) and scripts:
            metadata["lifecycle_scripts"] = ",".join(
                sorted(str(name) for name in scripts)
            )
            install_scripts = [
                str(name)
                for name in scripts
                if str(name) in {"preinstall", "install", "postinstall"}
            ]
            if install_scripts:
                metadata["install_scripts"] = ",".join(sorted(install_scripts))
                metadata["has_install_script"] = True
        return metadata

    def _package_scope(self, record: Mapping[str, object]) -> str:
        if record.get("optional"):
            return "optional"
        if record.get("dev") or record.get("devOptional"):
            return "dev"
        if record.get("peer"):
            return "peer"
        return "runtime"

    def _package_name_version_from_identifier(self, package_id: str) -> tuple[str, str]:
        name, separator, version = package_id.partition("==")
        if separator:
            return name, version
        return package_id, ""

    def _direct_dependency_paths(self, packages: Mapping[str, object]) -> set[str]:
        root_record = packages.get("")
        if not isinstance(root_record, Mapping):
            return set()
        paths = set()
        for dependency_name in self._dependency_names(root_record):
            dependency_path = self._resolve_dependency_path("", dependency_name, packages)
            if dependency_path is not None:
                paths.add(dependency_path)
        return paths

    def _line_numbers(
        self,
        text: str,
        package_paths: object,
    ) -> dict[str, int]:
        wanted = {str(path) for path in package_paths}
        line_numbers: dict[str, int] = {}
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            for package_path in wanted - set(line_numbers):
                if stripped.startswith(json.dumps(package_path) + ":"):
                    line_numbers[package_path] = line_number
        return line_numbers

    def _lockfile_format(self, source_file: Path) -> str:
        if source_file.name == "npm-shrinkwrap.json":
            return "npm-shrinkwrap"
        if source_file.name == "package.json":
            return "package-json"
        return "package-lock"

    def _is_remote_tarball(self, value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _is_git_dependency(self, record: Mapping[str, object]) -> bool:
        for key in ("resolved", "version"):
            value = record.get(key)
            if isinstance(value, str) and (
                value.startswith("git+")
                or value.startswith("git:")
                or value.endswith(".git")
            ):
                return True
        return False

    def _is_local_file_dependency(self, record: Mapping[str, object]) -> bool:
        for key in ("resolved", "version"):
            value = record.get(key)
            if isinstance(value, str) and value.startswith("file:"):
                return True
        return False
