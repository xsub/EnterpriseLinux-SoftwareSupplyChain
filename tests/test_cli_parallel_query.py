"""CLI tests for parallel frozen-CSR reachability queries."""

import json

from src.cli import main


def test_cli_parallel_query_runs_multiple_reachability_queries(capsys) -> None:
    assert (
        main(
            [
                "parallel-query",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--query",
                "dependencies:app==1.0.0",
                "--query",
                "dependents:core==1.0.0",
                "--workers",
                "2",
                "--backend",
                "auto",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.parallel.query.report.v1"
    assert payload["summary"]["queries"] == 2
    assert payload["summary"]["workers"] == 2
    assert payload["summary"]["backend"] == "auto"
    assert payload["summary"]["inputType"] == "snapshot"
    assert payload["summary"]["memoryMapped"] is False
    assert payload["results"][0]["nodes"] == ["lib==2.0.0", "core==1.0.0"]
    assert payload["results"][1]["nodes"] == ["lib==2.0.0", "app==1.0.0"]


def test_cli_parallel_query_outputs_text_summary(capsys) -> None:
    assert (
        main(
            [
                "parallel-query",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--query",
                "dependencies:app==1.0.0",
                "--query",
                "dependents:core==1.0.0",
                "--workers",
                "2",
                "--backend",
                "auto",
                "--format",
                "text",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out.strip()
    assert output.startswith("OK schema=edgp.parallel.query.report.v1 ")
    assert "inputType=snapshot" in output
    assert "memoryMapped=false" in output
    assert "queries=2" in output
    assert "workers=2" in output
    assert "backend=auto" in output
    assert "selectedBackend=" in output
    assert "totalResultNodes=4" in output
    assert "firstQuery=dependencies" in output
    assert "firstNode=app==1.0.0" in output


def test_cli_parallel_query_reads_memory_mapped_csr_artifact(tmp_path, capsys) -> None:
    artifact_dir = tmp_path / "csr-artifact"

    assert (
        main(
            [
                "csr-artifact",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(artifact_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "parallel-query",
                "--csr-artifact",
                str(artifact_dir),
                "--query",
                "dependencies:app==1.0.0",
                "--query",
                "dependents:core==1.0.0",
                "--workers",
                "2",
                "--backend",
                "auto",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["inputType"] == "csr-artifact"
    assert payload["summary"]["memoryMapped"] is True
    assert payload["results"][0]["nodes"] == ["lib==2.0.0", "core==1.0.0"]
    assert payload["results"][1]["nodes"] == ["lib==2.0.0", "app==1.0.0"]

    assert (
        main(
            [
                "parallel-query",
                "--csr-artifact",
                str(artifact_dir),
                "--query",
                "dependencies:app==1.0.0",
                "--workers",
                "1",
                "--format",
                "text",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out.strip()
    assert "inputType=csr-artifact" in output
    assert "memoryMapped=true" in output
    assert "totalResultNodes=2" in output
