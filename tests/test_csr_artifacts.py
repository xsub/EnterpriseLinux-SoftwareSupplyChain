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
    assert manifest["storageProfile"]["runtime"] == "frozen"
    assert manifest["storageProfile"]["dtype"] == "int32"
    assert manifest["storageProfile"]["cContiguous"] is True
    assert manifest["storageProfile"]["readOnly"] is True
    assert manifest["storageProfile"]["memoryMappable"] is True
    assert manifest["storageProfile"]["mmapMode"] == "r"
    assert manifest["storageProfile"]["arrayCount"] == 6
    assert manifest["storageProfile"]["digestAlgorithm"] == "sha256"
    assert manifest["storageProfile"]["digestCoverage"] == [
        "values",
        "column_indices",
        "row_pointers",
        "reverse_values",
        "reverse_column_indices",
        "reverse_row_pointers",
    ]
    assert manifest["storageProfile"]["forwardBytes"] == 32
    assert manifest["storageProfile"]["reverseBytes"] == 32
    assert manifest["storageProfile"]["totalBytes"] == 64
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


def test_frozen_csr_artifact_rejects_tampered_storage_profile_bytes(
    tmp_path,
) -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    write_frozen_csr_artifact(graph.freeze(), tmp_path)

    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["storageProfile"]["totalBytes"] += 4
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="storageProfile mismatch: totalBytes"):
        load_frozen_csr_artifact(tmp_path)


def test_frozen_csr_artifact_accepts_reordered_storage_profile_digest_coverage(
    tmp_path,
) -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    write_frozen_csr_artifact(graph.freeze(), tmp_path)

    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["storageProfile"]["digestCoverage"] = list(
        reversed(manifest["storageProfile"]["digestCoverage"])
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    loaded = load_frozen_csr_artifact(tmp_path)

    assert loaded.reachable_dependencies("app==1.0.0") == ["lib==1.0.0"]


def test_frozen_csr_artifact_rejects_tampered_storage_profile_digest_coverage(
    tmp_path,
) -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")
    write_frozen_csr_artifact(graph.freeze(), tmp_path)

    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["storageProfile"]["digestCoverage"] = ["values"]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="digest coverage mismatch"):
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
