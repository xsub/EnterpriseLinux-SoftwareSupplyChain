"""Public RPM repository metadata ingestion from primary.xml documents."""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from pathlib import Path

from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph

REL_RPM_REQUIRES = 30
REL_RPM_UNRESOLVED_REQUIRES = 31


class RpmRepositoryAdapter:
    """Build a CSR package universe graph from public RPM primary metadata."""

    ecosystem = "rpm"

    def parse_primary(
        self,
        path: Path,
        *,
        repo_id: str = "public-rpm-repository",
        package_limit: int = 5000,
        requirement_limit: int = 40,
    ) -> ResolvedProjectGraph:
        packages = _parse_primary_packages(path, package_limit=package_limit)
        graph = CSRDependencyGraph()
        root = f"rpm-repository=={repo_id}"
        graph.add_vertex(
            root,
            metadata={
                "ecosystem": self.ecosystem,
                "source": "rpm-primary",
                "node_type": "root",
                "repo_id": repo_id,
            },
        )
        provider_index = _provider_index(packages)
        for package in packages:
            graph.add_vertex(package.identifier, metadata=package.metadata)
            graph.add_dependency_edge(root, package.identifier)
        for package in packages:
            for requirement in package.requires[: max(requirement_limit, 0)]:
                providers = [
                    provider
                    for provider in provider_index.get(requirement.name, [])
                    if provider.identifier != package.identifier
                ]
                if providers:
                    for provider in providers:
                        graph.add_dependency_edge(
                            package.identifier,
                            provider.identifier,
                            REL_RPM_REQUIRES,
                        )
                    continue
                capability_id = f"rpm-capability:{requirement.name}"
                graph.add_vertex(
                    capability_id,
                    metadata={
                        "ecosystem": self.ecosystem,
                        "source": "rpm-primary",
                        "node_type": "unresolved_requirement",
                        "capability": requirement.name,
                    },
                )
                graph.add_dependency_edge(
                    package.identifier,
                    capability_id,
                    REL_RPM_UNRESOLVED_REQUIRES,
                )
        return ResolvedProjectGraph(root_identifier=root, graph=graph, ecosystem=self.ecosystem)


class _RpmRepoPackage:
    def __init__(
        self,
        *,
        name: str,
        epoch: str,
        version: str,
        release: str,
        arch: str,
        summary: str,
        source_rpm: str,
        provides: list["_RpmCapability"],
        requires: list["_RpmCapability"],
    ) -> None:
        self.name = name
        self.epoch = epoch
        self.version = version
        self.release = release
        self.arch = arch
        self.summary = summary
        self.source_rpm = source_rpm
        self.provides = provides
        self.requires = requires

    @property
    def identifier(self) -> str:
        return f"{self.name}=={self.version}-{self.release}.{self.arch}"

    @property
    def metadata(self) -> dict[str, str]:
        metadata = {
            "ecosystem": "rpm",
            "source": "rpm-primary",
            "node_type": "package",
            "name": self.name,
            "version": self.version,
            "release": self.release,
            "arch": self.arch,
        }
        if self.epoch and self.epoch not in ("0", "(none)"):
            metadata["epoch"] = self.epoch
        if self.summary:
            metadata["summary"] = self.summary
        if self.source_rpm:
            metadata["source_rpm"] = self.source_rpm
        return metadata


class _RpmCapability:
    def __init__(self, name: str) -> None:
        self.name = name


def _parse_primary_packages(path: Path, *, package_limit: int) -> list[_RpmRepoPackage]:
    root = ET.fromstring(_read_primary_bytes(path))
    packages: list[_RpmRepoPackage] = []
    for package_element in root.findall(".//{*}package"):
        if len(packages) >= max(package_limit, 0):
            break
        version = package_element.find("{*}version")
        format_element = package_element.find("{*}format")
        if version is None or format_element is None:
            continue
        packages.append(
            _RpmRepoPackage(
                name=_text(package_element.find("{*}name")),
                epoch=version.attrib.get("epoch", "0"),
                version=version.attrib.get("ver", ""),
                release=version.attrib.get("rel", ""),
                arch=_text(package_element.find("{*}arch")),
                summary=_text(package_element.find("{*}summary")),
                source_rpm=_text(format_element.find("{*}sourcerpm")),
                provides=_capabilities(format_element.find("{*}provides")),
                requires=_capabilities(format_element.find("{*}requires")),
            )
        )
    return packages


def _read_primary_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix == ".gz":
        return gzip.decompress(data)
    return data


def _capabilities(parent: ET.Element | None) -> list[_RpmCapability]:
    if parent is None:
        return []
    capabilities = []
    for entry in parent.findall("{*}entry"):
        name = entry.attrib.get("name", "")
        if name and not name.startswith(("rpmlib(", "config(")):
            capabilities.append(_RpmCapability(name))
    return capabilities


def _provider_index(
    packages: list[_RpmRepoPackage],
) -> dict[str, list[_RpmRepoPackage]]:
    providers: dict[str, list[_RpmRepoPackage]] = {}
    for package in packages:
        providers.setdefault(package.name, []).append(package)
        for capability in package.provides:
            providers.setdefault(capability.name, []).append(package)
    return providers


def _text(element: ET.Element | None) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()
