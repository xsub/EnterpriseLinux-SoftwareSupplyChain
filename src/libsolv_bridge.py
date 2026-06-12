"""libsolv command discovery and transaction-output bridge report."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

LIBSOLV_BRIDGE_SCHEMA = "edgp.libsolv.bridge.v1"
LIBSOLV_COMMANDS = ("repo2solv", "rpmmd2solv", "testsolv", "dumpsolv")


def build_libsolv_bridge_report(transaction_path: Path | None = None) -> dict[str, Any]:
    """Describe available libsolv tooling and parse a transaction transcript."""

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
    return {
        "schema": LIBSOLV_BRIDGE_SCHEMA,
        "ecosystem": "rpm",
        "summary": {
            "commandsAvailable": sum(1 for command in commands if command["available"]),
            "transactionActions": len(actions),
            "parsedPackages": _parsed_package_count(actions),
            "installs": sum(1 for action in actions if action["action"] == "install"),
            "erases": sum(1 for action in actions if action["action"] == "erase"),
            "upgrades": sum(1 for action in actions if action["action"] == "upgrade"),
            "architectures": _architecture_counts(actions),
        },
        "commands": commands,
        "transactionActions": actions,
        "integration": [
            "Use libsolv for RPM SAT solving and transaction explanation.",
            "Use EDGP to normalize solved packages into CSR graph snapshots and reports.",
            "Keep solver correctness in libsolv instead of maintaining a custom SAT engine for RPM metadata.",
        ],
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
