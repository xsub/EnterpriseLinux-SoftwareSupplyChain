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
    assert payload["results"][0]["nodes"] == ["lib==2.0.0", "core==1.0.0"]
    assert payload["results"][1]["nodes"] == ["lib==2.0.0", "app==1.0.0"]
