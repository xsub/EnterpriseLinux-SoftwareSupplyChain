"""Diff utilities for EDGP JSON graph snapshots."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path
from typing import Any


def diff_snapshot_files(left_path: Path, right_path: Path) -> str:
    left = json.loads(left_path.read_text(encoding="utf-8"))
    right = json.loads(right_path.read_text(encoding="utf-8"))
    return json.dumps(diff_snapshots(left, right), indent=2, sort_keys=True)


def diff_tree_snapshot_files(
    left_path: Path,
    right_path: Path,
    *,
    selector: str | None = None,
    left_selector: str | None = None,
    right_selector: str | None = None,
    direction: str = "dependencies",
    depth: int = 3,
) -> str:
    left = json.loads(left_path.read_text(encoding="utf-8"))
    right = json.loads(right_path.read_text(encoding="utf-8"))
    return json.dumps(
        diff_tree_snapshots(
            left,
            right,
            selector=selector,
            left_selector=left_selector,
            right_selector=right_selector,
            direction=direction,
            depth=depth,
        ),
        indent=2,
        sort_keys=True,
    )


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


def diff_tree_snapshots(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    selector: str | None = None,
    left_selector: str | None = None,
    right_selector: str | None = None,
    direction: str = "dependencies",
    depth: int = 3,
) -> dict[str, Any]:
    _require_snapshot(left, label="left")
    _require_snapshot(right, label="right")
    if direction not in {"dependencies", "dependents"}:
        raise ValueError("diff tree direction must be dependencies or dependents")
    if depth < 0:
        raise ValueError("diff tree depth must be non-negative")

    left_index = _SnapshotIndex.from_snapshot(left, label="left")
    right_index = _SnapshotIndex.from_snapshot(right, label="right")
    selectors = _resolve_diff_tree_selectors(
        selector=selector,
        left_selector=left_selector,
        right_selector=right_selector,
    )
    left_node = left_index.resolve_selector(selectors["left"])
    right_node = right_index.resolve_selector(selectors["right"])
    if left_node is None and right_node is None:
        raise ValueError(
            "diff tree selector does not match either snapshot: "
            f"left={selectors['left']} right={selectors['right']}"
        )

    left_view = _collect_neighborhood(left_index, left_node, direction=direction, depth=depth)
    right_view = _collect_neighborhood(
        right_index,
        right_node,
        direction=direction,
        depth=depth,
    )

    added_nodes = sorted(right_view.nodes - left_view.nodes)
    removed_nodes = sorted(left_view.nodes - right_view.nodes)
    common_nodes = sorted(left_view.nodes & right_view.nodes)
    metadata_changed = [
        _metadata_change(
            left_index,
            right_index,
            node_id,
            left_view=left_view,
            right_view=right_view,
        )
        for node_id in common_nodes
        if left_index.metadata(node_id) != right_index.metadata(node_id)
    ]
    changed_node_ids = {item["id"] for item in metadata_changed}
    unchanged_nodes = [node_id for node_id in common_nodes if node_id not in changed_node_ids]
    added_edges = sorted(right_view.edges - left_view.edges)
    removed_edges = sorted(left_view.edges - right_view.edges)
    unchanged_edges = sorted(left_view.edges & right_view.edges)
    added_payloads = [
        right_index.node_payload(
            node_id,
            distance=right_view.distance(node_id),
            path=right_view.path_to(node_id),
        )
        for node_id in added_nodes
    ]
    removed_payloads = [
        left_index.node_payload(
            node_id,
            distance=left_view.distance(node_id),
            path=left_view.path_to(node_id),
        )
        for node_id in removed_nodes
    ]
    classifications = _classify_diff_tree_changes(
        added_payloads,
        removed_payloads,
        metadata_changed,
    )
    classification_counts = _classification_counts(classifications)

    return {
        "schema": "edgp.graph.diff_tree.v1",
        "selector": selectors["display"],
        "leftSelector": selectors["left"],
        "rightSelector": selectors["right"],
        "direction": direction,
        "depth": depth,
        "leftRoot": left.get("root"),
        "rightRoot": right.get("root"),
        "leftNode": left_node,
        "rightNode": right_node,
        "summary": {
            "leftNodes": len(left_view.nodes),
            "rightNodes": len(right_view.nodes),
            "addedNodes": len(added_nodes),
            "removedNodes": len(removed_nodes),
            "metadataChangedNodes": len(metadata_changed),
            "unchangedNodes": len(unchanged_nodes),
            "addedEdges": len(added_edges),
            "removedEdges": len(removed_edges),
            "unchangedEdges": len(unchanged_edges),
            "classifiedChanges": len(classifications),
            "upgradeChanges": classification_counts.get("upgrade", 0),
            "downgradeChanges": classification_counts.get("downgrade", 0),
            "replacementChanges": classification_counts.get("replacement", 0),
            "addedOnlyChanges": classification_counts.get("added", 0),
            "removedOnlyChanges": classification_counts.get("removed", 0),
            "metadataOnlyChanges": classification_counts.get("metadataChange", 0),
        },
        "nodes": {
            "added": added_payloads,
            "removed": removed_payloads,
            "metadataChanged": metadata_changed,
            "unchanged": unchanged_nodes,
        },
        "classifications": classifications,
        "edges": {
            "added": [_edge_payload(edge) for edge in added_edges],
            "removed": [_edge_payload(edge) for edge in removed_edges],
            "unchanged": [_edge_payload(edge) for edge in unchanged_edges],
        },
        "neighborhoods": {
            "left": {
                "nodes": sorted(left_view.nodes),
                "edges": [_edge_payload(edge) for edge in sorted(left_view.edges)],
            },
            "right": {
                "nodes": sorted(right_view.nodes),
                "edges": [_edge_payload(edge) for edge in sorted(right_view.edges)],
            },
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


def _resolve_diff_tree_selectors(
    *,
    selector: str | None,
    left_selector: str | None,
    right_selector: str | None,
) -> dict[str, str]:
    left_value = _clean_selector(left_selector)
    right_value = _clean_selector(right_selector)
    shared_value = _clean_selector(selector)
    if shared_value:
        if left_value or right_value:
            raise ValueError(
                "use either a shared diff tree selector or explicit left/right selectors"
            )
        return {"display": shared_value, "left": shared_value, "right": shared_value}
    if not left_value and not right_value:
        raise ValueError("diff tree requires --node or --left-node/--right-node")
    if not left_value or not right_value:
        raise ValueError("diff tree explicit selectors require both left and right values")
    return {
        "display": f"{left_value} -> {right_value}",
        "left": left_value,
        "right": right_value,
    }


def _clean_selector(value: str | None) -> str:
    return value.strip() if isinstance(value, str) else ""


def _classify_diff_tree_changes(
    added_nodes: list[dict[str, Any]],
    removed_nodes: list[dict[str, Any]],
    metadata_changed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    added_by_name = _group_nodes_by_name(added_nodes)
    removed_by_name = _group_nodes_by_name(removed_nodes)
    classifications: list[dict[str, Any]] = []
    paired_added: set[str] = set()
    paired_removed: set[str] = set()

    for name in sorted(set(added_by_name) & set(removed_by_name)):
        added_group = added_by_name[name]
        removed_group = removed_by_name[name]
        for index, (removed, added) in enumerate(zip(removed_group, added_group, strict=False)):
            paired_removed.add(str(removed["id"]))
            paired_added.add(str(added["id"]))
            classifications.append(_paired_change(name, removed, added, order=index))

    for node in added_nodes:
        node_id = str(node["id"])
        if node_id not in paired_added:
            classifications.append(_single_node_change("added", "right", node))
    for node in removed_nodes:
        node_id = str(node["id"])
        if node_id not in paired_removed:
            classifications.append(_single_node_change("removed", "left", node))
    for change in metadata_changed:
        classifications.append(_metadata_only_change(change))

    return sorted(
        classifications,
        key=lambda item: (
            str(item.get("kind", "")),
            str(item.get("name", "")),
            str(item.get("leftNode", "")),
            str(item.get("rightNode", "")),
            str(item.get("node", "")),
        ),
    )


def _group_nodes_by_name(nodes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        name = str(node.get("name") or node.get("id") or "")
        if not name:
            continue
        grouped.setdefault(name, []).append(node)
    for group in grouped.values():
        group.sort(key=lambda item: str(item.get("id", "")))
    return grouped


def _paired_change(
    name: str,
    removed: dict[str, Any],
    added: dict[str, Any],
    *,
    order: int,
) -> dict[str, Any]:
    left_version = str(removed.get("version") or "")
    right_version = str(added.get("version") or "")
    return {
        "kind": _version_change_kind(left_version, right_version),
        "name": name,
        "leftNode": str(removed.get("id") or ""),
        "rightNode": str(added.get("id") or ""),
        "leftVersion": left_version,
        "rightVersion": right_version,
        "leftDistance": removed.get("distance"),
        "rightDistance": added.get("distance"),
        "leftPath": removed.get("path", []),
        "rightPath": added.get("path", []),
        "pairIndex": order,
    }


def _single_node_change(kind: str, side: str, node: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": kind,
        "name": str(node.get("name") or node.get("id") or ""),
        f"{side}Node": str(node.get("id") or ""),
        f"{side}Version": str(node.get("version") or ""),
        f"{side}Distance": node.get("distance"),
        f"{side}Path": node.get("path", []),
    }


def _metadata_only_change(change: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "metadataChange",
        "name": str(change.get("id") or ""),
        "node": str(change.get("id") or ""),
        "changedKeys": change.get("changedKeys", []),
        "leftDistance": change.get("leftDistance"),
        "rightDistance": change.get("rightDistance"),
        "leftPath": change.get("leftPath", []),
        "rightPath": change.get("rightPath", []),
    }


def _classification_counts(classifications: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in classifications:
        kind = str(item.get("kind") or "")
        counts[kind] = counts.get(kind, 0) + 1
    return counts


def _version_change_kind(left_version: str, right_version: str) -> str:
    comparison = _compare_versions(left_version, right_version)
    if comparison < 0:
        return "upgrade"
    if comparison > 0:
        return "downgrade"
    return "replacement"


def _compare_versions(left_version: str, right_version: str) -> int:
    left_parts = _version_parts(left_version)
    right_parts = _version_parts(right_version)
    for left, right in zip(left_parts, right_parts, strict=False):
        if left == right:
            continue
        if isinstance(left, int) and isinstance(right, int):
            return -1 if left < right else 1
        return -1 if str(left) < str(right) else 1
    if len(left_parts) == len(right_parts):
        return 0
    return -1 if len(left_parts) < len(right_parts) else 1


def _version_parts(version: str) -> list[int | str]:
    parts: list[int | str] = []
    token = ""
    token_is_digit: bool | None = None
    for char in version:
        is_digit = char.isdigit()
        if token and token_is_digit is not None and is_digit != token_is_digit:
            parts.append(int(token) if token_is_digit else token)
            token = ""
        if char.isalnum():
            token += char.lower()
            token_is_digit = is_digit
        elif token:
            parts.append(int(token) if token_is_digit else token)
            token = ""
            token_is_digit = None
    if token:
        parts.append(int(token) if token_is_digit else token)
    return parts


class _SnapshotIndex:
    def __init__(
        self,
        *,
        label: str,
        nodes: dict[str, dict[str, Any]],
        names: dict[str, list[str]],
        outgoing: dict[str, list[tuple[str, str, int]]],
        incoming: dict[str, list[tuple[str, str, int]]],
    ) -> None:
        self.label = label
        self.nodes = nodes
        self.names = names
        self.outgoing = outgoing
        self.incoming = incoming

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any], *, label: str) -> "_SnapshotIndex":
        nodes = {str(node["id"]): node for node in snapshot["nodes"]}
        names: dict[str, list[str]] = {}
        for node_id, node in nodes.items():
            names.setdefault(str(node.get("name") or node_id), []).append(node_id)
        outgoing: dict[str, list[tuple[str, str, int]]] = {node_id: [] for node_id in nodes}
        incoming: dict[str, list[tuple[str, str, int]]] = {node_id: [] for node_id in nodes}
        for edge in snapshot["edges"]:
            key = _edge_key(edge)
            outgoing.setdefault(key[0], []).append(key)
            incoming.setdefault(key[1], []).append(key)
        return cls(
            label=label,
            nodes=nodes,
            names=names,
            outgoing=outgoing,
            incoming=incoming,
        )

    def resolve_selector(self, selector: str) -> str | None:
        if selector in self.nodes:
            return selector
        matches = sorted(self.names.get(selector, []))
        if not matches:
            return None
        if len(matches) > 1:
            joined = ", ".join(matches[:5])
            suffix = "" if len(matches) <= 5 else ", ..."
            raise ValueError(
                f"{self.label} diff tree selector is ambiguous: {selector} "
                f"matches {joined}{suffix}"
            )
        return matches[0]

    def metadata(self, node_id: str) -> dict[str, Any]:
        metadata = self.nodes.get(node_id, {}).get("metadata", {})
        return dict(metadata) if isinstance(metadata, dict) else {}

    def node_payload(
        self,
        node_id: str,
        *,
        distance: int | None = None,
        path: list[str] | None = None,
    ) -> dict[str, Any]:
        node = self.nodes[node_id]
        payload: dict[str, Any] = {
            "id": node_id,
            "name": str(node.get("name") or node_id),
            "version": str(node.get("version") or ""),
            "metadata": self.metadata(node_id),
        }
        if distance is not None:
            payload["distance"] = distance
        if path:
            payload["path"] = path
        return payload


class _Neighborhood:
    def __init__(
        self,
        nodes: set[str],
        edges: set[tuple[str, str, int]],
        *,
        start: str | None,
        distances: dict[str, int] | None = None,
        parents: dict[str, str | None] | None = None,
    ) -> None:
        self.nodes = nodes
        self.edges = edges
        self.start = start
        self.distances = distances or {}
        self.parents = parents or {}

    def distance(self, node_id: str) -> int | None:
        return self.distances.get(node_id)

    def path_to(self, node_id: str) -> list[str]:
        if node_id not in self.nodes:
            return []
        path = [node_id]
        current = node_id
        seen = {node_id}
        while current != self.start:
            parent = self.parents.get(current)
            if parent is None or parent in seen:
                return []
            path.append(parent)
            seen.add(parent)
            current = parent
        return list(reversed(path))


def _collect_neighborhood(
    index: _SnapshotIndex,
    start: str | None,
    *,
    direction: str,
    depth: int,
) -> _Neighborhood:
    if start is None:
        return _Neighborhood(set(), set(), start=None)
    adjacency = index.outgoing if direction == "dependencies" else index.incoming
    nodes = {start}
    edges: set[tuple[str, str, int]] = set()
    distances = {start: 0}
    parents: dict[str, str | None] = {start: None}
    queue: deque[str] = deque([start])
    while queue:
        node_id = queue.popleft()
        distance = distances[node_id]
        if distance >= depth:
            continue
        for edge in adjacency.get(node_id, []):
            neighbor = edge[1] if direction == "dependencies" else edge[0]
            edges.add(edge)
            if neighbor not in nodes:
                nodes.add(neighbor)
                distances[neighbor] = distance + 1
                parents[neighbor] = node_id
                queue.append(neighbor)
    return _Neighborhood(
        nodes,
        edges,
        start=start,
        distances=distances,
        parents=parents,
    )


def _metadata_change(
    left_index: _SnapshotIndex,
    right_index: _SnapshotIndex,
    node_id: str,
    *,
    left_view: _Neighborhood,
    right_view: _Neighborhood,
) -> dict[str, Any]:
    left_metadata = left_index.metadata(node_id)
    right_metadata = right_index.metadata(node_id)
    keys = sorted(set(left_metadata) | set(right_metadata))
    payload: dict[str, Any] = {
        "id": node_id,
        "changedKeys": [
            key for key in keys if left_metadata.get(key) != right_metadata.get(key)
        ],
        "leftMetadata": left_metadata,
        "rightMetadata": right_metadata,
    }
    left_distance = left_view.distance(node_id)
    right_distance = right_view.distance(node_id)
    if left_distance is not None:
        payload["leftDistance"] = left_distance
        payload["leftPath"] = left_view.path_to(node_id)
    if right_distance is not None:
        payload["rightDistance"] = right_distance
        payload["rightPath"] = right_view.path_to(node_id)
    return payload
