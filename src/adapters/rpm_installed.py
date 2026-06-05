"""Installed RPM database ingestion for AlmaLinux-compatible hosts."""

from __future__ import annotations

import subprocess
from collections.abc import Callable

from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph

CommandRunner = Callable[[list[str]], str]


class InstalledRpmAdapter:
    """Build a dependency graph from the local RPM database."""

    ecosystem = "rpm"

    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self._command_runner = command_runner or self._run

    def parse_installed(
        self,
        *,
        limit: int = 100,
        max_requirements: int = 40,
    ) -> ResolvedProjectGraph:
        graph = CSRDependencyGraph()
        packages = self._installed_packages(limit)
        provider_cache: dict[str, str | None] = {}
        root_identifier = "rpm-installed==local"
        graph.add_vertex(
            root_identifier,
            metadata={
                "ecosystem": self.ecosystem,
                "source": "rpmdb",
                "node_type": "root",
            },
        )

        for package in packages:
            graph.add_vertex(package.identifier, metadata=package.metadata)
            graph.add_dependency_edge(root_identifier, package.identifier)

            for requirement in self._requirements(package.name, max_requirements):
                provider_id = provider_cache.setdefault(
                    requirement, self._provider_identifier(requirement)
                )
                if provider_id is None or provider_id == package.identifier:
                    continue
                graph.add_vertex(
                    provider_id,
                    metadata={
                        "ecosystem": self.ecosystem,
                        "source": "rpmdb",
                    },
                )
                graph.add_dependency_edge(package.identifier, provider_id)

        return ResolvedProjectGraph(
            root_identifier=root_identifier,
            graph=graph,
            ecosystem=self.ecosystem,
        )

    def _installed_packages(self, limit: int) -> list["_RpmPackage"]:
        output = self._command_runner(
            ["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\n"]
        )
        packages: list[_RpmPackage] = []
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            packages.append(_RpmPackage(parts[0], parts[1], parts[2]))
            if len(packages) >= limit:
                break
        return packages

    def _requirements(self, package_name: str, max_requirements: int) -> list[str]:
        output = self._command_runner(["rpm", "-q", "--requires", package_name])
        requirements: list[str] = []
        for line in output.splitlines():
            requirement = line.strip()
            if not requirement or self._skip_requirement(requirement):
                continue
            requirements.append(requirement)
            if len(requirements) >= max_requirements:
                break
        return requirements

    def _provider_identifier(self, requirement: str) -> str | None:
        output = self._command_runner(
            [
                "rpm",
                "-q",
                "--whatprovides",
                requirement,
                "--qf",
                "%{NAME}\t%{VERSION}-%{RELEASE}\t%{ARCH}\n",
            ]
        )
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                return _RpmPackage(parts[0], parts[1], parts[2]).identifier
        return None

    def _skip_requirement(self, requirement: str) -> bool:
        return requirement.startswith(("rpmlib(", "config("))

    def _run(self, args: list[str]) -> str:
        completed = subprocess.run(
            args,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return ""
        return completed.stdout


class _RpmPackage:
    def __init__(self, name: str, version_release: str, arch: str) -> None:
        self.name = name
        self.version_release = version_release
        self.arch = arch

    @property
    def identifier(self) -> str:
        return f"{self.name}=={self.version_release}"

    @property
    def metadata(self) -> dict[str, str]:
        return {
            "ecosystem": "rpm",
            "source": "rpmdb",
            "arch": self.arch,
        }
