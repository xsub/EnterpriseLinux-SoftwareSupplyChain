"""Graph snapshot diff tests."""

import json
from pathlib import Path

from src.graph_diff import diff_snapshot_files


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
