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
    assert loaded.reachable_dependencies("app==1.0.0") == [
        "lib==2.0.0",
        "core==1.0.0",
    ]
    assert loaded.storage_profile()["memoryMapped"] is True
