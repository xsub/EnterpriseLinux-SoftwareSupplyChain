"""Aggregate dry-run submission plans into one CI/workbench index."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

SUBMISSION_PLAN_INDEX_SCHEMA = "edgp.submission.plan.index.v1"
SUPPORTED_SUBMISSION_PLAN_SCHEMAS = {
    "edgp.export.batch.submission_plan.v1",
    "edgp.report.bundle.submission_plan.v1",
}


def build_submission_plan_index(
    input_paths: Sequence[Path],
    *,
    command: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic summary over existing dry-run submission plans."""

    if not input_paths:
        raise ValueError("At least one --input is required for a submission plan index")

    plans = []
    failures = []
    for path in input_paths:
        entry, entry_failures = _load_plan_entry(path)
        plans.append(entry)
        failures.extend(entry_failures)

    failed_plans = [entry for entry in plans if not entry["ok"]]
    triage_warn = sum(1 for entry in plans if entry.get("triageStatus") == "warn")
    triage_fail = sum(1 for entry in plans if entry.get("triageStatus") == "fail")
    summary = {
        "plans": len(plans),
        "okPlans": len(plans) - len(failed_plans),
        "failedPlans": len(failed_plans),
        "artifacts": sum(int(entry["artifacts"]) for entry in plans),
        "bytes": sum(int(entry["bytes"]) for entry in plans),
        "failures": sum(int(entry["failures"]) for entry in plans),
        "targets": sorted(
            {
                str(entry["target"]["kind"])
                for entry in plans
                if isinstance(entry.get("target"), dict)
                and isinstance(entry["target"].get("kind"), str)
                and entry["target"]["kind"]
            }
        ),
        "schemas": sorted(
            {
                str(entry["schema"])
                for entry in plans
                if isinstance(entry.get("schema"), str) and entry["schema"]
            }
        ),
    }
    if triage_warn or triage_fail:
        summary["triageWarn"] = triage_warn
        summary["triageFail"] = triage_fail
    index = {
        "schema": SUBMISSION_PLAN_INDEX_SCHEMA,
        "ok": not failed_plans,
        "summary": summary,
        "plans": plans,
        "failures": failures,
    }
    if command:
        index["command"] = command
    return index


def _load_plan_entry(path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    resolved = path.resolve()
    failures: list[dict[str, str]] = []
    payload: dict[str, Any] = {}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload = loaded
        else:
            failures.append(
                {
                    "code": "planInvalid",
                    "message": "Submission plan must be a JSON object",
                    "path": str(resolved),
                }
            )
    except FileNotFoundError:
        failures.append(
            {
                "code": "planMissing",
                "message": "Submission plan file is missing",
                "path": str(resolved),
            }
        )
    except json.JSONDecodeError as error:
        failures.append(
            {
                "code": "planInvalidJson",
                "message": str(error),
                "path": str(resolved),
            }
        )

    schema = payload.get("schema") if isinstance(payload.get("schema"), str) else ""
    if payload and schema not in SUPPORTED_SUBMISSION_PLAN_SCHEMAS:
        failures.append(
            {
                "code": "planSchemaUnsupported",
                "message": f"Unsupported submission plan schema {schema or '<missing>'}",
                "path": str(resolved),
            }
        )

    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    target = payload.get("target", {}) if isinstance(payload, dict) else {}
    triage_summary = (
        payload.get("triageSummary", {}) if isinstance(payload, dict) else {}
    )
    triage_status = (
        triage_summary.get("status", "") if isinstance(triage_summary, dict) else ""
    )
    plan_failures = payload.get("failures", []) if isinstance(payload, dict) else []
    entry_failure_count = len(failures) + (
        len(plan_failures) if isinstance(plan_failures, list) else 0
    )
    entry = {
        "path": str(resolved),
        "schema": schema,
        "mode": str(payload.get("mode", "")) if isinstance(payload, dict) else "",
        "ok": (
            bool(payload.get("ok")) and not failures
            if isinstance(payload, dict)
            else False
        ),
        "target": {
            "kind": str(target.get("kind", "")) if isinstance(target, dict) else "",
            "endpoint": str(target.get("endpoint", "")) if isinstance(target, dict) else "",
        },
        "artifacts": _summary_int(summary, "artifacts"),
        "bytes": _summary_int(summary, "bytes"),
        "failures": entry_failure_count,
    }
    if triage_status:
        entry["triageStatus"] = str(triage_status)
    if not payload:
        entry["ok"] = False
    return entry, failures


def _summary_int(summary: object, key: str) -> int:
    if not isinstance(summary, dict):
        return 0
    value = summary.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0
