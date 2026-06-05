"""CLI advisory overlay tests for local vulnerability context."""

import json

from src.cli import main


def test_cli_advisory_overlays_local_advisories_on_lockfile(capsys) -> None:
    assert (
        main(
            [
                "advisory",
                "--path",
                "tests/fixtures/package-lock.json",
                "--advisories",
                "tests/fixtures/advisories.json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.advisory.report.v1"
    assert payload["ecosystem"] == "npm"
    assert payload["summary"]["findings"] == 1
    assert payload["findings"][0]["package"] == "left-pad==1.3.0"
    assert payload["findings"][0]["impact"]["directDependents"] == [
        "@scope/tool==2.1.0",
        "demo-app==1.0.0",
    ]
