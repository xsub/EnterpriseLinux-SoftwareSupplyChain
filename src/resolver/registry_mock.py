"""In-memory package registry used for solver demos and deterministic tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from src.models.constraints import Version, VersionRange
from src.models.package import PackageVersion


class RegistryMock:
    """In-memory package registry used by the resolver and tests."""

    def __init__(self, packages: Mapping[str, list[PackageVersion]]) -> None:
        self._packages = {
            name: sorted(versions, key=lambda package: Version(package.version), reverse=True)
            for name, versions in packages.items()
        }

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "RegistryMock":
        packages: dict[str, list[PackageVersion]] = {}
        for name, versions in payload.items():
            if not isinstance(versions, Mapping):
                raise TypeError(f"Registry package {name!r} must map versions to records")
            packages[str(name)] = [
                PackageVersion.from_registry_record(str(name), str(version), record)
                for version, record in versions.items()
                if isinstance(record, Mapping)
            ]
        return cls(packages)

    @classmethod
    def from_json(cls, path: Path) -> "RegistryMock":
        with path.open("r", encoding="utf-8") as handle:
            return cls.from_mapping(json.load(handle))

    def package_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._packages))

    def versions(self, package_name: str) -> tuple[PackageVersion, ...]:
        return tuple(self._packages.get(package_name, ()))

    def package(self, package_name: str, version: str) -> PackageVersion:
        for candidate in self.versions(package_name):
            if candidate.version == version:
                return candidate
        raise KeyError(f"Package version not found: {package_name}=={version}")

    def matching_versions(self, package_name: str, constraint: str) -> tuple[PackageVersion, ...]:
        version_range = VersionRange(constraint)
        return tuple(
            candidate
            for candidate in self.versions(package_name)
            if version_range.allows(candidate.version)
        )
