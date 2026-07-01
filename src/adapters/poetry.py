"""Poetry pyproject and lockfile ingestion for Python dependency graphs."""

from __future__ import annotations

import tomllib
import re
from collections.abc import Mapping
from pathlib import Path

from src.adapters.base import LockfileAdapter, ProjectManifest, ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.core.model import DependencyEdge, Package
from src.models.package import DependencyRequirement

PYPI_SUPPORTED_NAMES = {"pyproject.toml", "poetry.lock", "requirements.txt"}
REQUIREMENT_OPERATORS = ("===", "==", "~=", "!=", "<=", ">=", "<", ">")
REQUIREMENT_HASH_RE = re.compile(r"--hash\s*=\s*([^\s]+)")


class PoetryAdapter(LockfileAdapter):
    ecosystem = "pypi"

    def supports(self, path: Path) -> bool:
        return path.name in PYPI_SUPPORTED_NAMES or path.name.startswith("requirements")

    def parse(self, path: Path) -> ProjectManifest:
        if self._is_requirements_file(path):
            requirements = self._parse_requirements(path)
            return ProjectManifest(
                root_name=path.stem,
                root_version="resolved",
                direct_dependencies=tuple(
                    DependencyRequirement(requirement["name"], requirement["constraint"])
                    for requirement in requirements
                ),
            )

        payload = self._load_toml(path)
        project = self._mapping(payload.get("project"))
        poetry = self._mapping(self._mapping(payload.get("tool")).get("poetry"))
        dependencies = self._pyproject_dependencies(payload)

        return ProjectManifest(
            root_name=str(poetry.get("name") or project.get("name") or "poetry-project"),
            root_version=str(poetry.get("version") or project.get("version") or "0.0.0"),
            direct_dependencies=tuple(
                DependencyRequirement(dependency["name"], dependency["constraint"])
                for dependency in dependencies
            ),
        )

    def parse_lockfile_graph(self, path: Path) -> ResolvedProjectGraph:
        if self._is_requirements_file(path):
            return self.parse_requirements_graph(path)
        if path.name == "pyproject.toml":
            return self.parse_pyproject_graph(path)

        payload = self._load_toml(path)

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
            graph.add_vertex(
                package_id,
                metadata=self._component_metadata(raw_package, source_file=path),
            )

        for raw_package in package_records:
            source_id = package_ids[self._normalize_name(str(raw_package["name"]))]
            dependencies = raw_package.get("dependencies", {})
            if not isinstance(dependencies, Mapping):
                continue
            for dependency_name in sorted(dependencies):
                target_id = package_ids.get(self._normalize_name(str(dependency_name)))
                if target_id is not None:
                    graph.add_dependency_edge(
                        source_id,
                        target_id,
                        metadata=DependencyEdge(
                            from_package=source_id,
                            to_package=target_id,
                            constraint=self._poetry_dependency_constraint(
                                dependencies[dependency_name]
                            ),
                            resolved_version=graph.get_vertex_metadata(target_id).get(
                                "version",
                                "",
                            ),
                            scope=self._scope_from_poetry_record(raw_package),
                            source_file=str(path),
                            metadata={
                                "ecosystem": self.ecosystem,
                                "package_manager": "poetry",
                                "lockfile": path.name,
                                "direct": False,
                            },
                        ).graph_metadata(),
                    )

        root_identifier = "poetry-lock==resolved"
        graph.add_vertex(
            root_identifier,
            metadata=self._root_metadata(
                "poetry-lock",
                "resolved",
                source_file=path,
                package_manager="poetry",
            ),
        )
        for package_id in sorted(package_ids.values()):
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
                        scope=graph.get_vertex_metadata(package_id).get(
                            "dependency_scope",
                            "runtime",
                        ),
                        source_file=str(path),
                        metadata={
                            "ecosystem": self.ecosystem,
                            "package_manager": "poetry",
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

    def parse_requirements_graph(self, path: Path) -> ResolvedProjectGraph:
        graph = CSRDependencyGraph()
        root_identifier = f"{path.stem}==resolved"
        graph.add_vertex(
            root_identifier,
            metadata=self._root_metadata(
                path.stem,
                "resolved",
                source_file=path,
                package_manager="pip",
            ),
        )
        for requirement in self._parse_requirements(path):
            package_id = self._requirement_identifier(requirement)
            graph.add_vertex(
                package_id,
                metadata=self._requirement_metadata(
                    requirement,
                    source_file=path,
                    package_manager="pip",
                ),
            )
            graph.add_dependency_edge(
                root_identifier,
                package_id,
                metadata=DependencyEdge(
                    from_package=root_identifier,
                    to_package=package_id,
                    constraint=requirement["constraint"],
                    resolved_version=requirement["version"],
                    scope=self._scope_from_requirement_file(path),
                    source_file=str(path),
                    source_line=requirement["line"],
                    metadata={
                        "ecosystem": self.ecosystem,
                        "package_manager": "pip",
                        "source_path": str(path),
                        "direct": True,
                    },
                ).graph_metadata(),
            )
        return ResolvedProjectGraph(
            root_identifier=root_identifier,
            graph=graph,
            ecosystem=self.ecosystem,
        )

    def parse_pyproject_graph(self, path: Path) -> ResolvedProjectGraph:
        payload = self._load_toml(path)
        project = self._mapping(payload.get("project"))
        poetry = self._mapping(self._mapping(payload.get("tool")).get("poetry"))
        root_name = str(poetry.get("name") or project.get("name") or "pyproject")
        root_version = str(poetry.get("version") or project.get("version") or "0.0.0")
        root_identifier = f"{root_name}=={root_version}"
        graph = CSRDependencyGraph()
        graph.add_vertex(
            root_identifier,
            metadata=self._root_metadata(
                root_name,
                root_version,
                source_file=path,
                package_manager="pyproject",
            ),
        )
        for dependency in self._pyproject_dependencies(payload):
            package_id = self._requirement_identifier(dependency)
            graph.add_vertex(
                package_id,
                metadata=self._requirement_metadata(
                    dependency,
                    source_file=path,
                    package_manager="pyproject",
                ),
            )
            graph.add_dependency_edge(
                root_identifier,
                package_id,
                metadata=DependencyEdge(
                    from_package=root_identifier,
                    to_package=package_id,
                    constraint=dependency["constraint"],
                    resolved_version=dependency["version"],
                    scope=dependency["scope"],
                    source_file=str(path),
                    source_line=dependency["line"],
                    metadata={
                        "ecosystem": self.ecosystem,
                        "package_manager": "pyproject",
                        "dependency_group": dependency.get("group", ""),
                        "direct": True,
                    },
                ).graph_metadata(),
            )
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

    def _component_metadata(
        self,
        record: Mapping[str, object],
        *,
        source_file: Path,
    ) -> dict[str, object]:
        category = record.get("category")
        groups = record.get("groups")
        if category is None and isinstance(groups, list) and "main" in groups:
            category = "main"
        name = str(record.get("name") or "")
        version = str(record.get("version") or "")
        metadata: dict[str, object] = Package(
            ecosystem=self.ecosystem,
            name=name,
            version=version,
            license=str(record.get("license") or ""),
            checksum=self._poetry_files_checksum(record),
            metadata={
                "source": source_file.name,
                "node_type": "package",
                "package_manager": "poetry",
                "classification": "transitive",
                "direct_dependency": False,
                "transitive_dependency": True,
                "dependency_scope": self._scope_from_poetry_record(record),
            },
        ).graph_metadata()
        optional_fields = {
            "category": category,
            "groups": groups,
            "optional": record.get("optional"),
            "python_versions": record.get("python-versions"),
            "description": record.get("description"),
        }
        for key, value in optional_fields.items():
            if value is not None:
                metadata[key] = value
        files = record.get("files")
        if isinstance(files, list) and files:
            metadata["artifact_count"] = len(files)
            metadata["artifact_type"] = "wheel_or_source_archive"
        return metadata

    def _normalize_name(self, name: str) -> str:
        return name.lower().replace("_", "-").replace(".", "-")

    def _root_metadata(
        self,
        name: str,
        version: str,
        *,
        source_file: Path,
        package_manager: str,
    ) -> dict[str, object]:
        return Package(
            ecosystem=self.ecosystem,
            name=name,
            version=version,
            metadata={
                "source": source_file.name,
                "node_type": "root",
                "package_manager": package_manager,
                "classification": "root",
                "direct_dependency": False,
                "transitive_dependency": False,
                "dependency_scope": "runtime",
            },
        ).graph_metadata()

    def _requirement_metadata(
        self,
        requirement: Mapping[str, object],
        *,
        source_file: Path,
        package_manager: str,
    ) -> dict[str, object]:
        hashes = requirement.get("hashes", [])
        checksum = ",".join(str(item) for item in hashes) if isinstance(hashes, list) else ""
        return Package(
            ecosystem=self.ecosystem,
            name=str(requirement["name"]),
            version=str(requirement.get("version", "")),
            source_url=str(requirement.get("source_url", "")),
            checksum=checksum,
            metadata={
                "source": source_file.name,
                "node_type": "package",
                "package_manager": package_manager,
                "classification": "direct",
                "direct_dependency": True,
                "transitive_dependency": False,
                "dependency_scope": requirement.get("scope", "runtime"),
                "constraint": requirement.get("constraint", ""),
                "marker": requirement.get("marker", ""),
                "extras": ",".join(requirement.get("extras", [])),
                "artifact_type": requirement.get("artifact_type", ""),
                "source_line": requirement.get("line", ""),
            },
        ).graph_metadata()

    def _parse_requirements(self, path: Path) -> list[dict[str, object]]:
        requirements: list[dict[str, object]] = []
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            parsed = self._parse_requirement_line(raw_line, line=line_number)
            if parsed is not None:
                parsed["scope"] = self._scope_from_requirement_file(path)
                requirements.append(parsed)
        return requirements

    def _parse_requirement_line(
        self,
        raw_line: str,
        *,
        line: int,
        scope: str = "runtime",
        group: str = "",
    ) -> dict[str, object] | None:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            return None
        if stripped.startswith(("-r ", "--requirement", "-c ", "--constraint", "--index-url", "--extra-index-url")):
            return None

        hashes = REQUIREMENT_HASH_RE.findall(stripped)
        requirement_text = REQUIREMENT_HASH_RE.sub("", stripped).strip()
        requirement_text = requirement_text.split(" #", 1)[0].strip()
        marker = ""
        if ";" in requirement_text:
            requirement_text, marker = [part.strip() for part in requirement_text.split(";", 1)]
        if requirement_text.startswith("-e "):
            requirement_text = requirement_text[3:].strip()

        source_url = ""
        if " @ " in requirement_text:
            name_part, source_url = requirement_text.split(" @ ", 1)
            name, extras = self._requirement_name_extras(name_part)
            return {
                "name": name,
                "version": "",
                "constraint": source_url,
                "source_url": source_url,
                "hashes": hashes,
                "marker": marker,
                "extras": extras,
                "scope": scope,
                "group": group,
                "line": line,
                "artifact_type": self._artifact_type_from_url(source_url),
            }

        operator, position = self._first_requirement_operator(requirement_text)
        if operator:
            name_part = requirement_text[:position].strip()
            specifier = requirement_text[position:].strip()
            version = requirement_text[position + len(operator) :].strip()
            if operator not in {"==", "==="}:
                version = ""
        else:
            name_part = requirement_text
            specifier = ""
            version = ""
        name, extras = self._requirement_name_extras(name_part)
        if not name:
            return None
        return {
            "name": name,
            "version": version,
            "constraint": specifier,
            "source_url": source_url,
            "hashes": hashes,
            "marker": marker,
            "extras": extras,
            "scope": scope,
            "group": group,
            "line": line,
            "artifact_type": "",
        }

    def _pyproject_dependencies(
        self,
        payload: Mapping[str, object],
    ) -> list[dict[str, object]]:
        dependencies: list[dict[str, object]] = []
        project = self._mapping(payload.get("project"))
        for raw_dependency in project.get("dependencies", []) or []:
            if isinstance(raw_dependency, str):
                parsed = self._parse_requirement_line(raw_dependency, line=0)
                if parsed is not None:
                    dependencies.append(parsed)

        optional = self._mapping(project.get("optional-dependencies"))
        for group, raw_dependencies in optional.items():
            if not isinstance(raw_dependencies, list):
                continue
            for raw_dependency in raw_dependencies:
                if not isinstance(raw_dependency, str):
                    continue
                parsed = self._parse_requirement_line(
                    raw_dependency,
                    line=0,
                    scope=self._scope_from_group(str(group)),
                    group=str(group),
                )
                if parsed is not None:
                    dependencies.append(parsed)

        poetry = self._mapping(self._mapping(payload.get("tool")).get("poetry"))
        for dependency in self._poetry_dependency_table(
            self._mapping(poetry.get("dependencies")),
            scope="runtime",
            group="main",
        ):
            dependencies.append(dependency)
        group_table = self._mapping(poetry.get("group"))
        for group, group_record in group_table.items():
            if not isinstance(group_record, Mapping):
                continue
            dependencies.extend(
                self._poetry_dependency_table(
                    self._mapping(group_record.get("dependencies")),
                    scope=self._scope_from_group(str(group)),
                    group=str(group),
                )
            )

        return sorted(
            dependencies,
            key=lambda item: (str(item.get("scope", "")), str(item["name"])),
        )

    def _poetry_dependency_table(
        self,
        dependency_table: Mapping[str, object],
        *,
        scope: str,
        group: str,
    ) -> list[dict[str, object]]:
        dependencies: list[dict[str, object]] = []
        for name, constraint in dependency_table.items():
            if str(name).lower() == "python":
                continue
            source_url = ""
            extras: list[str] = []
            if isinstance(constraint, Mapping):
                source_url = str(constraint.get("url") or constraint.get("git") or constraint.get("path") or "")
                extras = [str(item) for item in constraint.get("extras", [])] if isinstance(constraint.get("extras"), list) else []
                constraint_text = str(constraint.get("version") or source_url or "*")
            else:
                constraint_text = str(constraint or "*")
            dependencies.append(
                {
                    "name": self._normalize_name(str(name)),
                    "version": self._exact_version_from_constraint(constraint_text),
                    "constraint": constraint_text,
                    "source_url": source_url,
                    "hashes": [],
                    "marker": "",
                    "extras": extras,
                    "scope": scope,
                    "group": group,
                    "line": 0,
                    "artifact_type": self._artifact_type_from_url(source_url),
                }
            )
        return dependencies

    def _requirement_identifier(self, requirement: Mapping[str, object]) -> str:
        version = str(requirement.get("version") or "")
        constraint = str(requirement.get("constraint") or "")
        return f"{requirement['name']}=={version or constraint or 'unresolved'}"

    def _first_requirement_operator(self, requirement_text: str) -> tuple[str, int]:
        matches = [
            (operator, requirement_text.find(operator))
            for operator in REQUIREMENT_OPERATORS
            if requirement_text.find(operator) > 0
        ]
        if not matches:
            return "", -1
        return min(matches, key=lambda item: item[1])

    def _exact_version_from_constraint(self, constraint: str) -> str:
        constraint = constraint.strip()
        for operator in ("===", "=="):
            if constraint.startswith(operator):
                return constraint.removeprefix(operator).strip()
        return ""

    def _requirement_name_extras(self, name_part: str) -> tuple[str, list[str]]:
        name_part = name_part.strip()
        if "[" not in name_part:
            return self._normalize_name(name_part), []
        name, extras = name_part.split("[", 1)
        extras = extras.split("]", 1)[0]
        return self._normalize_name(name), [
            item.strip()
            for item in extras.split(",")
            if item.strip()
        ]

    def _scope_from_requirement_file(self, path: Path) -> str:
        name = path.name.lower()
        if "dev" in name:
            return "dev"
        if "test" in name:
            return "test"
        if "build" in name:
            return "build"
        return "runtime"

    def _scope_from_group(self, group: str) -> str:
        normalized = group.lower()
        if normalized in {"dev", "develop"}:
            return "dev"
        if normalized in {"test", "tests"}:
            return "test"
        if normalized == "build":
            return "build"
        return "optional"

    def _scope_from_poetry_record(self, record: Mapping[str, object]) -> str:
        groups = record.get("groups")
        if isinstance(groups, list):
            if "dev" in groups:
                return "dev"
            if "test" in groups:
                return "test"
            if "main" in groups:
                return "runtime"
        if record.get("optional"):
            return "optional"
        return "runtime"

    def _poetry_dependency_constraint(self, value: object) -> str:
        if isinstance(value, Mapping):
            return str(value.get("version") or value.get("url") or value.get("git") or value.get("path") or "*")
        return str(value)

    def _poetry_files_checksum(self, record: Mapping[str, object]) -> str:
        files = record.get("files")
        if not isinstance(files, list):
            return ""
        hashes = []
        for item in files:
            if isinstance(item, Mapping) and item.get("hash"):
                hashes.append(str(item["hash"]))
        return ",".join(hashes)

    def _artifact_type_from_url(self, source_url: str) -> str:
        lowered = source_url.lower()
        if lowered.endswith(".whl"):
            return "wheel"
        if lowered.endswith((".tar.gz", ".zip", ".tgz")):
            return "source_archive"
        return ""

    def _is_requirements_file(self, path: Path) -> bool:
        return path.name.startswith("requirements") and path.suffix in {".txt", ".in"}

    def _mapping(self, value: object) -> dict[str, object]:
        if not isinstance(value, Mapping):
            return {}
        return {str(key): item for key, item in value.items()}

    def _load_toml(self, path: Path) -> dict[str, object]:
        with path.open("rb") as handle:
            payload = tomllib.load(handle)
        return payload
