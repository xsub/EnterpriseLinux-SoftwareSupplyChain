"""Shared adapter contracts for project manifests and resolved graph imports."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.models.package import DependencyRequirement


@dataclass(frozen=True)
class ProjectManifest:
    root_name: str
    root_version: str = "0.0.0"
    direct_dependencies: tuple[DependencyRequirement, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ResolvedProjectGraph:
    root_identifier: str
    graph: CSRDependencyGraph
    ecosystem: str


class LockfileAdapter(ABC):
    ecosystem: str

    @abstractmethod
    def supports(self, path: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, path: Path) -> ProjectManifest:
        raise NotImplementedError
