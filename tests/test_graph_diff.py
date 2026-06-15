"""Graph snapshot diff tests."""

import json
from pathlib import Path

from src.cli import main
from src.graph_diff import diff_snapshot_files, diff_tree_snapshot_files


def test_diff_snapshot_files_reports_added_and_removed_graph_elements() -> None:
    payload = json.loads(
        diff_snapshot_files(
            Path("tests/fixtures/snapshot-left.json"),
            Path("tests/fixtures/snapshot-right.json"),
        )
    )

    assert payload["schema"] == "edgp.graph.diff.v1"
    assert payload["summary"] == {
        "addedNodes": 2,
        "removedNodes": 1,
        "addedEdges": 2,
        "removedEdges": 1,
        "metadataChangedNodes": 0,
    }
    assert payload["nodes"]["added"] == ["core==1.0.0", "lib==2.0.0"]
    assert payload["nodes"]["removed"] == ["lib==1.0.0"]


def test_diff_tree_snapshot_files_reports_focused_dependency_cone_changes() -> None:
    payload = json.loads(
        diff_tree_snapshot_files(
            Path("tests/fixtures/snapshot-left.json"),
            Path("tests/fixtures/snapshot-right.json"),
            selector="app",
            depth=2,
        )
    )

    assert payload["schema"] == "edgp.graph.diff_tree.v1"
    assert payload["leftNode"] == "app==1.0.0"
    assert payload["rightNode"] == "app==1.0.0"
    assert payload["summary"]["addedNodes"] == 2
    assert payload["summary"]["removedNodes"] == 1
    assert [node["id"] for node in payload["nodes"]["added"]] == [
        "core==1.0.0",
        "lib==2.0.0",
    ]
    assert [node["id"] for node in payload["nodes"]["removed"]] == ["lib==1.0.0"]


def test_cli_diff_bundle_writes_report_bundle(tmp_path, capsys) -> None:
    output_dir = tmp_path / "graph-diff-bundle"

    assert (
        main(
            [
                "diff-bundle",
                "--left",
                "tests/fixtures/snapshot-left.json",
                "--right",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "graph-diff.json").read_text(encoding="utf-8"))
    html = (output_dir / "001-graph-diff.html").read_text(encoding="utf-8")

    assert manifest["bundle"]["sourceKind"] == "graph-diff"
    assert manifest["reports"][0]["schema"] == "edgp.graph.diff.v1"
    assert manifest["reports"][0]["href"] == "001-graph-diff.html"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    assert report["summary"]["addedEdges"] == 2
    assert 'data-testid="graph-diff-added-edges-panel"' in html

    assert main(["verify-bundle", "--path", str(output_dir)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["ok"] is True


def test_cli_diff_tree_bundle_writes_report_bundle(tmp_path, capsys) -> None:
    output_dir = tmp_path / "graph-diff-tree-bundle"

    assert (
        main(
            [
                "diff-tree-bundle",
                "--left",
                "tests/fixtures/snapshot-left.json",
                "--right",
                "tests/fixtures/snapshot-right.json",
                "--node",
                "app",
                "--depth",
                "2",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "graph-diff-tree.json").read_text(encoding="utf-8"))
    html = (output_dir / "001-graph-diff-tree.html").read_text(encoding="utf-8")

    assert manifest["bundle"]["sourceKind"] == "graph-diff-tree"
    assert manifest["reports"][0]["schema"] == "edgp.graph.diff_tree.v1"
    assert manifest["reports"][0]["href"] == "001-graph-diff-tree.html"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    assert report["summary"]["addedEdges"] == 2
    assert 'data-testid="graph-diff-tree-added-edges-panel"' in html

    assert main(["verify-bundle", "--path", str(output_dir)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["ok"] is True
