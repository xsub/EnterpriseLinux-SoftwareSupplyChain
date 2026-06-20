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

    assert (
        main(
            [
                "npm-diagnostics",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
                "--format",
                "text",
            ]
        )
        == 0
    )
    text = capsys.readouterr().out.strip()
    assert text.startswith("NPM_DIAGNOSTICS ")
    assert "schema=edgp.npm.diagnostics.v1" in text
    assert "packages=4" in text
    assert "duplicatePackageNames=1" in text
    assert "nestedResolutionConflicts=1" in text
    assert "unresolvedDependencies=1" in text
    assert "firstDuplicatePackage=shared" in text
    assert "firstConflictDependency=shared" in text
    assert "firstUnresolvedDependency=missing" in text


def test_cli_npm_diagnostics_bundle_writes_verifiable_bundle(
    capsys,
    tmp_path,
) -> None:
    output_dir = tmp_path / "npm-diagnostics-bundle"

    assert (
        main(
            [
                "npm-diagnostics-bundle",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "npm-diagnostics"
    assert manifest["reports"][0]["href"] == "001-npm-diagnostics.html"
    assert manifest["reports"][0]["schema"] == "edgp.npm.diagnostics.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"

    report = json.loads(
        (output_dir / "npm-diagnostics.json").read_text(encoding="utf-8")
    )
    assert report["schema"] == "edgp.npm.diagnostics.v1"
    assert report["summary"]["nestedResolutionConflicts"] == 1
    assert report["summary"]["unresolvedDependencies"] == 1
    assert 'data-testid="npm-conflicts-panel"' in (
        output_dir / "001-npm-diagnostics.html"
    ).read_text(encoding="utf-8")

    assert main(["verify-bundle", "--path", str(output_dir), "--format", "text"]) == 0
    assert capsys.readouterr().out.startswith("OK ")


def test_cli_npm_diagnostics_bundle_prints_text_summary(capsys, tmp_path) -> None:
    output_dir = tmp_path / "npm-diagnostics-bundle-text"

    assert (
        main(
            [
                "npm-diagnostics-bundle",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
                "--format",
                "text",
            ]
        )
        == 0
    )

    text = capsys.readouterr().out.strip()
    assert text.startswith("BUNDLE ")
    assert f"index={output_dir / 'index.html'}" in text
    assert "sourceKind=npm-diagnostics" in text
    assert "triageStatus=warn" in text
