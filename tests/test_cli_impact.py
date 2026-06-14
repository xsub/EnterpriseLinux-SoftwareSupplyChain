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


def test_cli_impact_bundle_writes_verifiable_report_bundle(
    capsys,
    tmp_path,
) -> None:
    output_dir = tmp_path / "impact-bundle"

    assert (
        main(
            [
                "impact-bundle",
                "--path",
                "tests/fixtures/package-lock.json",
                "--node",
                "left-pad",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "impact-report"
    assert manifest["reports"][0]["href"] == "001-impact-report.html"
    assert manifest["reports"][0]["schema"] == "edgp.impact.report.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"

    report = json.loads((output_dir / "impact-report.json").read_text(encoding="utf-8"))
    assert report["schema"] == "edgp.impact.report.v1"
    assert report["node"] == "left-pad==1.3.0"
    assert report["summary"]["affectedDependents"] == 2
    assert 'data-testid="impact-chains-panel"' in (
        output_dir / "001-impact-report.html"
    ).read_text(encoding="utf-8")

    assert main(["verify-bundle", "--path", str(output_dir), "--format", "text"]) == 0
    assert capsys.readouterr().out.startswith("OK ")
