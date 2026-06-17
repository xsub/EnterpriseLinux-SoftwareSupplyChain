"""Compare EDGP real-data coverage reports for CI trend review."""

from __future__ import annotations

from typing import Any

REAL_DATA_COVERAGE_DIFF_SCHEMA = "edgp.real_data.coverage_diff.v1"
REAL_DATA_COVERAGE_SCHEMA = "edgp.real_data.coverage.v1"


def build_real_data_coverage_diff_report(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    left_label: str = "left",
    right_label: str = "right",
    fail_on_regression: bool = False,
) -> dict[str, Any]:
    """Build a deterministic diff between two real-data coverage reports."""

    if left.get("schema") != REAL_DATA_COVERAGE_SCHEMA:
        raise ValueError("left input must be an EDGP real-data coverage report")
    if right.get("schema") != REAL_DATA_COVERAGE_SCHEMA:
        raise ValueError("right input must be an EDGP real-data coverage report")

    left_summary = _summary(left)
    right_summary = _summary(right)
    public_evidence = _path_diff(
        _dict_list(left.get("publicEvidence")),
        _dict_list(right.get("publicEvidence")),
    )
    synthetic_groups = _group_diff(
        _dict_list(left.get("syntheticGroups")),
        _dict_list(right.get("syntheticGroups")),
        keys=("kind", "fileCount", "reason", "files"),
    )
    replacement_plan = _group_diff(
        _dict_list(left.get("replacementPlan")),
        _dict_list(right.get("replacementPlan")),
        keys=("kind", "fileCount", "decision", "priority", "nextStep"),
    )
    summary = {
        "publicEvidenceCoveragePercentDelta": _number_delta(
            left_summary,
            right_summary,
            "publicEvidenceCoveragePercent",
        ),
        "directPublicSourceCoveragePercentDelta": _number_delta(
            left_summary,
            right_summary,
            "directPublicSourceCoveragePercent",
        ),
        "directPublicSourcesDelta": _int_delta(
            left_summary,
            right_summary,
            "directPublicSources",
        ),
        "publicEvidenceFilesDelta": _int_delta(
            left_summary,
            right_summary,
            "publicEvidenceFiles",
        ),
        "generatedPublicReportsDelta": _int_delta(
            left_summary,
            right_summary,
            "generatedPublicReports",
        ),
        "syntheticFilesDelta": _int_delta(
            left_summary,
            right_summary,
            "syntheticFiles",
        ),
        "replacementCandidateGroupsDelta": _int_delta(
            left_summary,
            right_summary,
            "replacementCandidateGroups",
        ),
        "addedPublicEvidence": len(public_evidence["added"]),
        "removedPublicEvidence": len(public_evidence["removed"]),
        "changedSyntheticGroups": len(synthetic_groups["changed"]),
        "changedReplacementGroups": len(replacement_plan["changed"]),
    }
    regressions = _regressions(summary)
    summary["regressions"] = len(regressions)
    report: dict[str, Any] = {
        "schema": REAL_DATA_COVERAGE_DIFF_SCHEMA,
        "left": _side(left, left_label),
        "right": _side(right, right_label),
        "status": "pass",
        "summary": summary,
        "publicEvidence": public_evidence,
        "syntheticGroups": synthetic_groups,
        "replacementPlan": replacement_plan,
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
        "publicEvidenceCoveragePercent": float(
            summary.get("publicEvidenceCoveragePercent", 0.0) or 0.0
        ),
        "publicEvidenceFiles": int(summary.get("publicEvidenceFiles", 0) or 0),
        "syntheticFiles": int(summary.get("syntheticFiles", 0) or 0),
        "replacementCandidateGroups": int(
            summary.get("replacementCandidateGroups", 0) or 0
        ),
    }


def _path_diff(
    left_items: list[dict[str, Any]],
    right_items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    left_by_path = _by_key(left_items, "path")
    right_by_path = _by_key(right_items, "path")
    return {
        "added": [
            right_by_path[path] for path in sorted(set(right_by_path) - set(left_by_path))
        ],
        "removed": [
            left_by_path[path] for path in sorted(set(left_by_path) - set(right_by_path))
        ],
    }


def _group_diff(
    left_items: list[dict[str, Any]],
    right_items: list[dict[str, Any]],
    *,
    keys: tuple[str, ...],
) -> dict[str, list[dict[str, Any]]]:
    left_by_group = _by_key(left_items, "group")
    right_by_group = _by_key(right_items, "group")
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
            "publicEvidenceCoverageDecreased",
            "publicEvidenceCoveragePercentDelta",
            "Public evidence coverage decreased.",
            "negative",
        ),
        (
            "directPublicSourcesDecreased",
            "directPublicSourcesDelta",
            "Direct public source count decreased.",
            "negative",
        ),
        (
            "publicEvidenceFilesDecreased",
            "publicEvidenceFilesDelta",
            "Public evidence file count decreased.",
            "negative",
        ),
        (
            "syntheticFilesIncreased",
            "syntheticFilesDelta",
            "Synthetic fixture file count increased.",
            "positive",
        ),
        (
            "replacementCandidateGroupsIncreased",
            "replacementCandidateGroupsDelta",
            "Replacement candidate group count increased.",
            "positive",
        ),
    ]
    regressions = []
    for code, key, message, direction in checks:
        value = float(summary.get(key, 0) or 0)
        failed = value < 0 if direction == "negative" else value > 0
        if failed:
            regressions.append(
                {
                    "code": code,
                    "metric": key,
                    "delta": value,
                    "message": message,
                }
            )
    return regressions


def _by_key(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(item[key]): item
        for item in items
        if isinstance(item.get(key), str) and item.get(key)
    }


def _dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _int_delta(left: dict[str, Any], right: dict[str, Any], key: str) -> int:
    return int(right.get(key, 0) or 0) - int(left.get(key, 0) or 0)


def _number_delta(left: dict[str, Any], right: dict[str, Any], key: str) -> float:
    return round(float(right.get(key, 0.0) or 0.0) - float(left.get(key, 0.0) or 0.0), 2)
