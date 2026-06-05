"""CLI tests for npm package-lock dependency path diagnostics."""

import json

from src.cli import main


def test_cli_npm_diagnostics_reports_conflicts(capsys) -> None:
    assert (
        main(
            [
                "npm-diagnostics",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.npm.diagnostics.v1"
    assert payload["root"] == "conflict-app==1.0.0"
    assert payload["summary"]["nestedResolutionConflicts"] == 1
    assert payload["summary"]["unresolvedDependencies"] == 1
