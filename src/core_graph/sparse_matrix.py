"""Compressed Sparse Row graph storage backed by contiguous NumPy arrays."""

from __future__ import annotations

from collections.abc import Mapping
from collections import deque
from dataclasses import dataclass
from typing import Iterator

import numpy as np

_CSR_DTYPE = np.int32
_CSR_MAX = int(np.iinfo(_CSR_DTYPE).max)


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    relationship_type: int = 1


class CSRDependencyGraph:
    """Directed dependency graph materialized as C-contiguous CSR arrays."""

    def __init__(self) -> None:
        self.vertex_map: dict[str, int] = {}
        self.reverse_vertex_map: dict[int, str] = {}
        self.next_vertex_id = 0

        self.values = np.array([], dtype=_CSR_DTYPE)
        self.column_indices = np.array([], dtype=_CSR_DTYPE)
        self.row_pointers = np.array([0], dtype=_CSR_DTYPE)
        self.reverse_values = np.array([], dtype=_CSR_DTYPE)
        self.reverse_column_indices = np.array([], dtype=_CSR_DTYPE)
        self.reverse_row_pointers = np.array([0], dtype=_CSR_DTYPE)
        self.vertex_metadata: dict[str, dict[str, str]] = {}

        self._adjacency: dict[int, dict[int, int]] = {}
        self._dirty = False

    def __len__(self) -> int:
        return self.next_vertex_id

    def add_vertex(
        self, package_id: str, metadata: Mapping[str, object] | None = None
    ) -> int:
        if package_id not in self.vertex_map:
            if self.next_vertex_id >= _CSR_MAX:
                raise OverflowError("CSR vertex id exceeds np.int32 capacity")
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
        start = int(self.row_pointers[vertex_id])
        end = int(self.row_pointers[vertex_id + 1])
        return [
            self.reverse_vertex_map[int(target)]
            for target in self.column_indices[start:end]
        ]

    def get_dependents(self, package_id: str) -> list[str]:
        self._materialize()
        if package_id not in self.vertex_map:
            return []
        vertex_id = self.vertex_map[package_id]
        start = int(self.reverse_row_pointers[vertex_id])
        end = int(self.reverse_row_pointers[vertex_id + 1])
        return [
            self.reverse_vertex_map[int(source)]
            for source in self.reverse_column_indices[start:end]
        ]

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
            start = int(self.row_pointers[source])
            end = int(self.row_pointers[source + 1])
            for index in range(start, end):
                yield DependencyEdge(
                    source=self.reverse_vertex_map[source],
                    target=self.reverse_vertex_map[int(self.column_indices[index])],
                    relationship_type=int(self.values[index]),
                )

    def to_adjacency_dict(self) -> dict[str, list[str]]:
        return {
            package_id: self.get_dependencies(package_id)
            for package_id in sorted(self.vertex_map)
        }

    def storage_profile(self) -> dict[str, object]:
        """Return the materialized CSR array memory layout and byte footprint."""

        self._materialize()
        return {
            "layout": "numpy.int32.c_contiguous",
            "dtype": str(self.values.dtype),
            "valuesBytes": int(self.values.nbytes),
            "columnIndicesBytes": int(self.column_indices.nbytes),
            "rowPointersBytes": int(self.row_pointers.nbytes),
            "reverseValuesBytes": int(self.reverse_values.nbytes),
            "reverseColumnIndicesBytes": int(self.reverse_column_indices.nbytes),
            "reverseRowPointersBytes": int(self.reverse_row_pointers.nbytes),
            "totalBytes": int(
                self.values.nbytes
                + self.column_indices.nbytes
                + self.row_pointers.nbytes
                + self.reverse_values.nbytes
                + self.reverse_column_indices.nbytes
                + self.reverse_row_pointers.nbytes
            ),
            "cContiguous": bool(
                self.values.flags.c_contiguous
                and self.column_indices.flags.c_contiguous
                and self.row_pointers.flags.c_contiguous
                and self.reverse_values.flags.c_contiguous
                and self.reverse_column_indices.flags.c_contiguous
                and self.reverse_row_pointers.flags.c_contiguous
            ),
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

        if self.next_vertex_id > _CSR_MAX:
            raise OverflowError("CSR vertex count exceeds np.int32 capacity")

        values: list[int] = []
        column_indices: list[int] = []
        row_pointers: list[int] = [0]
        reverse_adjacency: dict[int, dict[int, int]] = {
            vertex_id: {} for vertex_id in range(self.next_vertex_id)
        }

        for source in range(self.next_vertex_id):
            for target, relationship_type in sorted(self._adjacency.get(source, {}).items()):
                values.append(relationship_type)
                column_indices.append(target)
                reverse_adjacency[target][source] = relationship_type
            if len(column_indices) > _CSR_MAX:
                raise OverflowError("CSR edge count exceeds np.int32 capacity")
            row_pointers.append(len(column_indices))

        reverse_values: list[int] = []
        reverse_column_indices: list[int] = []
        reverse_row_pointers: list[int] = [0]
        for target in range(self.next_vertex_id):
            for source, relationship_type in sorted(reverse_adjacency[target].items()):
                reverse_values.append(relationship_type)
                reverse_column_indices.append(source)
            reverse_row_pointers.append(len(reverse_column_indices))

        self.values = np.ascontiguousarray(values, dtype=_CSR_DTYPE)
        self.column_indices = np.ascontiguousarray(column_indices, dtype=_CSR_DTYPE)
        self.row_pointers = np.ascontiguousarray(row_pointers, dtype=_CSR_DTYPE)
        self.reverse_values = np.ascontiguousarray(reverse_values, dtype=_CSR_DTYPE)
        self.reverse_column_indices = np.ascontiguousarray(
            reverse_column_indices,
            dtype=_CSR_DTYPE,
        )
        self.reverse_row_pointers = np.ascontiguousarray(
            reverse_row_pointers,
            dtype=_CSR_DTYPE,
        )

        self._dirty = False
