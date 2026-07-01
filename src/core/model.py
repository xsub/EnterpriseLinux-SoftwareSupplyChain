"""Normalized package, dependency, and artifact model primitives."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping
from urllib.parse import quote, urlencode


@dataclass(frozen=True)
class Package:
    """A package release normalized across source ecosystems."""

    ecosystem: str
    name: str
    version: str = ""
    purl: str = ""
    source_url: str = ""
    license: str = ""
    checksum: str = ""
    signature: str = ""
    provenance: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "ecosystem", self.ecosystem.strip().lower())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "version", self.version.strip())
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )

    @property
    def identifier(self) -> str:
        if self.version:
            return f"{self.name}=={self.version}"
        return self.name

    def graph_metadata(self) -> dict[str, object]:
        """Return graph node metadata using the normalized package fields."""

        metadata = dict(self.metadata)
        metadata.update(
            {
                "ecosystem": self.ecosystem,
                "name": self.name,
            }
        )
        if self.version:
            metadata["version"] = self.version
        purl = self.purl or package_purl(self.ecosystem, self.name, self.version, metadata=metadata)
        if purl:
            metadata["purl"] = purl
        for key, value in (
            ("source_url", self.source_url),
            ("license", self.license),
            ("checksum", self.checksum),
            ("signature", self.signature),
            ("provenance", self.provenance),
        ):
            if value:
                metadata[key] = value
        return metadata


@dataclass(frozen=True)
class DependencyEdge:
    """A normalized dependency relationship between two package nodes."""

    from_package: str
    to_package: str
    constraint: str = ""
    resolved_version: str = ""
    scope: str = "runtime"
    source_file: str = ""
    source_line: int | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scope", (self.scope or "runtime").strip().lower())
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )

    def graph_metadata(self) -> dict[str, object]:
        metadata = dict(self.metadata)
        for key, value in (
            ("constraint", self.constraint),
            ("resolved_version", self.resolved_version),
            ("scope", self.scope),
            ("source_file", self.source_file),
            ("source_line", self.source_line),
        ):
            if value not in (None, ""):
                metadata[key] = value
        return metadata


@dataclass(frozen=True)
class Artifact:
    """A normalized build or distribution artifact."""

    type: str
    name: str
    version: str = ""
    checksum: str = ""
    size: int | None = None
    origin: str = ""
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "type", self.type.strip())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "version", self.version.strip())
        object.__setattr__(
            self,
            "metadata",
            MappingProxyType(dict(self.metadata)),
        )


def package_purl(
    ecosystem: str,
    name: str,
    version: str = "",
    *,
    namespace: str = "",
    metadata: Mapping[str, object] | None = None,
) -> str:
    """Generate a Package URL for supported ecosystems."""

    ecosystem = ecosystem.strip().lower()
    name = name.strip()
    version = version.strip()
    metadata = metadata or {}

    if ecosystem == "npm":
        namespace, package_name = _npm_namespace_and_name(name, namespace=namespace)
        if namespace:
            path = f"{quote(namespace, safe='')}/{quote(package_name, safe='')}"
        else:
            path = quote(package_name, safe="")
        return _versioned_purl("pkg:npm", path, version)

    if ecosystem == "rpm":
        namespace = namespace or str(metadata.get("namespace") or metadata.get("vendor") or "")
        if namespace:
            path = f"{quote(namespace.lower(), safe='')}/{quote(name, safe='')}"
        else:
            path = quote(name, safe="")
        qualifiers = {
            key: str(metadata[key])
            for key in ("arch", "distro", "epoch")
            if metadata.get(key)
        }
        suffix = f"?{urlencode(sorted(qualifiers.items()))}" if qualifiers else ""
        return f"{_versioned_purl('pkg:rpm', path, version)}{suffix}"

    if ecosystem == "pypi":
        return _versioned_purl("pkg:pypi", quote(name.lower(), safe=""), version)
    if ecosystem == "cargo":
        return _versioned_purl("pkg:cargo", quote(name.lower(), safe=""), version)
    if ecosystem == "maven":
        group = namespace or str(metadata.get("group") or "")
        artifact = str(metadata.get("artifact") or name.rsplit(":", 1)[-1])
        if group:
            path = f"{quote(group, safe='')}/{quote(artifact, safe='')}"
        else:
            path = quote(name, safe="")
        return _versioned_purl("pkg:maven", path, version)
    if ecosystem == "oci":
        return _versioned_purl("pkg:oci", quote(name, safe="/:"), version)
    return _versioned_purl("pkg:generic", quote(name, safe=""), version)


def _npm_namespace_and_name(name: str, *, namespace: str = "") -> tuple[str, str]:
    if namespace:
        return namespace, name.removeprefix(f"{namespace}/")
    if name.startswith("@") and "/" in name:
        return name.split("/", 1)
    return "", name


def _versioned_purl(prefix: str, path: str, version: str) -> str:
    if version:
        return f"{prefix}/{path}@{quote(version, safe='')}"
    return f"{prefix}/{path}"

