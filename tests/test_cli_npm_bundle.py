"""CLI tests for npm graph and diagnostics report bundles."""

import json
from pathlib import Path

from src.cli import main


def test_cli_npm_bundle_writes_json_html_index_and_manifest(tmp_path, capsys) -> None:
    output_dir = tmp_path / "npm-bundle"

    assert (
        main(
            [
                "npm-bundle",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    index_path = output_dir / "index.html"
    assert Path(capsys.readouterr().out.strip()) == index_path
    graph = json.loads((output_dir / "npm-graph.json").read_text(encoding="utf-8"))
    diagnostics = json.loads(
        (output_dir / "npm-diagnostics.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert graph["schema"] == "edgp.graph.snapshot.v1"
    assert diagnostics["schema"] == "edgp.npm.diagnostics.v1"
    assert manifest["schema"] == "edgp.report.bundle.v1"
    assert manifest["bundle"]["sourceKind"] == "npm-lockfile"
    assert manifest["bundle"]["command"].startswith("edgp npm-bundle ")
    assert manifest["triageSummary"]["href"] == "triage-summary.html"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.npm.diagnostics.v1",
    ]
    assert [report["source"] for report in manifest["reports"]] == [
        "npm-graph.json",
        "npm-diagnostics.json",
    ]
    assert (output_dir / "001-npm-graph.html").exists()
    diagnostics_html = (output_dir / "002-npm-diagnostics.html").read_text(
        encoding="utf-8"
    )
    assert 'data-testid="npm-conflicts-panel"' in diagnostics_html
    triage = json.loads(
        (output_dir / "triage-summary.json").read_text(encoding="utf-8")
    )
    assert triage["schema"] == "edgp.triage.summary.v1"
    assert triage["status"] == "warn"
    assert triage["summary"]["reports"] == 2


def test_cli_npm_bundle_can_fail_on_triage_status(tmp_path, capsys) -> None:
    output_dir = tmp_path / "npm-bundle"

    assert (
        main(
            [
                "npm-bundle",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
                "--output-dir",
                str(output_dir),
                "--fail-on-status",
                "warn",
            ]
        )
        == 2
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    triage = json.loads(
        (output_dir / "triage-summary.json").read_text(encoding="utf-8")
    )
    assert triage["schema"] == "edgp.triage.summary.v1"
    assert triage["status"] == "warn"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["triageSummary"]["href"] == "triage-summary.html"


def test_cli_npm_bundle_can_include_impact_and_advisory_reports(
    tmp_path, capsys
) -> None:
    output_dir = tmp_path / "npm-bundle"

    assert (
        main(
            [
                "npm-bundle",
                "--path",
                "tests/fixtures/package-lock.json",
                "--impact-node",
                "left-pad",
                "--advisories",
                "tests/fixtures/advisories.json",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    impact = json.loads(
        (output_dir / "impact-left-pad-1.3.0.json").read_text(encoding="utf-8")
    )
    advisory = json.loads(
        (output_dir / "advisory-report.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert impact["schema"] == "edgp.impact.report.v1"
    assert impact["node"] == "left-pad==1.3.0"
    assert advisory["schema"] == "edgp.advisory.report.v1"
    assert advisory["summary"]["findings"] == 1
    assert manifest["bundle"]["sourceKind"] == "npm-lockfile"
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.npm.diagnostics.v1",
        "edgp.impact.report.v1",
        "edgp.advisory.report.v1",
    ]
    assert (output_dir / "003-impact-left-pad-1.3.0.html").exists()


def test_cli_npm_bundle_can_include_license_inventory(tmp_path, capsys) -> None:
    output_dir = tmp_path / "npm-bundle"

    assert (
        main(
            [
                "npm-bundle",
                "--path",
                "tests/fixtures/package-lock.json",
                "--license-report",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    license_report = json.loads(
        (output_dir / "license-report.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert license_report["schema"] == "edgp.license.report.v1"
    assert license_report["summary"]["licensedPackages"] == 2
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.npm.diagnostics.v1",
        "edgp.license.report.v1",
    ]
    assert (output_dir / "003-license-report.html").exists()


def test_cli_ingest_npm_lock_outputs_normalized_graph_json(capsys) -> None:
    assert (
        main(
            [
                "ingest",
                "npm-lock",
                "tests/fixtures/npm/simple-package-lock.json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["root"] == "simple-app==1.0.0"
    assert payload["nodes"][0]["metadata"]["ecosystem"] == "npm"
    assert any(node.get("purl") == "pkg:npm/left-pad@1.3.0" for node in payload["nodes"])


def test_cli_ingest_npm_lock_accepts_yarn_and_pnpm(capsys) -> None:
    assert main(["ingest", "npm-lock", "tests/fixtures/npm/yarn.lock"]) == 0
    yarn = json.loads(capsys.readouterr().out)
    assert yarn["root"] == "yarn-lock==resolved"
    assert any(node.get("purl") == "pkg:npm/%40acme/tool@2.1.0" for node in yarn["nodes"])

    assert main(["ingest", "npm-lock", "tests/fixtures/npm/pnpm-lock.yaml"]) == 0
    pnpm = json.loads(capsys.readouterr().out)
    assert pnpm["root"] == "pnpm-lock==resolved"
    edge = next(
        edge
        for edge in pnpm["edges"]
        if edge["source"] == "pnpm-lock==resolved"
        and edge["target"] == "test-runner==3.0.0"
    )
    assert edge["scope"] == "dev"


def test_cli_ingest_package_json_flags_lifecycle_scripts(capsys) -> None:
    assert (
        main(
            [
                "ingest",
                "package-json",
                "tests/fixtures/npm/package.json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    root = next(node for node in payload["nodes"] if node["id"] == "scripted-app==1.0.0")
    assert root["metadata"]["has_install_script"] == "True"
    assert root["metadata"]["install_scripts"] == "postinstall,preinstall"


def test_cli_report_npm_summary_outputs_security_sections(capsys) -> None:
    assert (
        main(
            [
                "report",
                "npm-summary",
                "--path",
                "tests/fixtures/npm/missing-integrity-package-lock.json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.npm.summary.v1"
    assert payload["summary"]["packagesWithoutIntegrity"] == 1
    assert payload["packagesWithoutIntegrity"][0]["id"] == "no-integrity==1.0.0"


def test_cli_report_dependency_path_accepts_purl_selector(capsys) -> None:
    assert (
        main(
            [
                "report",
                "dependency-path",
                "--path",
                "tests/fixtures/npm/small-real-world-style-package-lock.json",
                "--package",
                "pkg:npm/is-number@6.0.0",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["package"] == "is-number==6.0.0"
    assert payload["path"] == [
        "real-world-style-app==1.0.0",
        "is-odd==3.0.1",
        "is-number==6.0.0",
    ]


def test_cli_report_vulnerable_surface_for_npm(capsys) -> None:
    assert (
        main(
            [
                "report",
                "vulnerable-surface",
                "--ecosystem",
                "npm",
                "--path",
                "tests/fixtures/npm/missing-integrity-package-lock.json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.vulnerable_surface.v1"
    assert any(finding["type"] == "packagesWithoutIntegrity" for finding in payload["findings"])


def test_cli_export_cyclonedx_and_graph_json(capsys) -> None:
    assert (
        main(
            [
                "export",
                "cyclonedx",
                "--path",
                "tests/fixtures/npm/simple-package-lock.json",
            ]
        )
        == 0
    )
    cyclonedx = json.loads(capsys.readouterr().out)
    assert cyclonedx["bomFormat"] == "CycloneDX"
    assert any(
        component.get("purl") == "pkg:npm/left-pad@1.3.0"
        for component in cyclonedx["components"]
    )

    assert (
        main(
            [
                "export",
                "graph-json",
                "--path",
                "tests/fixtures/npm/simple-package-lock.json",
            ]
        )
        == 0
    )
    graph = json.loads(capsys.readouterr().out)
    assert graph["schema"] == "edgp.graph.snapshot.v1"
