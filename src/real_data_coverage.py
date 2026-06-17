"""Real-data coverage report derived from EDGP fixture provenance."""

from __future__ import annotations

from collections import Counter
from typing import Any, Sequence

REAL_DATA_COVERAGE_SCHEMA = "edgp.real_data.coverage.v1"
FIXTURE_PROVENANCE_SCHEMA = "edgp.fixture.provenance.v1"

PUBLIC_EVIDENCE_KINDS = {
    "public-derived-source",
    "deterministic-public-derived-variant",
    "local-pointer-fixture",
    "generated-public-report",
}
PRIORITY_RANKS = {"low": 1, "medium": 2, "high": 3}

REPLACEMENT_DECISIONS: dict[str, dict[str, str]] = {
    "npm lockfiles and registry mock": {
        "decision": "hybrid",
        "priority": "medium",
        "nextStep": (
            "Replace the happy-path package-lock with a tiny public npm project "
            "lockfile; keep conflict and registry-mock fixtures synthetic because "
            "they isolate resolver edge cases."
        ),
    },
    "Python and Rust lockfiles": {
        "decision": "replace-where-practical",
        "priority": "medium",
        "nextStep": (
            "Use small public Poetry and Cargo lockfiles when their dependency "
            "shape is useful; keep parser-minimal fixtures for offline format smoke."
        ),
    },
    "Maven dependency trees": {
        "decision": "replace-where-practical",
        "priority": "medium",
        "nextStep": (
            "Add a captured dependency tree from a public Maven project, while "
            "keeping classifier, scope, marker, and packaging snippets synthetic."
        ),
    },
    "Generic graph and SBOM examples": {
        "decision": "hybrid",
        "priority": "low",
        "nextStep": (
            "Add one public CycloneDX SBOM when available; keep tiny graph "
            "snapshots synthetic so traversal and diff assertions stay auditable."
        ),
    },
    "Advisory and OSV-shaped samples": {
        "decision": "replace-where-practical",
        "priority": "high",
        "nextStep": (
            "Replace public advisory feed samples with curated OSV/GHSA/RHSA "
            "records where licensing and stability allow; keep severity edge cases "
            "synthetic."
        ),
    },
    "Report and export bundle fixtures": {
        "decision": "keep-generated",
        "priority": "low",
        "nextStep": (
            "Keep these as generated contract fixtures; they document EDGP output "
            "shape rather than upstream data fidelity."
        ),
    },
    "Validation failure examples": {
        "decision": "keep-synthetic",
        "priority": "low",
        "nextStep": (
            "Keep negative fixtures synthetic because they deliberately model "
            "invalid states that public sources should not provide."
        ),
    },
    "Performance, CSR, and license reports": {
        "decision": "keep-generated",
        "priority": "low",
        "nextStep": (
            "Refresh from deterministic EDGP generators; public replacement is "
            "less useful than stable performance and rendering contracts."
        ),
    },
}


def build_real_data_coverage_report(
    provenance: dict[str, Any],
    *,
    min_public_evidence_percent: float | None = None,
    fail_on_priority: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic report that separates public evidence from fixtures."""

    if provenance.get("schema") != FIXTURE_PROVENANCE_SCHEMA:
        raise ValueError("real-data coverage requires an EDGP fixture provenance report")

    entries = _dict_list(provenance.get("entries"))
    synthetic_groups = _dict_list(provenance.get("syntheticGroups"))
    source_urls = _dict_list(provenance.get("sourceUrls"))
    summary = provenance.get("summary")
    if not isinstance(summary, dict):
        summary = {}

    kind_counts = Counter(str(entry.get("kind", "")) for entry in entries)
    public_evidence = [
        _public_evidence_entry(entry)
        for entry in entries
        if entry.get("kind") in PUBLIC_EVIDENCE_KINDS
    ]
    synthetic_summaries = [
        _synthetic_group_entry(group) for group in synthetic_groups
    ]
    synthetic_files = sum(int(group.get("fileCount", 0) or 0) for group in synthetic_summaries)
    cataloged_files = int(
        summary.get("catalogedFiles", len(public_evidence) + synthetic_files) or 0
    )
    public_evidence_files = len(public_evidence)
    replacement_plan = [
        _replacement_plan_entry(group) for group in synthetic_summaries
    ]
    replacement_candidates = sum(
        1 for item in replacement_plan if item["priority"] in {"high", "medium"}
    )

    report = {
        "schema": REAL_DATA_COVERAGE_SCHEMA,
        "sourceSchema": FIXTURE_PROVENANCE_SCHEMA,
        "generatedBy": "src.real_data_coverage.build_real_data_coverage_report",
        "fixtureRoot": str(provenance.get("fixtureRoot", "")),
        "status": "warn" if replacement_candidates else "pass",
        "summary": {
            "catalogedFiles": cataloged_files,
            "directPublicSources": kind_counts["public-derived-source"],
            "deterministicPublicDerivedVariants": kind_counts[
                "deterministic-public-derived-variant"
            ],
            "localPointerFixtures": kind_counts["local-pointer-fixture"],
            "generatedPublicReports": kind_counts["generated-public-report"],
            "publicEvidenceFiles": public_evidence_files,
            "syntheticGroups": len(synthetic_summaries),
            "syntheticFiles": synthetic_files,
            "sourceUrls": len(source_urls),
            "publicEvidenceCoveragePercent": _percentage(
                public_evidence_files,
                cataloged_files,
            ),
            "directPublicSourceCoveragePercent": _percentage(
                kind_counts["public-derived-source"],
                cataloged_files,
            ),
            "replacementCandidateGroups": replacement_candidates,
            "intentionallySyntheticGroups": (
                len(replacement_plan) - replacement_candidates
            ),
        },
        "sourceUrls": [
            {
                "label": str(source.get("label", "")),
                "url": str(source.get("url", "")),
                "access": str(source.get("access", "")),
                "refreshedAt": str(source.get("refreshedAt", "")),
            }
            for source in source_urls
        ],
        "publicEvidence": public_evidence,
        "syntheticGroups": synthetic_summaries,
        "replacementPlan": replacement_plan,
        "qualityGates": _quality_gates(provenance),
    }
    policy = _policy(
        report["summary"],
        replacement_plan,
        min_public_evidence_percent=min_public_evidence_percent,
        fail_on_priority=fail_on_priority,
    )
    if policy is not None:
        report["policy"] = policy
        if policy["status"] == "fail":
            report["status"] = "fail"
    return report


def _public_evidence_entry(entry: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(entry.get("path", "")),
        "kind": str(entry.get("kind", "")),
    }
    for key in (
        "source",
        "sourceUrl",
        "reportSchema",
        "generator",
        "refreshedAt",
        "notes",
    ):
        value = entry.get(key)
        if isinstance(value, str) and value:
            result[key] = value
    derived_from = _string_list(entry.get("derivedFrom"))
    if derived_from:
        result["derivedFrom"] = derived_from
    return result


def _synthetic_group_entry(group: dict[str, Any]) -> dict[str, Any]:
    files = _string_list(group.get("files"))
    return {
        "group": str(group.get("group", "")),
        "kind": str(group.get("kind", "")),
        "fileCount": int(group.get("fileCount", len(files)) or 0),
        "reason": str(group.get("reason", "")),
        "files": files,
    }


def _replacement_plan_entry(group: dict[str, Any]) -> dict[str, str | int]:
    decision = REPLACEMENT_DECISIONS.get(
        str(group.get("group", "")),
        {
            "decision": "review",
            "priority": "low",
            "nextStep": "Review whether a public fixture improves coverage.",
        },
    )
    return {
        "group": str(group.get("group", "")),
        "kind": str(group.get("kind", "")),
        "fileCount": int(group.get("fileCount", 0) or 0),
        "decision": decision["decision"],
        "priority": decision["priority"],
        "nextStep": decision["nextStep"],
    }


def _quality_gates(provenance: dict[str, Any]) -> list[dict[str, str]]:
    refresh = provenance.get("refresh")
    if not isinstance(refresh, dict):
        refresh = {}
    check_commands = _string_list(refresh.get("checkCommands"))
    return [
        {
            "name": "public fixture freshness",
            "command": " && ".join(check_commands)
            if check_commands
            else "python -B scripts/generate_fixture_provenance.py --check",
        },
        {
            "name": "real-data coverage JSON",
            "command": "edgp real-data-coverage --fixture-dir tests/fixtures",
        },
        {
            "name": "real-data coverage bundle",
            "command": (
                "edgp real-data-coverage-bundle --fixture-dir tests/fixtures "
                "--output-dir reports/real-data-coverage --triage-summary"
            ),
        },
    ]


def _policy(
    summary: dict[str, Any],
    replacement_plan: Sequence[dict[str, Any]],
    *,
    min_public_evidence_percent: float | None,
    fail_on_priority: str | None,
) -> dict[str, Any] | None:
    if min_public_evidence_percent is None and fail_on_priority is None:
        return None

    failures: list[dict[str, Any]] = []
    coverage = float(summary.get("publicEvidenceCoveragePercent", 0.0) or 0.0)
    if (
        min_public_evidence_percent is not None
        and coverage < min_public_evidence_percent
    ):
        failures.append(
            {
                "code": "publicEvidenceCoverageBelowThreshold",
                "message": (
                    "Public evidence coverage is below the configured threshold."
                ),
                "actual": coverage,
                "expected": min_public_evidence_percent,
            }
        )

    matched_priorities = _replacement_priority_matches(
        replacement_plan,
        fail_on_priority=fail_on_priority,
    )
    if matched_priorities:
        failures.append(
            {
                "code": "replacementPriorityMatched",
                "message": (
                    "Replacement-plan groups matched the configured priority gate."
                ),
                "failOnPriority": fail_on_priority,
                "groups": matched_priorities,
            }
        )

    return {
        "minPublicEvidenceCoveragePercent": min_public_evidence_percent,
        "failOnPriority": fail_on_priority,
        "matchedReplacementGroups": len(matched_priorities),
        "status": "fail" if failures else "pass",
        "exitCode": 2 if failures else 0,
        "failures": failures,
    }


def _replacement_priority_matches(
    replacement_plan: Sequence[dict[str, Any]],
    *,
    fail_on_priority: str | None,
) -> list[dict[str, Any]]:
    if fail_on_priority is None:
        return []
    threshold = PRIORITY_RANKS[fail_on_priority]
    return [
        {
            "group": str(item.get("group", "")),
            "priority": str(item.get("priority", "")),
            "decision": str(item.get("decision", "")),
        }
        for item in replacement_plan
        if PRIORITY_RANKS.get(str(item.get("priority", "")), 0) >= threshold
    ]


def _dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _percentage(part: int, whole: int) -> float:
    if whole <= 0:
        return 0.0
    return round((part / whole) * 100, 2)
