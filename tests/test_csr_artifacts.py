"""Frozen CSR artifact tests for memory-mapped graph loading."""

import json

import numpy as np
import pytest

from src.core_graph.artifacts import (
    CSR_ARTIFACT_SCHEMA,
    load_frozen_csr_artifact,
    write_frozen_csr_artifact,
)
from src.core_graph.sparse_matrix import CSRDependencyGraph


def test_frozen_csr_artifact_round_trips_with_memmap(tmp_path) -> None:
    graph = CSRDependencyGraph()
    graph.add_vertex("app==1.0.0", metadata={"ecosystem": "test"})
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    graph.add_dependency_edge("lib==1.0.0", "base==1.0.0")

    manifest = write_frozen_csr_artifact(graph.freeze(), tmp_path)
    loaded = load_frozen_csr_artifact(tmp_path)

    assert manifest["schema"] == CSR_ARTIFACT_SCHEMA
    assert manifest["layoutVersion"] == 1
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "column_indices.npy").exists()
    assert isinstance(loaded.column_indices, np.memmap)
    assert loaded.storage_profile()["memoryMapped"] is True
    assert loaded.storage_profile()["readOnly"] is True
    assert loaded.reachable_dependencies("app==1.0.0") == [
        "lib==1.0.0",
        "base==1.0.0",
    ]
    assert loaded.get_vertex_metadata("app==1.0.0") == {"ecosystem": "test"}


def test_frozen_csr_artifact_rejects_tampered_array(tmp_path) -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    write_frozen_csr_artifact(graph.freeze(), tmp_path)

    path = tmp_path / "values.npy"
    payload = bytearray(path.read_bytes())
    payload[-1] = (payload[-1] + 1) % 255
    path.write_bytes(payload)

    with pytest.raises(ValueError, match="digest mismatch"):
        load_frozen_csr_artifact(tmp_path)


def test_frozen_csr_artifact_rejects_wrong_schema(tmp_path) -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    write_frozen_csr_artifact(graph.freeze(), tmp_path)

    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema"] = "wrong"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported schema"):
        load_frozen_csr_artifact(tmp_path)
