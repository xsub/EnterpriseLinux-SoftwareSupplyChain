"""CLI impact report tests for reverse dependency investigations."""

import json

from src.cli import main


def test_cli_impact_reports_affected_lockfile_dependents(capsys) -> None:
    assert (
        main(
            [
                "impact",
                "--path",
                "tests/fixtures/package-lock.json",
                "--node",
                "left-pad",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.impact.report.v1"
    assert payload["ecosystem"] == "npm"
    assert payload["node"] == "left-pad==1.3.0"
    assert payload["summary"] == {
        "directDependents": 2,
        "affectedDependents": 2,
        "directDependencies": 0,
        "renderedChains": 2,
        "truncatedChains": 0,
    }
    assert payload["directDependents"] == ["@scope/tool==2.1.0", "demo-app==1.0.0"]
    assert payload["dependencyChainsToNode"] == [
        {
            "distance": 1,
            "package": "@scope/tool==2.1.0",
            "path": ["@scope/tool==2.1.0", "left-pad==1.3.0"],
        },
        {
            "distance": 1,
            "package": "demo-app==1.0.0",
            "path": ["demo-app==1.0.0", "left-pad==1.3.0"],
        },
    ]
