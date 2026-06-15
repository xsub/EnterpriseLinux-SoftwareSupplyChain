"""Persist and load memory-mappable frozen CSR graph artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from src.core_graph.sparse_matrix import FrozenCSRGraph

CSR_ARTIFACT_SCHEMA = "edgp.csr.artifact.v1"
CSR_ARTIFACT_LAYOUT = "frozen_csr_numpy_npy_directory"

_ARRAY_NAMES = (
    "values",
    "column_indices",
    "row_pointers",
    "reverse_values",
    "reverse_column_indices",
    "reverse_row_pointers",
)


def write_frozen_csr_artifact(
    graph: FrozenCSRGraph, output_dir: str | Path
) -> dict[str, Any]:
    """Write a frozen CSR graph as `.npy` arrays plus a verified manifest."""

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    arrays: dict[str, dict[str, object]] = {}
    for name in _ARRAY_NAMES:
        path = destination / f"{name}.npy"
        array = getattr(graph, name)
        np.save(path, array, allow_pickle=False)
        arrays[name] = {
            "path": path.name,
            "dtype": str(array.dtype),
            "shape": list(array.shape),
            "sha256": _sha256(path),
        }

    manifest: dict[str, Any] = {
        "schema": CSR_ARTIFACT_SCHEMA,
        "layout": CSR_ARTIFACT_LAYOUT,
        "layoutVersion": 1,
        "dtype": "int32",
        "nodes": len(graph),
        "edges": int(len(graph.column_indices)),
        "arrays": arrays,
        "packageIds": list(graph.package_ids),
        "vertexMetadata": {
            package_id: dict(metadata)
            for package_id, metadata in graph.vertex_metadata.items()
        },
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_frozen_csr_artifact(
    input_dir: str | Path, *, mmap_mode: str | None = "r"
) -> FrozenCSRGraph:
    """Load and verify a frozen CSR graph artifact directory."""

    source = Path(input_dir)
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != CSR_ARTIFACT_SCHEMA:
        raise ValueError("CSR artifact manifest has an unsupported schema")
    if manifest.get("layout") != CSR_ARTIFACT_LAYOUT:
        raise ValueError("CSR artifact manifest has an unsupported layout")

    arrays = {
        name: _load_manifest_array(source, manifest, name, mmap_mode=mmap_mode)
        for name in _ARRAY_NAMES
    }
    package_ids = tuple(str(package_id) for package_id in manifest["packageIds"])
    vertex_map = {package_id: index for index, package_id in enumerate(package_ids)}
    vertex_metadata = {
        str(package_id): {
            str(key): str(value)
            for key, value in dict(metadata).items()
        }
        for package_id, metadata in manifest.get("vertexMetadata", {}).items()
    }
    return FrozenCSRGraph(
        vertex_map=vertex_map,
        package_ids=package_ids,
        vertex_metadata=vertex_metadata,
        copy_arrays=False,
        **arrays,
    )


def _load_manifest_array(
    source: Path,
    manifest: dict[str, Any],
    name: str,
    *,
    mmap_mode: str | None,
) -> np.ndarray:
    try:
        descriptor = manifest["arrays"][name]
    except KeyError as exc:
        raise ValueError(f"CSR artifact manifest is missing array {name}") from exc
    path = source / str(descriptor["path"])
    expected_digest = str(descriptor["sha256"])
    if _sha256(path) != expected_digest:
        raise ValueError(f"CSR artifact array digest mismatch: {name}")
    array = np.load(path, mmap_mode=mmap_mode, allow_pickle=False)
    if str(array.dtype) != str(descriptor["dtype"]):
        raise ValueError(f"CSR artifact array dtype mismatch: {name}")
    if list(array.shape) != list(descriptor["shape"]):
        raise ValueError(f"CSR artifact array shape mismatch: {name}")
    return array


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
