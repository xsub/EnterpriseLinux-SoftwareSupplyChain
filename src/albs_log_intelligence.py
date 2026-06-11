"""ALBS build log signal extraction for public build metadata."""

from __future__ import annotations

import re
from typing import Any, Mapping

ALBS_LOG_INTELLIGENCE_SCHEMA = "edgp.albs.log_intelligence.v1"

_SIGNAL_PATTERNS = {
    "error": re.compile(r"\berror\b|error:", re.IGNORECASE),
    "failed": re.compile(r"\bfailed\b|\bfailure\b", re.IGNORECASE),
    "fatal": re.compile(r"\bfatal\b|fatal:", re.IGNORECASE),
    "missing": re.compile(r"\bmissing\b|no matching package|not found", re.IGNORECASE),
    "warning": re.compile(r"\bwarning\b|warning:", re.IGNORECASE),
}


def build_albs_log_intelligence_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Extract deterministic build-log signals from ALBS metadata."""

    build_id = str(payload.get("id") or payload.get("build_id") or "unknown")
    logs = [_log_entry(task, artifact) for task in _object_list(payload.get("tasks")) for artifact in _object_list(task.get("artifacts")) if artifact.get("type") == "build_log"]
    analyzed = [log for log in logs if log["contentAvailable"]]
    signal_counts: dict[str, int] = {name: 0 for name in _SIGNAL_PATTERNS}
    for log in analyzed:
        for name, count in log["signals"].items():
            signal_counts[name] += int(count)
    signal_counts = {key: value for key, value in signal_counts.items() if value}
    return {
        "schema": ALBS_LOG_INTELLIGENCE_SCHEMA,
        "ecosystem": "albs",
        "root": f"albs-build:{build_id}",
        "summary": {
            "logArtifacts": len(logs),
            "logsWithInlineContent": len(analyzed),
            "signalKinds": len(signal_counts),
            "signals": sum(signal_counts.values()),
        },
        "signalCounts": signal_counts,
        "logs": logs,
    }


def _log_entry(task: Mapping[str, Any], artifact: Mapping[str, Any]) -> dict[str, Any]:
    content = _log_content(artifact)
    signals = _signals(content)
    return {
        "artifactId": str(artifact.get("id") or ""),
        "name": str(artifact.get("name") or ""),
        "buildTaskId": str(task.get("id") or ""),
        "buildArch": str(task.get("arch") or "unknown"),
        "href": str(artifact.get("href") or ""),
        "casHash": str(artifact.get("cas_hash") or ""),
        "contentAvailable": bool(content),
        "lineCount": len(content.splitlines()) if content else 0,
        "signals": signals,
        "sample": _sample(content),
    }


def _log_content(artifact: Mapping[str, Any]) -> str:
    for key in ("log_content", "log", "content", "text", "excerpt"):
        value = artifact.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _signals(content: str) -> dict[str, int]:
    if not content:
        return {}
    return {
        name: len(pattern.findall(content))
        for name, pattern in _SIGNAL_PATTERNS.items()
        if pattern.search(content)
    }


def _sample(content: str) -> str:
    if not content:
        return ""
    interesting = [
        line.strip()
        for line in content.splitlines()
        if any(pattern.search(line) for pattern in _SIGNAL_PATTERNS.values())
    ]
    if not interesting:
        interesting = [line.strip() for line in content.splitlines() if line.strip()]
    return " | ".join(interesting[:3])[:500]


def _object_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
