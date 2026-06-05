"""CLI tests for synthetic CSR graph benchmarks."""

import json

from src.cli import main


def test_cli_benchmark_outputs_json(capsys) -> None:
    assert main(["benchmark", "--nodes", "6", "--fanout", "2"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.benchmark.v1"
    assert payload["stats"]["nodes"] == 6
    assert payload["stats"]["edges"] == 9
