"""Real-data fixture replacement planning report."""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

from src.real_data_coverage import PRIORITY_RANKS, REAL_DATA_COVERAGE_SCHEMA

REAL_DATA_REPLACEMENT_PLAN_SCHEMA = "edgp.real_data.replacement_plan.v1"

REPLACEMENT_CANDIDATE_DECISIONS = {
    "hybrid",
    "replace-where-practical",
    "review",
}


def build_real_data_replacement_plan_report(
    coverage: dict[str, Any],
    *,
    fail_on_priority: str | None = None,
) -> dict[str, Any]:
    """Build a ranked plan for replacing synthetic fixtures with public data."""

    if coverage.get("schema") != REAL_DATA_COVERAGE_SCHEMA:
        raise ValueError("replacement planning requires an EDGP real-data coverage report")

    plan_entries = _dict_list(coverage.get("replacementPlan"))
    synthetic_groups = {
        str(group.get("group", "")): group
        for group in _dict_list(coverage.get("syntheticGroups"))
    }
    enriched = [
        _enriched_plan_entry(entry, synthetic_groups.get(str(entry.get("group", ""))))
        for entry in plan_entries
    ]
    replacement_candidates = [
        entry for entry in enriched if _is_replacement_candidate(entry)
    ]
    deferred_groups = [
        entry for entry in enriched if not _is_replacement_candidate(entry)
    ]
    replacement_candidates = _ranked(replacement_candidates)
    deferred_groups = _sorted_plan_entries(deferred_groups)
    summary = _summary(
        replacement_candidates,
        deferred_groups,
        coverage_summary=_dict(coverage.get("summary")),
    )
    report: dict[str, Any] = {
        "schema": REAL_DATA_REPLACEMENT_PLAN_SCHEMA,
        "sourceSchema": REAL_DATA_COVERAGE_SCHEMA,
        "generatedBy": (
            "src.real_data_replacement_plan."
            "build_real_data_replacement_plan_report"
        ),
        "fixtureRoot": str(coverage.get("fixtureRoot", "")),
        "status": "warn" if replacement_candidates else "pass",
        "summary": summary,
        "coverageSummary": _coverage_summary(coverage),
        "sourceUrls": _source_urls(coverage.get("sourceUrls")),
        "replacementCandidates": replacement_candidates,
        "deferredGroups": deferred_groups,
        "qualityGates": _quality_gates(),
    }
    policy = _policy(replacement_candidates, fail_on_priority=fail_on_priority)
    if policy is not None:
        report["policy"] = policy
        if policy["status"] == "fail":
            report["status"] = "fail"
    return report


def _enriched_plan_entry(
    entry: dict[str, Any],
    synthetic_group: dict[str, Any] | None,
) -> dict[str, Any]:
    files = _string_list(synthetic_group.get("files")) if synthetic_group else []
    return {
        "group": str(entry.get("group", "")),
        "kind": str(entry.get("kind", "")),
        "fileCount": int(entry.get("fileCount", 0) or 0),
        "decision": str(entry.get("decision", "")),
        "priority": str(entry.get("priority", "low")),
        "nextStep": str(entry.get("nextStep", "")),
        "files": files,
    }


def _ranked(entries: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for index, entry in enumerate(_sorted_plan_entries(entries), start=1):
        ranked.append({"rank": index, **entry})
    return ranked


def _sorted_plan_entries(entries: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        entries,
        key=lambda entry: (
            -PRIORITY_RANKS.get(str(entry.get("priority", "")), 0),
            -int(entry.get("fileCount", 0) or 0),
            str(entry.get("group", "")),
        ),
    )


def _is_replacement_candidate(entry: dict[str, Any]) -> bool:
    return str(entry.get("decision", "")) in REPLACEMENT_CANDIDATE_DECISIONS and (
        str(entry.get("priority", "")) in {"high", "medium"}
    )


def _summary(
    replacement_candidates: Sequence[dict[str, Any]],
    deferred_groups: Sequence[dict[str, Any]],
    *,
    coverage_summary: dict[str, Any],
) -> dict[str, Any]:
    priorities = Counter(
        str(entry.get("priority", "low"))
        for entry in [*replacement_candidates, *deferred_groups]
    )
    return {
        "totalGroups": len(replacement_candidates) + len(deferred_groups),
        "replacementCandidates": len(replacement_candidates),
        "candidateFiles": sum(
            int(entry.get("fileCount", 0) or 0) for entry in replacement_candidates
        ),
        "deferredGroups": len(deferred_groups),
        "highPriorityGroups": priorities["high"],
        "mediumPriorityGroups": priorities["medium"],
        "lowPriorityGroups": priorities["low"],
        "publicEvidenceFiles": int(
            coverage_summary.get("publicEvidenceFiles", 0) or 0
        ),
        "publicEvidenceCoveragePercent": float(
            coverage_summary.get("publicEvidenceCoveragePercent", 0.0) or 0.0
        ),
        "syntheticFiles": int(coverage_summary.get("syntheticFiles", 0) or 0),
    }


def _coverage_summary(coverage: dict[str, Any]) -> dict[str, Any]:
    summary = _dict(coverage.get("summary"))
    return {
        "coverageStatus": str(coverage.get("status", "")),
        "catalogedFiles": int(summary.get("catalogedFiles", 0) or 0),
        "directPublicSources": int(summary.get("directPublicSources", 0) or 0),
        "generatedPublicReports": int(summary.get("generatedPublicReports", 0) or 0),
        "publicEvidenceFiles": int(summary.get("publicEvidenceFiles", 0) or 0),
        "syntheticFiles": int(summary.get("syntheticFiles", 0) or 0),
        "publicEvidenceCoveragePercent": float(
            summary.get("publicEvidenceCoveragePercent", 0.0) or 0.0
        ),
    }


def _policy(
    replacement_candidates: Sequence[dict[str, Any]],
    *,
    fail_on_priority: str | None,
) -> dict[str, Any] | None:
    if fail_on_priority is None:
        return None

    threshold = PRIORITY_RANKS[fail_on_priority]
    matched = [
        {
            "group": str(entry.get("group", "")),
            "priority": str(entry.get("priority", "")),
            "decision": str(entry.get("decision", "")),
            "rank": int(entry.get("rank", 0) or 0),
        }
        for entry in replacement_candidates
        if PRIORITY_RANKS.get(str(entry.get("priority", "")), 0) >= threshold
    ]
    failures = []
    if matched:
        failures.append(
            {
                "code": "replacementPlanPriorityMatched",
                "message": (
                    "Replacement-plan candidates matched the configured "
                    "priority gate."
                ),
                "failOnPriority": fail_on_priority,
                "groups": matched,
            }
        )
    return {
        "failOnPriority": fail_on_priority,
        "matchedReplacementGroups": len(matched),
        "status": "fail" if failures else "pass",
        "exitCode": 2 if failures else 0,
        "failures": failures,
    }


def _quality_gates() -> list[dict[str, str]]:
    return [
        {
            "name": "fixture provenance freshness",
            "command": (
                "python -B scripts/generate_public_fixture_reports.py --check && "
                "python -B scripts/generate_fixture_provenance.py --check"
            ),
        },
        {
            "name": "real-data replacement plan JSON",
            "command": "edgp real-data-replacement-plan --fixture-dir tests/fixtures",
        },
        {
            "name": "real-data replacement plan bundle",
            "command": (
                "edgp real-data-replacement-plan-bundle "
                "--fixture-dir tests/fixtures "
                "--output-dir reports/real-data-replacement-plan --triage-summary"
            ),
        },
    ]


def _source_urls(value: object) -> list[dict[str, str]]:
    urls = []
    for source in _dict_list(value):
        urls.append(
            {
                "label": str(source.get("label", "")),
                "url": str(source.get("url", "")),
                "access": str(source.get("access", "")),
                "refreshedAt": str(source.get("refreshedAt", "")),
            }
        )
    return urls


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]
