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


def test_cli_accelerator_status_outputs_text_summary(capsys) -> None:
    assert main(["accelerator-status", "--backend", "auto", "--format", "text"]) == 0

    output = capsys.readouterr().out.strip()
    assert output.startswith("OK command=accelerator-status ")
    assert "requestedBackend=auto" in output
    assert "selectedBackend=" in output
    assert "numbaAvailable=" in output
    assert "graphblasAvailable=" in output
    assert "graphblasStorageContract='frozen CSR remains canonical'" in output
