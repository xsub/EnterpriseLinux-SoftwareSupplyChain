from __future__ import annotations

import json
from pathlib import Path

from src.adapters.base import LockfileAdapter, ProjectManifest
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
