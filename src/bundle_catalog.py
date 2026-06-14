"""Catalog verified EDGP report bundles for batch investigation workflows."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

from src.output.report_bundle import verify_report_bundle

BUNDLE_CATALOG_SCHEMA = "edgp.bundle.catalog.v1"


def build_bundle_catalog_report(
    bundle_dirs: Sequence[Path],
    *,
    manifest_name: str = "manifest.json",
) -> dict[str, Any]:
    """Summarize multiple static report bundles into one EDGP report."""
    if not bundle_dirs:
        raise ValueError("At least one --bundle is required for bundle catalog")

    entries = [
        _bundle_catalog_entry(bundle_dir, manifest_name=manifest_name)
        for bundle_dir in bundle_dirs
    ]
    return {
        "schema": BUNDLE_CATALOG_SCHEMA,
        "manifestName": manifest_name,
        "summary": _summary(entries),
        "sourceKinds": _source_kind_summary(entries),
        "bundles": entries,
    }


def _bundle_catalog_entry(bundle_dir: Path, *, manifest_name: str) -> dict[str, Any]:
    bundle_dir = bundle_dir.resolve()
    verification = verify_report_bundle(bundle_dir, manifest_name=manifest_name)
    manifest = _load_manifest(bundle_dir / manifest_name)
    bundle_metadata = manifest.get("bundle", {}) if isinstance(manifest, dict) else {}
    if not isinstance(bundle_metadata, dict):
        bundle_metadata = {}
    reports = manifest.get("reports", []) if isinstance(manifest, dict) else []
    if not isinstance(reports, list):
        reports = []
    triage_summary = (
        manifest.get("triageSummary", {}) if isinstance(manifest, dict) else {}
    )
    if not isinstance(triage_summary, dict):
        triage_summary = {}
    failure_codes = [
        str(failure.get("code", "unknown"))
        for failure in verification.get("failures", [])
        if isinstance(failure, dict)
    ]
    verification_summary = verification.get("summary", {})
    if not isinstance(verification_summary, dict):
        verification_summary = {}
    return {
        "path": str(bundle_dir),
        "manifest": manifest_name,
        "ok": bool(verification.get("ok")),
        "sourceKind": str(bundle_metadata.get("sourceKind") or "unknown"),
        "command": str(bundle_metadata.get("command") or ""),
        "bundleSha256": verification.get("bundleSha256"),
        "reportCount": int(verification_summary.get("reports", 0) or 0),
        "failureCount": int(verification_summary.get("failures", 0) or 0),
        "failureCodes": failure_codes,
        "reportSchemas": _report_schemas(reports),
        "triageStatus": _triage_status(bundle_dir, triage_summary),
    }


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _report_schemas(reports: list[object]) -> list[str]:
    schemas = []
    for report in reports:
        if isinstance(report, dict) and isinstance(report.get("schema"), str):
            schemas.append(report["schema"])
    return sorted(set(schemas))


def _triage_status(bundle_dir: Path, triage_summary: dict[str, Any]) -> str:
    source = triage_summary.get("source")
    if not isinstance(source, str) or not source:
        return "not-present"
    triage_path = bundle_dir / source
    try:
        payload = json.loads(triage_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return "unreadable"
    if not isinstance(payload, dict):
        return "unreadable"
    return str(payload.get("status") or "unknown")


def _summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    triage_counts: dict[str, int] = defaultdict(int)
    for entry in entries:
        triage_counts[str(entry.get("triageStatus") or "unknown")] += 1
    return {
        "bundles": len(entries),
        "okBundles": sum(1 for entry in entries if entry.get("ok") is True),
        "failedBundles": sum(1 for entry in entries if entry.get("ok") is not True),
        "reports": sum(int(entry.get("reportCount", 0) or 0) for entry in entries),
        "failures": sum(int(entry.get("failureCount", 0) or 0) for entry in entries),
        "triagePass": triage_counts.get("pass", 0),
        "triageWarn": triage_counts.get("warn", 0),
        "triageFail": triage_counts.get("fail", 0),
        "withoutTriage": triage_counts.get("not-present", 0),
    }


def _source_kind_summary(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        source_kind = str(entry.get("sourceKind") or "unknown")
        row = grouped.setdefault(
            source_kind,
            {"sourceKind": source_kind, "bundles": 0, "reports": 0, "failures": 0},
        )
        row["bundles"] += 1
        row["reports"] += int(entry.get("reportCount", 0) or 0)
        row["failures"] += int(entry.get("failureCount", 0) or 0)
    return [grouped[key] for key in sorted(grouped)]
