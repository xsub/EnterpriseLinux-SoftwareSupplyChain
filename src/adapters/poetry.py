from __future__ import annotations

import tomllib
from pathlib import Path

from src.adapters.base import LockfileAdapter, ProjectManifest
from src.models.package import DependencyRequirement


class PoetryAdapter(LockfileAdapter):
    ecosystem = "poetry"

    def supports(self, path: Path) -> bool:
        return path.name == "pyproject.toml"

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
