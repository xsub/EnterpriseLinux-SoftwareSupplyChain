"""CLI tests for optional accelerator availability reports."""

import json

from src.cli import main


def test_cli_accelerator_status_reports_numba_and_graphblas(capsys) -> None:
    assert main(["accelerator-status", "--backend", "auto"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["requestedBackend"] == "auto"
    assert payload["selectedBackend"] in {"python", "numba"}
    assert payload["numba"]["installExtra"] == ".[fast]"
    assert payload["graphblas"]["installExtra"] == ".[graphblas]"
    assert payload["graphblas"]["storageContract"] == "frozen CSR remains canonical"
