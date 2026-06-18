"""Diff real-data replacement plans for public backlog trend review."""

from __future__ import annotations

from typing import Any

REAL_DATA_REPLACEMENT_PLAN_DIFF_SCHEMA = "edgp.real_data.replacement_plan_diff.v1"
REAL_DATA_REPLACEMENT_PLAN_SCHEMA = "edgp.real_data.replacement_plan.v1"


def build_real_data_replacement_plan_diff_report(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    left_label: str = "left",
    right_label: str = "right",
    fail_on_regression: bool = False,
) -> dict[str, Any]:
    """Build a deterministic diff between two replacement-plan reports."""

    if left.get("schema") != REAL_DATA_REPLACEMENT_PLAN_SCHEMA:
        raise ValueError("left input must be an EDGP real-data replacement plan")
    if right.get("schema") != REAL_DATA_REPLACEMENT_PLAN_SCHEMA:
        raise ValueError("right input must be an EDGP real-data replacement plan")

    left_summary = _summary(left)
    right_summary = _summary(right)
    candidates = _group_diff(
        _dict_list(left.get("replacementCandidates")),
        _dict_list(right.get("replacementCandidates")),
        keys=("kind", "fileCount", "decision", "priority", "nextStep", "files"),
    )
    deferred_groups = _group_diff(
        _dict_list(left.get("deferredGroups")),
        _dict_list(right.get("deferredGroups")),
        keys=("kind", "fileCount", "decision", "priority", "nextStep", "files"),
    )
    summary = {
        "replacementCandidatesDelta": _int_delta(
            left_summary,
            right_summary,
            "replacementCandidates",
        ),
        "candidateFilesDelta": _int_delta(
            left_summary,
            right_summary,
            "candidateFiles",
        ),
        "highPriorityGroupsDelta": _int_delta(
            left_summary,
            right_summary,
            "highPriorityGroups",
        ),
        "mediumPriorityGroupsDelta": _int_delta(
            left_summary,
            right_summary,
            "mediumPriorityGroups",
        ),
        "deferredGroupsDelta": _int_delta(left_summary, right_summary, "deferredGroups"),
        "addedCandidates": len(candidates["added"]),
        "removedCandidates": len(candidates["removed"]),
        "changedCandidates": len(candidates["changed"]),
        "addedDeferredGroups": len(deferred_groups["added"]),
        "removedDeferredGroups": len(deferred_groups["removed"]),
        "changedDeferredGroups": len(deferred_groups["changed"]),
    }
    regressions = _regressions(summary)
    summary["regressions"] = len(regressions)
    report: dict[str, Any] = {
        "schema": REAL_DATA_REPLACEMENT_PLAN_DIFF_SCHEMA,
        "left": _side(left, left_label),
        "right": _side(right, right_label),
        "status": "pass",
        "summary": summary,
        "replacementCandidates": candidates,
        "deferredGroups": deferred_groups,
        "regressions": regressions,
    }
    if fail_on_regression:
        policy = {
            "failOnRegression": True,
            "status": "fail" if regressions else "pass",
            "exitCode": 2 if regressions else 0,
            "failures": regressions,
        }
        report["policy"] = policy
        if regressions:
            report["status"] = "fail"
    return report


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary")
    return summary if isinstance(summary, dict) else {}


def _side(report: dict[str, Any], label: str) -> dict[str, Any]:
    summary = _summary(report)
    return {
        "label": label,
        "fixtureRoot": str(report.get("fixtureRoot", "")),
        "status": str(report.get("status", "")),
        "replacementCandidates": int(summary.get("replacementCandidates", 0) or 0),
        "candidateFiles": int(summary.get("candidateFiles", 0) or 0),
        "highPriorityGroups": int(summary.get("highPriorityGroups", 0) or 0),
        "mediumPriorityGroups": int(summary.get("mediumPriorityGroups", 0) or 0),
        "deferredGroups": int(summary.get("deferredGroups", 0) or 0),
        "publicEvidenceCoveragePercent": float(
            summary.get("publicEvidenceCoveragePercent", 0.0) or 0.0
        ),
    }


def _group_diff(
    left_items: list[dict[str, Any]],
    right_items: list[dict[str, Any]],
    *,
    keys: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    left_by_group = _by_group(left_items)
    right_by_group = _by_group(right_items)
    left_groups = set(left_by_group)
    right_groups = set(right_by_group)
    changed = []
    for group in sorted(left_groups & right_groups):
        left_item = left_by_group[group]
        right_item = right_by_group[group]
        changed_keys = [
            key for key in keys if left_item.get(key) != right_item.get(key)
        ]
        if changed_keys:
            changed.append(
                {
                    "group": group,
                    "changedKeys": changed_keys,
                    "left": {key: left_item.get(key) for key in changed_keys},
                    "right": {key: right_item.get(key) for key in changed_keys},
                }
            )
    return {
        "added": [
            right_by_group[group] for group in sorted(right_groups - left_groups)
        ],
        "removed": [
            left_by_group[group] for group in sorted(left_groups - right_groups)
        ],
        "changed": changed,
    }


def _regressions(summary: dict[str, Any]) -> list[dict[str, Any]]:
    checks = [
        (
            "replacementCandidatesIncreased",
            "replacementCandidatesDelta",
            "Replacement candidate group count increased.",
        ),
        (
            "candidateFilesIncreased",
            "candidateFilesDelta",
            "Replacement candidate file count increased.",
        ),
        (
            "highPriorityGroupsIncreased",
            "highPriorityGroupsDelta",
            "High-priority replacement group count increased.",
        ),
    ]
    regressions = []
    for code, key, message in checks:
        value = float(summary.get(key, 0) or 0)
        if value > 0:
            regressions.append(
                {
                    "code": code,
                    "metric": key,
                    "delta": value,
                    "message": message,
                }
            )
    return regressions


def _by_group(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(item["group"]): item
        for item in items
        if isinstance(item.get("group"), str) and item.get("group")
    }


def _dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _int_delta(left: dict[str, Any], right: dict[str, Any], key: str) -> int:
    return int(right.get(key, 0) or 0) - int(left.get(key, 0) or 0)
