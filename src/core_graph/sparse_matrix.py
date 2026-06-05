"""Compressed Sparse Row graph storage for resolved dependency topology."""

from __future__ import annotations

from collections.abc import Mapping
from collections import deque
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
        self.vertex_metadata: dict[str, dict[str, str]] = {}

        self._adjacency: dict[int, dict[int, int]] = {}
        self._dirty = False

    def __len__(self) -> int:
        return self.next_vertex_id

    def add_vertex(
        self, package_id: str, metadata: Mapping[str, object] | None = None
    ) -> int:
        if package_id not in self.vertex_map:
            vertex_id = self.next_vertex_id
            self.vertex_map[package_id] = vertex_id
            self.reverse_vertex_map[vertex_id] = package_id
            self.vertex_metadata[package_id] = {}
            self._adjacency[vertex_id] = {}
            self.next_vertex_id += 1
            self._dirty = True
        if metadata:
            self.set_vertex_metadata(package_id, metadata)
        return self.vertex_map[package_id]

    def set_vertex_metadata(
        self, package_id: str, metadata: Mapping[str, object]
    ) -> None:
        self.add_vertex(package_id)
        current = self.vertex_metadata.setdefault(package_id, {})
        for key, value in metadata.items():
            if value is None:
                continue
            current[str(key)] = str(value)

    def get_vertex_metadata(self, package_id: str) -> dict[str, str]:
        return dict(self.vertex_metadata.get(package_id, {}))

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

    def get_dependents(self, package_id: str) -> list[str]:
        self._materialize()
        if package_id not in self.vertex_map:
            return []

        target_id = self.vertex_map[package_id]
        dependents: list[str] = []
        for source in range(self.next_vertex_id):
            start = self.row_pointers[source]
            end = self.row_pointers[source + 1]
            if target_id in self.column_indices[start:end]:
                dependents.append(self.reverse_vertex_map[source])
        return dependents

    def reachable_dependencies(self, package_id: str) -> list[str]:
        return self._reachable(package_id, self.get_dependencies)

    def reachable_dependents(self, package_id: str) -> list[str]:
        return self._reachable(package_id, self.get_dependents)

    def shortest_dependency_path(
        self, source_id: str, target_id: str, *, reverse: bool = False
    ) -> list[str]:
        self._materialize()
        if source_id not in self.vertex_map or target_id not in self.vertex_map:
            return []

        neighbors = self.get_dependents if reverse else self.get_dependencies
        queue: deque[list[str]] = deque([[source_id]])
        visited = {source_id}

        while queue:
            path = queue.popleft()
            current = path[-1]
            if current == target_id:
                return path
            for neighbor in neighbors(current):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append([*path, neighbor])

        return []

    def most_depended_upon(self, limit: int = 10) -> list[tuple[str, int]]:
        self._materialize()
        incoming_counts = {package_id: 0 for package_id in self.vertex_map}
        for edge in self.edges():
            incoming_counts[edge.target] += 1
        ranked = sorted(
            ((package_id, count) for package_id, count in incoming_counts.items() if count),
            key=lambda item: (-item[1], item[0]),
        )
        return ranked[:limit]

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

    def _reachable(self, package_id: str, neighbor_fn) -> list[str]:
        self._materialize()
        if package_id not in self.vertex_map:
            return []

        queue: deque[str] = deque(neighbor_fn(package_id))
        visited: set[str] = set()
        reachable: list[str] = []

        while queue:
            current = queue.popleft()
            if current in visited or current == package_id:
                continue
            visited.add(current)
            reachable.append(current)
            queue.extend(neighbor_fn(current))

        return reachable

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
