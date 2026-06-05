"""Package release and dependency requirement models for registry metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class DependencyRequirement:
    """A package dependency and the version constraint it requires."""

    name: str
    constraint: str = "*"

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "constraint", (self.constraint or "*").strip())


@dataclass(frozen=True)
class PackageVersion:
    """A concrete package release as it appears in an external registry."""

    name: str
    version: str
    dependencies: tuple[DependencyRequirement, ...] = field(default_factory=tuple)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "version", self.version.strip())
        object.__setattr__(self, "dependencies", tuple(self.dependencies))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def identifier(self) -> str:
        return f"{self.name}=={self.version}"

    @classmethod
    def from_registry_record(
        cls, name: str, version: str, record: Mapping[str, object] | None = None
    ) -> "PackageVersion":
        record = record or {}
        dependencies = record.get("dependencies", {})
        parsed_dependencies: list[DependencyRequirement] = []

        if isinstance(dependencies, Mapping):
            parsed_dependencies = [
                DependencyRequirement(dep_name, str(dep_constraint))
                for dep_name, dep_constraint in dependencies.items()
            ]
        elif isinstance(dependencies, list):
            for item in dependencies:
                if isinstance(item, Mapping):
                    parsed_dependencies.append(
                        DependencyRequirement(str(item["name"]), str(item.get("constraint", "*")))
                    )

        metadata = record.get("metadata", {})
        if not isinstance(metadata, Mapping):
            metadata = {}

        return cls(
            name=name,
            version=version,
            dependencies=tuple(parsed_dependencies),
            metadata={str(key): str(value) for key, value in metadata.items()},
        )
