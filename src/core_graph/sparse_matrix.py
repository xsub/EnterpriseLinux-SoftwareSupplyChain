"""Compressed Sparse Row graph storage for resolved dependency topology."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    relationship_type: int = 1


class CSRDependencyGraph:
    """Directed dependency graph materialized as Compressed Sparse Row arrays."""

    def __init__(self) -> None:
        self.vertex_map: dict[str, int] = {}
        self.reverse_vertex_map: dict[int, str] = {}
        self.next_vertex_id = 0

        self.values: list[int] = []
        self.column_indices: list[int] = []
        self.row_pointers: list[int] = [0]

        self._adjacency: dict[int, dict[int, int]] = {}
        self._dirty = False

    def __len__(self) -> int:
        return self.next_vertex_id

    def add_vertex(self, package_id: str) -> int:
        if package_id not in self.vertex_map:
            vertex_id = self.next_vertex_id
            self.vertex_map[package_id] = vertex_id
            self.reverse_vertex_map[vertex_id] = package_id
            self._adjacency[vertex_id] = {}
            self.next_vertex_id += 1
            self._dirty = True
        return self.vertex_map[package_id]

    def add_dependency_edge(
        self, source_id: str, target_id: str, relationship_type: int = 1
    ) -> None:
        source = self.add_vertex(source_id)
        target = self.add_vertex(target_id)
        self._adjacency[source][target] = relationship_type
        self._dirty = True

    def get_dependencies(self, package_id: str) -> list[str]:
        self._materialize()
        if package_id not in self.vertex_map:
            return []
        vertex_id = self.vertex_map[package_id]
        start = self.row_pointers[vertex_id]
        end = self.row_pointers[vertex_id + 1]
        return [self.reverse_vertex_map[target] for target in self.column_indices[start:end]]

    def edges(self) -> Iterator[DependencyEdge]:
        self._materialize()
        for source in range(self.next_vertex_id):
            start = self.row_pointers[source]
            end = self.row_pointers[source + 1]
            for index in range(start, end):
                yield DependencyEdge(
                    source=self.reverse_vertex_map[source],
                    target=self.reverse_vertex_map[self.column_indices[index]],
                    relationship_type=self.values[index],
                )

    def to_adjacency_dict(self) -> dict[str, list[str]]:
        return {
            package_id: self.get_dependencies(package_id)
            for package_id in sorted(self.vertex_map)
        }

    def _materialize(self) -> None:
        if not self._dirty:
            return

        self.values = []
        self.column_indices = []
        self.row_pointers = [0]

        for source in range(self.next_vertex_id):
            for target, relationship_type in sorted(self._adjacency.get(source, {}).items()):
                self.values.append(relationship_type)
                self.column_indices.append(target)
            self.row_pointers.append(len(self.column_indices))

        self._dirty = False
