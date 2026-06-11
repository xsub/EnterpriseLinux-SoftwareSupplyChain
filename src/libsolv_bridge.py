"""libsolv command discovery and transaction-output bridge report."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

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
            "installs": sum(1 for action in actions if action["action"] == "install"),
            "erases": sum(1 for action in actions if action["action"] == "erase"),
            "upgrades": sum(1 for action in actions if action["action"] == "upgrade"),
        },
        "commands": commands,
        "transactionActions": actions,
        "integration": [
            "Use libsolv for RPM SAT solving and transaction explanation.",
            "Use EDGP to normalize solved packages into CSR graph snapshots and reports.",
            "Keep solver correctness in libsolv instead of maintaining a custom SAT engine for RPM metadata.",
        ],
    }


def _parse_transaction_actions(text: str) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
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
        actions.append(
            {
                "action": action,
                "package": package,
                "oldPackage": old,
                "newPackage": new,
            }
        )
    return actions
