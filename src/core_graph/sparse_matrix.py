"""Compressed Sparse Row graph storage backed by contiguous NumPy arrays."""

from __future__ import annotations

from collections.abc import Mapping
from collections import deque
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterator

import numpy as np

from src.core_graph.accelerators import (
    maybe_numba_reachable_ids,
    select_traversal_backend,
)

_CSR_DTYPE = np.int32
_CSR_MAX = int(np.iinfo(_CSR_DTYPE).max)


@dataclass(frozen=True)
class DependencyEdge:
    source: str
    target: str
    relationship_type: int = 1


@dataclass(frozen=True, eq=False)
class FrozenCSRGraph:
    """Immutable CSR runtime snapshot for read-only graph traversal."""

    vertex_map: Mapping[str, int]
    package_ids: tuple[str, ...]
    values: np.ndarray
    column_indices: np.ndarray
    row_pointers: np.ndarray
    reverse_values: np.ndarray
    reverse_column_indices: np.ndarray
    reverse_row_pointers: np.ndarray
    vertex_metadata: Mapping[str, Mapping[str, str]] = field(default_factory=dict)
    copy_arrays: bool = field(default=True, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "vertex_map", MappingProxyType(dict(self.vertex_map)))
        object.__setattr__(
            self,
            "vertex_metadata",
            MappingProxyType(
                {
                    package_id: MappingProxyType(dict(metadata))
                    for package_id, metadata in self.vertex_metadata.items()
                }
            ),
        )
        for name in (
            "values",
            "column_indices",
            "row_pointers",
            "reverse_values",
            "reverse_column_indices",
            "reverse_row_pointers",
        ):
            object.__setattr__(
                self,
                name,
                _readonly_csr_array(getattr(self, name), copy=self.copy_arrays),
            )
        self._validate_shape()

    def __len__(self) -> int:
        return len(self.package_ids)

    @property
    def next_vertex_id(self) -> int:
        return len(self.package_ids)

    def get_vertex_metadata(self, package_id: str) -> dict[str, str]:
        return dict(self.vertex_metadata.get(package_id, {}))

    def get_dependencies(self, package_id: str) -> list[str]:
        vertex_id = self.vertex_map.get(package_id)
        if vertex_id is None:
            return []
        return self._vertex_labels(self.get_dependency_ids(vertex_id))

    def get_dependency_ids(self, vertex_id: int) -> np.ndarray:
        if not self._is_valid_vertex_id(vertex_id):
            return np.array([], dtype=_CSR_DTYPE)
        start = int(self.row_pointers[vertex_id])
        end = int(self.row_pointers[vertex_id + 1])
        return self.column_indices[start:end]

    def get_dependents(self, package_id: str) -> list[str]:
        vertex_id = self.vertex_map.get(package_id)
        if vertex_id is None:
            return []
        return self._vertex_labels(self.get_dependent_ids(vertex_id))

    def get_dependent_ids(self, vertex_id: int) -> np.ndarray:
        if not self._is_valid_vertex_id(vertex_id):
            return np.array([], dtype=_CSR_DTYPE)
        start = int(self.reverse_row_pointers[vertex_id])
        end = int(self.reverse_row_pointers[vertex_id + 1])
        return self.reverse_column_indices[start:end]

    def reachable_dependencies(
        self, package_id: str, *, backend: str = "python"
    ) -> list[str]:
        vertex_id = self.vertex_map.get(package_id)
        if vertex_id is None:
            return []
        return self._vertex_labels(
            self.reachable_dependency_ids(vertex_id, backend=backend)
        )

    def reachable_dependency_ids(
        self, vertex_id: int, *, backend: str = "python"
    ) -> list[int]:
        return self._reachable_ids(vertex_id, reverse=False, backend=backend)

    def reachable_dependents(
        self, package_id: str, *, backend: str = "python"
    ) -> list[str]:
        vertex_id = self.vertex_map.get(package_id)
        if vertex_id is None:
            return []
        return self._vertex_labels(
            self.reachable_dependent_ids(vertex_id, backend=backend)
        )

    def reachable_dependent_ids(
        self, vertex_id: int, *, backend: str = "python"
    ) -> list[int]:
        return self._reachable_ids(vertex_id, reverse=True, backend=backend)

    def shortest_dependency_path(
        self, source_id: str, target_id: str, *, reverse: bool = False
    ) -> list[str]:
        source_vertex = self.vertex_map.get(source_id)
        target_vertex = self.vertex_map.get(target_id)
        if source_vertex is None or target_vertex is None:
            return []
        return self._vertex_labels(
            self.shortest_dependency_path_ids(
                source_vertex,
                target_vertex,
                reverse=reverse,
            )
        )

    def shortest_dependency_path_ids(
        self, source_id: int, target_id: int, *, reverse: bool = False
    ) -> list[int]:
        if not self._is_valid_vertex_id(source_id) or not self._is_valid_vertex_id(
            target_id
        ):
            return []

        neighbors = self.get_dependent_ids if reverse else self.get_dependency_ids
        queue: deque[list[int]] = deque([[source_id]])
        visited = {source_id}

        while queue:
            path = queue.popleft()
            current = path[-1]
            if current == target_id:
                return path
            for neighbor in neighbors(current):
                neighbor_id = int(neighbor)
                if neighbor_id in visited:
                    continue
                visited.add(neighbor_id)
                queue.append([*path, neighbor_id])

        return []

    def most_depended_upon(self, limit: int = 10) -> list[tuple[str, int]]:
        incoming_counts = np.bincount(
            self.column_indices,
            minlength=self.next_vertex_id,
        )
        ranked = sorted(
            (
                (self.package_ids[vertex_id], int(count))
                for vertex_id, count in enumerate(incoming_counts[: self.next_vertex_id])
                if count
            ),
            key=lambda item: (-item[1], item[0]),
        )
        return ranked[:limit]

    def edges(self) -> Iterator[DependencyEdge]:
        for source in range(self.next_vertex_id):
            start = int(self.row_pointers[source])
            end = int(self.row_pointers[source + 1])
            for index in range(start, end):
                yield DependencyEdge(
                    source=self.package_ids[source],
                    target=self.package_ids[int(self.column_indices[index])],
                    relationship_type=int(self.values[index]),
                )

    def to_adjacency_dict(self) -> dict[str, list[str]]:
        return {
            package_id: self.get_dependencies(package_id)
            for package_id in sorted(self.vertex_map)
        }

    def storage_profile(self) -> dict[str, object]:
        profile = _storage_profile(
            values=self.values,
            column_indices=self.column_indices,
            row_pointers=self.row_pointers,
            reverse_values=self.reverse_values,
            reverse_column_indices=self.reverse_column_indices,
            reverse_row_pointers=self.reverse_row_pointers,
        )
        profile["runtime"] = "frozen"
        profile["readOnly"] = bool(
            not self.values.flags.writeable
            and not self.column_indices.flags.writeable
            and not self.row_pointers.flags.writeable
            and not self.reverse_values.flags.writeable
            and not self.reverse_column_indices.flags.writeable
            and not self.reverse_row_pointers.flags.writeable
        )
        profile["memoryMapped"] = bool(
            isinstance(self.values, np.memmap)
            or isinstance(self.column_indices, np.memmap)
            or isinstance(self.row_pointers, np.memmap)
            or isinstance(self.reverse_values, np.memmap)
            or isinstance(self.reverse_column_indices, np.memmap)
            or isinstance(self.reverse_row_pointers, np.memmap)
        )
        return profile

    def save_artifact(self, output_dir) -> dict[str, object]:
        """Persist this frozen graph as a memory-mappable CSR artifact."""

        from src.core_graph.artifacts import write_frozen_csr_artifact

        return write_frozen_csr_artifact(self, output_dir)

    def _reachable_ids(
        self, vertex_id: int, *, reverse: bool, backend: str = "python"
    ) -> list[int]:
        if not self._is_valid_vertex_id(vertex_id):
            return []

        resolved_backend = select_traversal_backend(backend)
        row_pointers = self.reverse_row_pointers if reverse else self.row_pointers
        column_indices = (
            self.reverse_column_indices if reverse else self.column_indices
        )
        accelerated = maybe_numba_reachable_ids(
            row_pointers=row_pointers,
            column_indices=column_indices,
            start_vertex=vertex_id,
            vertex_count=self.next_vertex_id,
            backend=resolved_backend,
        )
        if accelerated is not None:
            return [int(vertex_id) for vertex_id in accelerated]

        neighbor_fn = self.get_dependent_ids if reverse else self.get_dependency_ids
        queue: deque[int] = deque(int(neighbor) for neighbor in neighbor_fn(vertex_id))
        visited: set[int] = set()
        reachable: list[int] = []

        while queue:
            current = queue.popleft()
            if current in visited or current == vertex_id:
                continue
            visited.add(current)
            reachable.append(current)
            queue.extend(int(neighbor) for neighbor in neighbor_fn(current))

        return reachable

    def _vertex_labels(self, vertex_ids) -> list[str]:
        return [self.package_ids[int(vertex_id)] for vertex_id in vertex_ids]

    def _is_valid_vertex_id(self, vertex_id: int) -> bool:
        return 0 <= vertex_id < self.next_vertex_id

    def _validate_shape(self) -> None:
        expected_rows = self.next_vertex_id + 1
        if len(self.row_pointers) != expected_rows:
            raise ValueError("forward CSR row pointer length does not match vertices")
        if len(self.reverse_row_pointers) != expected_rows:
            raise ValueError("reverse CSR row pointer length does not match vertices")
        if len(self.values) != len(self.column_indices):
            raise ValueError("forward CSR values and column indices differ")
        if len(self.reverse_values) != len(self.reverse_column_indices):
            raise ValueError("reverse CSR values and column indices differ")


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
        vertex_id = self.vertex_map.get(package_id)
        if vertex_id is None:
            return []
        return self._vertex_labels(self.get_dependency_ids(vertex_id))

    def get_dependency_ids(self, vertex_id: int) -> np.ndarray:
        self._materialize()
        if not self._is_valid_vertex_id(vertex_id):
            return np.array([], dtype=_CSR_DTYPE)
        start = int(self.row_pointers[vertex_id])
        end = int(self.row_pointers[vertex_id + 1])
        return self.column_indices[start:end]

    def get_dependents(self, package_id: str) -> list[str]:
        self._materialize()
        vertex_id = self.vertex_map.get(package_id)
        if vertex_id is None:
            return []
        return self._vertex_labels(self.get_dependent_ids(vertex_id))

    def get_dependent_ids(self, vertex_id: int) -> np.ndarray:
        self._materialize()
        if not self._is_valid_vertex_id(vertex_id):
            return np.array([], dtype=_CSR_DTYPE)
        start = int(self.reverse_row_pointers[vertex_id])
        end = int(self.reverse_row_pointers[vertex_id + 1])
        return self.reverse_column_indices[start:end]

    def reachable_dependencies(
        self, package_id: str, *, backend: str = "python"
    ) -> list[str]:
        self._materialize()
        vertex_id = self.vertex_map.get(package_id)
        if vertex_id is None:
            return []
        return self._vertex_labels(
            self.reachable_dependency_ids(vertex_id, backend=backend)
        )

    def reachable_dependency_ids(
        self, vertex_id: int, *, backend: str = "python"
    ) -> list[int]:
        return self._reachable_ids(vertex_id, reverse=False, backend=backend)

    def reachable_dependents(
        self, package_id: str, *, backend: str = "python"
    ) -> list[str]:
        self._materialize()
        vertex_id = self.vertex_map.get(package_id)
        if vertex_id is None:
            return []
        return self._vertex_labels(
            self.reachable_dependent_ids(vertex_id, backend=backend)
        )

    def reachable_dependent_ids(
        self, vertex_id: int, *, backend: str = "python"
    ) -> list[int]:
        return self._reachable_ids(vertex_id, reverse=True, backend=backend)

    def shortest_dependency_path(
        self, source_id: str, target_id: str, *, reverse: bool = False
    ) -> list[str]:
        self._materialize()
        source_vertex = self.vertex_map.get(source_id)
        target_vertex = self.vertex_map.get(target_id)
        if source_vertex is None or target_vertex is None:
            return []
        return self._vertex_labels(
            self.shortest_dependency_path_ids(
                source_vertex,
                target_vertex,
                reverse=reverse,
            )
        )

    def shortest_dependency_path_ids(
        self, source_id: int, target_id: int, *, reverse: bool = False
    ) -> list[int]:
        self._materialize()
        if not self._is_valid_vertex_id(source_id) or not self._is_valid_vertex_id(
            target_id
        ):
            return []

        neighbors = self.get_dependent_ids if reverse else self.get_dependency_ids
        queue: deque[list[int]] = deque([[source_id]])
        visited = {source_id}

        while queue:
            path = queue.popleft()
            current = path[-1]
            if current == target_id:
                return path
            for neighbor in neighbors(current):
                neighbor_id = int(neighbor)
                if neighbor_id in visited:
                    continue
                visited.add(neighbor_id)
                queue.append([*path, neighbor_id])

        return []

    def most_depended_upon(self, limit: int = 10) -> list[tuple[str, int]]:
        self._materialize()
        incoming_counts = np.bincount(
            self.column_indices,
            minlength=self.next_vertex_id,
        )
        ranked = sorted(
            (
                (self.reverse_vertex_map[vertex_id], int(count))
                for vertex_id, count in enumerate(incoming_counts[: self.next_vertex_id])
                if count
            ),
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
        return _storage_profile(
            values=self.values,
            column_indices=self.column_indices,
            row_pointers=self.row_pointers,
            reverse_values=self.reverse_values,
            reverse_column_indices=self.reverse_column_indices,
            reverse_row_pointers=self.reverse_row_pointers,
        )

    def freeze(self) -> FrozenCSRGraph:
        """Return an immutable read-only copy of the current CSR arrays."""

        self._materialize()
        package_ids = tuple(
            self.reverse_vertex_map[vertex_id]
            for vertex_id in range(self.next_vertex_id)
        )
        return FrozenCSRGraph(
            vertex_map=self.vertex_map,
            package_ids=package_ids,
            values=self.values,
            column_indices=self.column_indices,
            row_pointers=self.row_pointers,
            reverse_values=self.reverse_values,
            reverse_column_indices=self.reverse_column_indices,
            reverse_row_pointers=self.reverse_row_pointers,
            vertex_metadata=self.vertex_metadata,
        )

    def _reachable_ids(
        self, vertex_id: int, *, reverse: bool, backend: str = "python"
    ) -> list[int]:
        self._materialize()
        if not self._is_valid_vertex_id(vertex_id):
            return []

        resolved_backend = select_traversal_backend(backend)
        row_pointers = self.reverse_row_pointers if reverse else self.row_pointers
        column_indices = (
            self.reverse_column_indices if reverse else self.column_indices
        )
        accelerated = maybe_numba_reachable_ids(
            row_pointers=row_pointers,
            column_indices=column_indices,
            start_vertex=vertex_id,
            vertex_count=self.next_vertex_id,
            backend=resolved_backend,
        )
        if accelerated is not None:
            return [int(vertex_id) for vertex_id in accelerated]

        neighbor_fn = self.get_dependent_ids if reverse else self.get_dependency_ids
        queue: deque[int] = deque(int(neighbor) for neighbor in neighbor_fn(vertex_id))
        visited: set[int] = set()
        reachable: list[int] = []

        while queue:
            current = queue.popleft()
            if current in visited or current == vertex_id:
                continue
            visited.add(current)
            reachable.append(current)
            queue.extend(int(neighbor) for neighbor in neighbor_fn(current))

        return reachable

    def _vertex_labels(self, vertex_ids) -> list[str]:
        return [self.reverse_vertex_map[int(vertex_id)] for vertex_id in vertex_ids]

    def _is_valid_vertex_id(self, vertex_id: int) -> bool:
        return 0 <= vertex_id < self.next_vertex_id

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


def _readonly_csr_array(values: np.ndarray, *, copy: bool = True) -> np.ndarray:
    if copy:
        array = np.ascontiguousarray(values, dtype=_CSR_DTYPE).copy()
    else:
        array = np.asanyarray(values, dtype=_CSR_DTYPE)
        if not array.flags.c_contiguous:
            array = np.ascontiguousarray(array, dtype=_CSR_DTYPE)
    array.setflags(write=False)
    return array


def _storage_profile(
    *,
    values: np.ndarray,
    column_indices: np.ndarray,
    row_pointers: np.ndarray,
    reverse_values: np.ndarray,
    reverse_column_indices: np.ndarray,
    reverse_row_pointers: np.ndarray,
) -> dict[str, object]:
    return {
        "layout": "numpy.int32.c_contiguous",
        "dtype": str(values.dtype),
        "valuesBytes": int(values.nbytes),
        "columnIndicesBytes": int(column_indices.nbytes),
        "rowPointersBytes": int(row_pointers.nbytes),
        "reverseValuesBytes": int(reverse_values.nbytes),
        "reverseColumnIndicesBytes": int(reverse_column_indices.nbytes),
        "reverseRowPointersBytes": int(reverse_row_pointers.nbytes),
        "totalBytes": int(
            values.nbytes
            + column_indices.nbytes
            + row_pointers.nbytes
            + reverse_values.nbytes
            + reverse_column_indices.nbytes
            + reverse_row_pointers.nbytes
        ),
        "cContiguous": bool(
            values.flags.c_contiguous
            and column_indices.flags.c_contiguous
            and row_pointers.flags.c_contiguous
            and reverse_values.flags.c_contiguous
            and reverse_column_indices.flags.c_contiguous
            and reverse_row_pointers.flags.c_contiguous
        ),
    }
