"""Public RPM repository metadata ingestion from repomd.xml and primary metadata."""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph

REL_RPM_REQUIRES = 30
REL_RPM_UNRESOLVED_REQUIRES = 31


class RpmRepositoryAdapter:
    """Build a CSR package universe graph from public RPM primary metadata."""

    ecosystem = "rpm"

    def parse_source(
        self,
        source: str | Path,
        *,
        repo_id: str = "public-rpm-repository",
        package_limit: int = 5000,
        requirement_limit: int = 40,
    ) -> ResolvedProjectGraph:
        metadata = load_repository_metadata(source)
        return self.parse_primary_bytes(
            metadata.primary_bytes,
            repo_id=repo_id,
            package_limit=package_limit,
            requirement_limit=requirement_limit,
            source_label=metadata.source_label,
            primary_location=metadata.primary_location,
        )

    def parse_primary(
        self,
        path: Path,
        *,
        repo_id: str = "public-rpm-repository",
        package_limit: int = 5000,
        requirement_limit: int = 40,
    ) -> ResolvedProjectGraph:
        return self.parse_source(
            path,
            repo_id=repo_id,
            package_limit=package_limit,
            requirement_limit=requirement_limit,
        )

    def parse_primary_bytes(
        self,
        data: bytes,
        *,
        repo_id: str = "public-rpm-repository",
        package_limit: int = 5000,
        requirement_limit: int = 40,
        source_label: str = "rpm-primary",
        primary_location: str = "",
    ) -> ResolvedProjectGraph:
        packages = _parse_primary_packages(data, package_limit=package_limit)
        graph = CSRDependencyGraph()
        root = f"rpm-repository=={repo_id}"
        graph.add_vertex(
            root,
            metadata={
                "ecosystem": self.ecosystem,
                "source": "rpm-primary",
                "node_type": "root",
                "repo_id": repo_id,
                "source_label": source_label,
                "primary_location": primary_location,
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
        return ResolvedProjectGraph(
            root_identifier=root,
            graph=graph,
            ecosystem=self.ecosystem,
        )


@dataclass(frozen=True)
class RepositoryMetadata:
    primary_bytes: bytes
    primary_location: str
    source_label: str


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


def load_repository_metadata(source: str | Path) -> RepositoryMetadata:
    """Load primary metadata from a local/remote primary file or repomd source."""

    source_text = str(source)
    if _is_url(source_text):
        return _load_remote_repository_metadata(source_text)
    return _load_local_repository_metadata(Path(source))


def _load_local_repository_metadata(path: Path) -> RepositoryMetadata:
    if _looks_like_repomd(path.name):
        repomd = path.read_bytes()
        primary_href = _primary_href(repomd)
        if not primary_href:
            raise ValueError(f"repomd.xml does not reference primary metadata: {path}")
        primary_path = (path.parent / primary_href).resolve()
        return RepositoryMetadata(
            primary_bytes=_maybe_decompress(primary_path.read_bytes(), str(primary_path)),
            primary_location=str(primary_path),
            source_label=str(path),
        )
    return RepositoryMetadata(
        primary_bytes=_maybe_decompress(path.read_bytes(), str(path)),
        primary_location=str(path),
        source_label=str(path),
    )


def _load_remote_repository_metadata(source: str) -> RepositoryMetadata:
    if _looks_like_primary(source):
        return RepositoryMetadata(
            primary_bytes=_maybe_decompress(_fetch_bytes(source), source),
            primary_location=source,
            source_label=source,
        )
    repomd_url = _remote_repomd_url(source)
    repomd = _fetch_bytes(repomd_url)
    primary_href = _primary_href(repomd)
    if not primary_href:
        raise ValueError(f"repomd.xml does not reference primary metadata: {repomd_url}")
    primary_url = urljoin(repomd_url, primary_href)
    return RepositoryMetadata(
        primary_bytes=_maybe_decompress(_fetch_bytes(primary_url), primary_url),
        primary_location=primary_url,
        source_label=repomd_url,
    )


def _parse_primary_packages(data: bytes, *, package_limit: int) -> list[_RpmRepoPackage]:
    root = ET.fromstring(data)
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


def _primary_href(repomd_bytes: bytes) -> str:
    root = ET.fromstring(repomd_bytes)
    for data in root.findall(".//{*}data"):
        if data.attrib.get("type") != "primary":
            continue
        location = data.find("{*}location")
        if location is not None:
            href = location.attrib.get("href", "")
            if href:
                return href
    return ""


def _maybe_decompress(data: bytes, location: str) -> bytes:
    if location.endswith(".gz"):
        return gzip.decompress(data)
    return data


def _fetch_bytes(url: str, *, timeout: float = 30.0) -> bytes:
    request = Request(url, headers={"User-Agent": "edgp-rpm-repository/0.1"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _remote_repomd_url(source: str) -> str:
    if source.endswith("/repodata/repomd.xml") or source.endswith("repomd.xml"):
        return source
    return f"{source.rstrip('/')}/repodata/repomd.xml"


def _looks_like_repomd(name: str) -> bool:
    return name.endswith("repomd.xml")


def _looks_like_primary(value: str) -> bool:
    return (
        value.endswith("primary.xml")
        or value.endswith("primary.xml.gz")
        or "-primary.xml.gz" in value
    )


def _is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


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
