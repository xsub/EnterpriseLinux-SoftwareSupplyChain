"""Optional accelerated kernels for frozen CSR graph traversal."""

from __future__ import annotations

from functools import lru_cache
from importlib.util import find_spec
from typing import Callable

import numpy as np

_BACKENDS = {"python", "numba", "auto"}


def select_traversal_backend(requested: str = "python") -> str:
    """Resolve a requested traversal backend into an executable backend name."""

    if requested not in _BACKENDS:
        raise ValueError("backend must be one of: auto, numba, python")
    if requested == "python":
        return "python"
    if requested == "auto":
        return "numba" if numba_available() else "python"
    if not numba_available():
        raise RuntimeError(
            "Numba traversal backend is not available; install the fast extra."
        )
    return "numba"


def accelerator_profile(
    *, requested_backend: str = "python", selected_backend: str | None = None
) -> dict[str, object]:
    """Return optional accelerator availability for benchmark evidence."""

    selected = selected_backend or select_traversal_backend(requested_backend)
    return {
        "requestedBackend": requested_backend,
        "selectedBackend": selected,
        "numba": {
            "available": numba_available(),
            "installExtra": ".[fast]",
            "kernels": ["reachable_ids"],
        },
        "graphblas": graphblas_profile(),
    }


def numba_available() -> bool:
    if find_spec("numba") is None:
        return False
    try:
        import numba  # noqa: F401
    except Exception:
        return False
    return True


def graphblas_available() -> bool:
    if find_spec("graphblas") is None:
        return False
    try:
        import graphblas  # noqa: F401
    except Exception:
        return False
    return True


def graphblas_profile() -> dict[str, object]:
    return {
        "available": graphblas_available(),
        "installExtra": ".[graphblas]",
        "package": "python-graphblas",
        "storageContract": "frozen CSR remains canonical",
        "candidateKernels": [
            "multi_source_reachability",
            "batch_impact_queries",
            "sparse_boolean_frontier_expansion",
        ],
    }


def maybe_numba_reachable_ids(
    *,
    row_pointers: np.ndarray,
    column_indices: np.ndarray,
    start_vertex: int,
    vertex_count: int,
    backend: str,
) -> np.ndarray | None:
    """Run a Numba reachability kernel when selected, otherwise return None."""

    if backend == "python":
        return None
    if backend != "numba":
        raise ValueError("resolved backend must be python or numba")
    kernel = _numba_reachable_ids_kernel()
    return kernel(row_pointers, column_indices, int(start_vertex), int(vertex_count))


@lru_cache(maxsize=1)
def _numba_reachable_ids_kernel() -> Callable[..., np.ndarray]:
    from numba import njit

    @njit
    def reachable_ids_kernel(
        row_pointers: np.ndarray,
        column_indices: np.ndarray,
        start_vertex: int,
        vertex_count: int,
    ) -> np.ndarray:
        seen = np.zeros(vertex_count, dtype=np.uint8)
        queue = np.empty(vertex_count, dtype=np.int32)
        output = np.empty(vertex_count, dtype=np.int32)
        head = 0
        tail = 0
        output_count = 0
        seen[start_vertex] = 1

        start = row_pointers[start_vertex]
        end = row_pointers[start_vertex + 1]
        for index in range(start, end):
            neighbor = column_indices[index]
            if seen[neighbor] == 0:
                seen[neighbor] = 1
                queue[tail] = neighbor
                tail += 1

        while head < tail:
            current = queue[head]
            head += 1
            output[output_count] = current
            output_count += 1

            start = row_pointers[current]
            end = row_pointers[current + 1]
            for index in range(start, end):
                neighbor = column_indices[index]
                if seen[neighbor] == 0:
                    seen[neighbor] = 1
                    queue[tail] = neighbor
                    tail += 1

        return output[:output_count].copy()

    return reachable_ids_kernel
