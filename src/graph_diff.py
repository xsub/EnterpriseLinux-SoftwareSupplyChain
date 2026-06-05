"""Diff utilities for EDGP JSON graph snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def diff_snapshot_files(left_path: Path, right_path: Path) -> str:
    left = json.loads(left_path.read_text(encoding="utf-8"))
    right = json.loads(right_path.read_text(encoding="utf-8"))
    return json.dumps(diff_snapshots(left, right), indent=2, sort_keys=True)


def diff_snapshots(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    _require_snapshot(left, label="left")
    _require_snapshot(right, label="right")

    left_nodes = {node["id"]: node for node in left["nodes"]}
    right_nodes = {node["id"]: node for node in right["nodes"]}
    left_edges = {_edge_key(edge) for edge in left["edges"]}
    right_edges = {_edge_key(edge) for edge in right["edges"]}

    added_nodes = sorted(set(right_nodes) - set(left_nodes))
    removed_nodes = sorted(set(left_nodes) - set(right_nodes))
    common_nodes = sorted(set(left_nodes) & set(right_nodes))
    metadata_changed = [
        node_id
        for node_id in common_nodes
        if left_nodes[node_id].get("metadata", {}) != right_nodes[node_id].get("metadata", {})
    ]

    return {
        "schema": "edgp.graph.diff.v1",
        "leftRoot": left.get("root"),
        "rightRoot": right.get("root"),
        "summary": {
            "addedNodes": len(added_nodes),
            "removedNodes": len(removed_nodes),
            "addedEdges": len(right_edges - left_edges),
            "removedEdges": len(left_edges - right_edges),
            "metadataChangedNodes": len(metadata_changed),
        },
        "nodes": {
            "added": added_nodes,
            "removed": removed_nodes,
            "metadataChanged": metadata_changed,
        },
        "edges": {
            "added": [_edge_payload(edge) for edge in sorted(right_edges - left_edges)],
            "removed": [_edge_payload(edge) for edge in sorted(left_edges - right_edges)],
        },
    }


def _require_snapshot(payload: dict[str, Any], *, label: str) -> None:
    if payload.get("schema") != "edgp.graph.snapshot.v1":
        raise ValueError(f"{label} is not an EDGP graph snapshot")
    if not isinstance(payload.get("nodes"), list) or not isinstance(payload.get("edges"), list):
        raise ValueError(f"{label} snapshot is missing nodes or edges")


def _edge_key(edge: dict[str, Any]) -> tuple[str, str, int]:
    return (
        str(edge["source"]),
        str(edge["target"]),
        int(edge.get("relationshipType", 1)),
    )


def _edge_payload(edge: tuple[str, str, int]) -> dict[str, Any]:
    source, target, relationship_type = edge
    return {
        "source": source,
        "target": target,
        "relationshipType": relationship_type,
    }
