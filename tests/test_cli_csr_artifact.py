"""CLI tests for memory-mappable CSR artifact export."""

import json

from src.cli import main
from src.core_graph.artifacts import load_frozen_csr_artifact


def test_cli_csr_artifact_writes_verified_runtime_artifact(tmp_path, capsys) -> None:
    output_dir = tmp_path / "csr-artifact"

    assert (
        main(
            [
                "csr-artifact",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    manifest = json.loads(capsys.readouterr().out)
    loaded = load_frozen_csr_artifact(output_dir)

    assert manifest["schema"] == "edgp.csr.artifact.v1"
    assert manifest["nodes"] == 3
    assert manifest["edges"] == 2
    assert manifest["matrixViews"]["csr"]["direction"] == "outgoing_dependencies"
    assert manifest["matrixViews"]["csr"]["indices"] == "column_indices"
    assert manifest["matrixViews"]["csc"]["direction"] == "incoming_dependents"
    assert manifest["matrixViews"]["csc"]["indices"] == "reverse_column_indices"
    assert manifest["matrixViews"]["csc"]["materialization"] == (
        "reverse_csr_transpose"
    )
    assert manifest["storageProfile"]["layout"] == "numpy.int32.c_contiguous"
    assert manifest["storageProfile"]["memoryMappable"] is True
    assert manifest["storageProfile"]["digestCoverage"] == [
        "values",
        "column_indices",
        "row_pointers",
        "reverse_values",
        "reverse_column_indices",
        "reverse_row_pointers",
    ]
    assert loaded.reachable_dependencies("app==1.0.0") == [
        "lib==2.0.0",
        "core==1.0.0",
    ]
    assert loaded.storage_profile()["memoryMapped"] is True

    assert main(["validate", "--path", str(output_dir), "--format", "text"]) == 0
    assert capsys.readouterr().out.strip() == (
        "OK targetType=csr-artifact failures=0 contract=edgp.csr.artifact.v1"
    )


def test_cli_csr_artifact_outputs_text_summary(tmp_path, capsys) -> None:
    output_dir = tmp_path / "csr-artifact-text"

    assert (
        main(
            [
                "csr-artifact",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(output_dir),
                "--format",
                "text",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out.strip()
    assert output.startswith("OK schema=edgp.csr.artifact.v1 ")
    assert "nodes=3" in output
    assert "edges=2" in output
    assert "dtype=int32" in output
    assert "arrays=6" in output
    assert "memoryMappable=true" in output
    assert f"outputDir={output_dir}" in output
    assert (output_dir / "manifest.json").exists()
