"""libsolv command discovery and transaction-output bridge report."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

LIBSOLV_BRIDGE_SCHEMA = "edgp.libsolv.bridge.v1"
LIBSOLV_COMMANDS = ("repo2solv", "rpmmd2solv", "testsolv", "dumpsolv")


def build_libsolv_bridge_report(
    transaction_path: Path | None = None,
    graph_snapshot_path: Path | None = None,
) -> dict[str, Any]:
    """Describe libsolv tooling, transactions, and optional graph matches."""

    commands = [
        {
            "command": command,
            "available": shutil.which(command) is not None,
            "path": shutil.which(command) or "",
        }
        for command in LIBSOLV_COMMANDS
    ]
    transaction_text = (
        transaction_path.read_text(encoding="utf-8") if transaction_path is not None else ""
    )
    actions = _parse_transaction_actions(transaction_text)
    graph_snapshot = (
        _load_graph_snapshot(graph_snapshot_path)
        if graph_snapshot_path is not None
        else None
    )
    if graph_snapshot is not None:
        _attach_graph_matches(actions, graph_snapshot)
    summary = {
        "commandsAvailable": sum(1 for command in commands if command["available"]),
        "transactionActions": len(actions),
        "parsedPackages": _parsed_package_count(actions),
        "installs": sum(1 for action in actions if action["action"] == "install"),
        "erases": sum(1 for action in actions if action["action"] == "erase"),
        "upgrades": sum(1 for action in actions if action["action"] == "upgrade"),
        "architectures": _architecture_counts(actions),
    }
    if graph_snapshot is not None:
        summary.update(_graph_match_summary(actions))
    report: dict[str, Any] = {
        "schema": LIBSOLV_BRIDGE_SCHEMA,
        "ecosystem": "rpm",
        "summary": summary,
        "commands": commands,
        "transactionActions": actions,
        "integration": [
            "Use libsolv for RPM SAT solving and transaction explanation.",
            "Use EDGP to normalize solved packages into CSR graph snapshots and reports.",
            "Keep solver correctness in libsolv instead of maintaining a custom SAT engine for RPM metadata.",
        ],
    }
    if graph_snapshot is not None:
        report["graphContext"] = _graph_context(graph_snapshot, graph_snapshot_path)
        report["transactionImpact"] = _transaction_impact(actions)
    return report


def _load_graph_snapshot(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "edgp.graph.snapshot.v1":
        raise ValueError("libsolv graph matching requires edgp.graph.snapshot.v1")
    return payload


def _graph_context(payload: dict[str, Any], path: Path | None) -> dict[str, Any]:
    stats = payload.get("stats")
    if not isinstance(stats, dict):
        stats = {}
    return {
        "source": str(path) if path is not None else "",
        "schema": str(payload.get("schema") or ""),
        "ecosystem": str(payload.get("ecosystem") or ""),
        "root": str(payload.get("root") or ""),
        "nodes": int(stats.get("nodes", 0) or 0),
        "edges": int(stats.get("edges", 0) or 0),
    }


def _parse_transaction_actions(text: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        action, _, rest = line.partition(" ")
        action = action.lower().rstrip(":")
        if action not in {"install", "erase", "upgrade", "downgrade", "reinstall"}:
            continue
        package = rest.strip()
        old = ""
        new = ""
        if " -> " in package:
            old, _, new = package.partition(" -> ")
        action_record: dict[str, Any] = {
            "action": action,
            "package": package,
            "oldPackage": old,
            "newPackage": new,
        }
        if old or new:
            old_metadata = _parse_transaction_package(old)
            new_metadata = _parse_transaction_package(new)
            action_record["oldPackageMetadata"] = old_metadata
            action_record["newPackageMetadata"] = new_metadata
            _copy_primary_package_fields(action_record, new_metadata or old_metadata)
            if old_metadata:
                action_record["oldNodeId"] = old_metadata["nodeId"]
            if new_metadata:
                action_record["newNodeId"] = new_metadata["nodeId"]
        else:
            package_metadata = _parse_transaction_package(package)
            action_record["packageMetadata"] = package_metadata
            _copy_primary_package_fields(action_record, package_metadata)
        actions.append(action_record)
    return actions


def _attach_graph_matches(
    actions: list[dict[str, Any]], graph_snapshot: dict[str, Any]
) -> None:
    graph_index = _graph_index(graph_snapshot)
    for action in actions:
        matches = [
            _graph_match(graph_index, "package", action.get("packageMetadata")),
            _graph_match(graph_index, "old", action.get("oldPackageMetadata")),
            _graph_match(graph_index, "new", action.get("newPackageMetadata")),
        ]
        matches = [match for match in matches if match]
        action["graphMatches"] = matches
        matched_node_ids = sorted(
            {
                str(match["nodeId"])
                for match in matches
                if match.get("matched") and match.get("nodeId")
            }
        )
        action["graphMatchedNodeIds"] = matched_node_ids
        action["graphMatchStatus"] = _graph_match_status(matches)
        action["graphAffectedDependents"] = _matched_affected_dependents_count(matches)


def _graph_index(graph_snapshot: dict[str, Any]) -> dict[str, Any]:
    nodes = graph_snapshot.get("nodes")
    if not isinstance(nodes, list):
        nodes = []
    by_id: dict[str, dict[str, Any]] = {}
    by_name_arch: dict[tuple[str, str], list[str]] = {}
    dependents: dict[str, list[str]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        if not node_id:
            continue
        by_id[node_id] = node
        metadata = node.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        name = str(metadata.get("name") or node.get("name") or "")
        arch = str(metadata.get("arch") or "")
        if name and arch:
            by_name_arch.setdefault((name, arch), []).append(node_id)
        node_dependents = node.get("dependents")
        if not isinstance(node_dependents, list):
            node_dependents = []
        dependents[node_id] = [str(dependent) for dependent in node_dependents]
    return {
        "by_id": by_id,
        "by_name_arch": {
            key: sorted(values) for key, values in by_name_arch.items()
        },
        "dependents": dependents,
    }


def _graph_match(
    graph_index: dict[str, Any],
    role: str,
    metadata_value: object,
) -> dict[str, Any]:
    if not isinstance(metadata_value, dict):
        return {}
    metadata = {str(key): str(value) for key, value in metadata_value.items()}
    requested_node_id = metadata.get("nodeId", "")
    by_id: dict[str, dict[str, Any]] = graph_index["by_id"]
    if requested_node_id in by_id:
        return _matched_graph_node(
            graph_index,
            role,
            metadata,
            node_id=requested_node_id,
            match_type="exact",
            candidate_node_ids=[],
        )

    name = metadata.get("name", "")
    arch = metadata.get("arch", "")
    candidate_node_ids = graph_index["by_name_arch"].get((name, arch), [])
    if candidate_node_ids:
        return _matched_graph_node(
            graph_index,
            role,
            metadata,
            node_id=candidate_node_ids[0],
            match_type="name-arch",
            candidate_node_ids=candidate_node_ids,
        )

    return {
        "role": role,
        "matched": False,
        "matchType": "none",
        "requestedNodeId": requested_node_id,
        "packageName": name,
        "packageArch": arch,
        "nodeId": "",
        "candidateNodeIds": [],
        "directDependencies": 0,
        "directDependents": 0,
        "affectedDependents": 0,
    }


def _matched_graph_node(
    graph_index: dict[str, Any],
    role: str,
    metadata: dict[str, str],
    *,
    node_id: str,
    match_type: str,
    candidate_node_ids: list[str],
) -> dict[str, Any]:
    node = graph_index["by_id"][node_id]
    dependencies = node.get("dependencies")
    dependents = node.get("dependents")
    if not isinstance(dependencies, list):
        dependencies = []
    if not isinstance(dependents, list):
        dependents = []
    return {
        "role": role,
        "matched": True,
        "matchType": match_type,
        "requestedNodeId": metadata.get("nodeId", ""),
        "packageName": metadata.get("name", ""),
        "packageArch": metadata.get("arch", ""),
        "nodeId": node_id,
        "candidateNodeIds": candidate_node_ids,
        "directDependencies": len(dependencies),
        "directDependents": len(dependents),
        "affectedDependents": len(_reachable_dependents(graph_index, node_id)),
    }


def _reachable_dependents(graph_index: dict[str, Any], node_id: str) -> set[str]:
    dependents: dict[str, list[str]] = graph_index["dependents"]
    seen: set[str] = set()
    stack = list(dependents.get(node_id, []))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(dependents.get(current, []))
    return seen


def _graph_match_status(matches: list[dict[str, Any]]) -> str:
    if any(match.get("matchType") == "exact" for match in matches):
        return "exact"
    if any(match.get("matchType") == "name-arch" for match in matches):
        return "candidate"
    return "unmatched"


def _matched_affected_dependents_count(matches: list[dict[str, Any]]) -> int:
    return sum(
        int(match.get("affectedDependents", 0) or 0)
        for match in matches
        if match.get("matched")
    )


def _parse_transaction_package(package: str) -> dict[str, str]:
    package = package.strip()
    if not package:
        return {}

    stem = package.removesuffix(".rpm")
    nevr, separator, arch = stem.rpartition(".")
    if not separator:
        nevr = stem
        arch = "unknown"

    name_version_release = nevr.rsplit("-", 2)
    if len(name_version_release) != 3:
        return {
            "raw": package,
            "name": stem,
            "epoch": "0",
            "version": "",
            "release": "",
            "arch": arch,
            "nodeId": stem,
            "purl": _rpm_purl(stem, "unknown", arch=arch, epoch="0"),
        }

    name, version, release = name_version_release
    epoch = "0"
    if ":" in version:
        epoch, _, version = version.partition(":")

    evr = f"{version}-{release}" if release else version
    node_version = f"{evr}.{arch}" if arch and arch != "unknown" else evr
    node_id = f"{name}=={node_version}" if node_version else name
    return {
        "raw": package,
        "name": name,
        "epoch": epoch or "0",
        "version": version,
        "release": release,
        "evr": evr,
        "arch": arch,
        "nodeId": node_id,
        "purl": _rpm_purl(name, evr or "unknown", arch=arch, epoch=epoch or "0"),
    }


def _copy_primary_package_fields(
    action_record: dict[str, Any], metadata: dict[str, str]
) -> None:
    if not metadata:
        return
    action_record["packageName"] = metadata["name"]
    action_record["packageVersion"] = metadata["version"]
    action_record["packageRelease"] = metadata["release"]
    action_record["packageArch"] = metadata["arch"]
    action_record["nodeId"] = metadata["nodeId"]
    action_record["purl"] = metadata["purl"]


def _rpm_purl(name: str, version: str, *, arch: str, epoch: str) -> str:
    qualifiers = {}
    if arch and arch != "unknown":
        qualifiers["arch"] = arch
    if epoch and epoch not in {"0", "(none)"}:
        qualifiers["epoch"] = epoch
    suffix = f"?{urlencode(sorted(qualifiers.items()))}" if qualifiers else ""
    return f"pkg:rpm/{quote(name, safe='')}@{quote(version, safe='')}{suffix}"


def _architecture_counts(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for action in actions:
        arch = str(action.get("packageArch") or "unknown")
        counts[arch] = counts.get(arch, 0) + 1
    return [{"arch": arch, "actions": counts[arch]} for arch in sorted(counts)]


def _parsed_package_count(actions: list[dict[str, Any]]) -> int:
    count = 0
    for action in actions:
        for key in ("packageMetadata", "oldPackageMetadata", "newPackageMetadata"):
            if action.get(key):
                count += 1
    return count


def _graph_match_summary(actions: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = [str(action.get("graphMatchStatus") or "unmatched") for action in actions]
    matches = [
        match
        for action in actions
        for match in action.get("graphMatches", [])
        if isinstance(match, dict)
    ]
    return {
        "graphMatchedActions": sum(
            1 for status in statuses if status in {"exact", "candidate"}
        ),
        "graphImpactedActions": sum(
            1 for action in actions if int(action.get("graphAffectedDependents", 0) or 0)
        ),
        "graphExactActions": statuses.count("exact"),
        "graphCandidateActions": statuses.count("candidate"),
        "graphUnmatchedActions": statuses.count("unmatched"),
        "graphExactPackageMatches": sum(
            1 for match in matches if match.get("matchType") == "exact"
        ),
        "graphCandidatePackageMatches": sum(
            1 for match in matches if match.get("matchType") == "name-arch"
        ),
        "graphAffectedDependents": sum(
            int(action.get("graphAffectedDependents", 0) or 0)
            for action in actions
        ),
        "maxGraphAffectedDependents": max(
            (
                int(action.get("graphAffectedDependents", 0) or 0)
                for action in actions
            ),
            default=0,
        ),
    }


def _transaction_impact(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, action in enumerate(actions, start=1):
        matches = [
            match
            for match in action.get("graphMatches", [])
            if isinstance(match, dict)
        ]
        matched = [match for match in matches if match.get("matched")]
        rows.append(
            {
                "actionIndex": index,
                "action": str(action.get("action") or ""),
                "packageName": str(action.get("packageName") or ""),
                "packageArch": str(action.get("packageArch") or ""),
                "matchStatus": str(action.get("graphMatchStatus") or "unmatched"),
                "matchedRoles": sorted(
                    str(match.get("role") or "") for match in matched
                ),
                "matchedNodeIds": sorted(
                    str(match.get("nodeId") or "")
                    for match in matched
                    if match.get("nodeId")
                ),
                "directDependents": sum(
                    int(match.get("directDependents", 0) or 0)
                    for match in matched
                ),
                "affectedDependents": int(
                    action.get("graphAffectedDependents", 0) or 0
                ),
                "purl": str(action.get("purl") or ""),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -int(row["affectedDependents"]),
            _match_status_sort_key(str(row["matchStatus"])),
            int(row["actionIndex"]),
        ),
    )


def _match_status_sort_key(status: str) -> int:
    return {"exact": 0, "candidate": 1, "unmatched": 2}.get(status, 3)
