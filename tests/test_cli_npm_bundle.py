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
