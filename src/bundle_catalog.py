"""Catalog verified EDGP report bundles for batch investigation workflows."""

from __future__ import annotations

import json
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Sequence

from src.output.report_bundle import verify_report_bundle, verify_report_bundle_archive

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
    summary = _summary(entries)
    return {
        "schema": BUNDLE_CATALOG_SCHEMA,
        "manifestName": manifest_name,
        "status": _status(summary),
        "summary": summary,
        "sourceKinds": _source_kind_summary(entries),
        "bundles": entries,
    }


def _bundle_catalog_entry(bundle_dir: Path, *, manifest_name: str) -> dict[str, Any]:
    if _is_report_bundle_archive(bundle_dir):
        return _bundle_archive_catalog_entry(bundle_dir, manifest_name=manifest_name)
    return _bundle_directory_catalog_entry(bundle_dir, manifest_name=manifest_name)


def _bundle_directory_catalog_entry(
    bundle_dir: Path,
    *,
    manifest_name: str,
) -> dict[str, Any]:
    bundle_dir = bundle_dir.resolve()
    verification = verify_report_bundle(bundle_dir, manifest_name=manifest_name)
    manifest = _load_manifest(bundle_dir / manifest_name)
    triage_summary = _triage_summary(
        lambda label: _load_manifest(_bundle_member_path(bundle_dir, label)),
        manifest,
    )
    return _catalog_entry(
        path=bundle_dir,
        input_type="directory",
        manifest_name=manifest_name,
        verification=verification,
        manifest=manifest,
        triage_summary=triage_summary,
    )


def _bundle_archive_catalog_entry(
    archive_path: Path,
    *,
    manifest_name: str,
) -> dict[str, Any]:
    archive_path = archive_path.resolve()
    archive_report = verify_report_bundle_archive(
        archive_path,
        manifest_name=manifest_name,
    )
    verification = archive_report.get("verification", {})
    if not isinstance(verification, dict):
        verification = {}
    manifest = _load_archive_manifest(archive_path, manifest_name)
    triage_summary = _triage_summary(
        lambda label: _load_archive_json_member(archive_path, label),
        manifest,
    )
    return _catalog_entry(
        path=archive_path,
        input_type="archive",
        manifest_name=manifest_name,
        verification=verification,
        manifest=manifest,
        triage_summary=triage_summary,
    )


def _catalog_entry(
    *,
    path: Path,
    input_type: str,
    manifest_name: str,
    verification: dict[str, Any],
    manifest: dict[str, Any],
    triage_summary: dict[str, Any],
) -> dict[str, Any]:
    bundle_metadata = manifest.get("bundle", {}) if isinstance(manifest, dict) else {}
    if not isinstance(bundle_metadata, dict):
        bundle_metadata = {}
    reports = manifest.get("reports", []) if isinstance(manifest, dict) else []
    if not isinstance(reports, list):
        reports = []
    failure_codes = [
        str(failure.get("code", "unknown"))
        for failure in verification.get("failures", [])
        if isinstance(failure, dict)
    ]
    verification_summary = verification.get("summary", {})
    if not isinstance(verification_summary, dict):
        verification_summary = {}
    return {
        "path": str(path),
        "inputType": input_type,
        "manifest": manifest_name,
        "ok": bool(verification.get("ok")),
        "sourceKind": str(bundle_metadata.get("sourceKind") or "unknown"),
        "command": str(bundle_metadata.get("command") or ""),
        "bundleSha256": verification.get("bundleSha256"),
        "reportCount": int(verification_summary.get("reports", 0) or 0),
        "failureCount": int(verification_summary.get("failures", 0) or 0),
        "failureCodes": failure_codes,
        "reportSchemas": _report_schemas(reports),
        "triageStatus": str(triage_summary.get("status") or "unknown"),
        "graphDiffPolicyFailures": int(
            triage_summary.get("graphDiffPolicyFailures", 0) or 0
        ),
        "diffTreePolicyFailures": int(
            triage_summary.get("diffTreePolicyFailures", 0) or 0
        ),
        "realDataCoveragePolicyFailures": int(
            triage_summary.get("realDataCoveragePolicyFailures", 0) or 0
        ),
        "realDataCoverageDiffPolicyFailures": int(
            triage_summary.get("realDataCoverageDiffPolicyFailures", 0) or 0
        ),
        "graphDiffFailOnChanges": _string_list(
            triage_summary.get("graphDiffFailOnChanges")
        ),
        "graphDiffMatchedChanges": _string_list(
            triage_summary.get("graphDiffMatchedChanges")
        ),
        "graphDiffFailOnKinds": _string_list(
            triage_summary.get("graphDiffFailOnKinds")
        ),
        "graphDiffMatchedKinds": _string_list(
            triage_summary.get("graphDiffMatchedKinds")
        ),
        "diffTreeFailOnKinds": _string_list(triage_summary.get("diffTreeFailOnKinds")),
        "diffTreeMatchedKinds": _string_list(triage_summary.get("diffTreeMatchedKinds")),
    }


def _is_report_bundle_archive(path: Path) -> bool:
    suffixes = path.suffixes
    return path.suffix == ".tgz" or suffixes[-2:] == [".tar", ".gz"]


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_archive_manifest(archive_path: Path, manifest_name: str) -> dict[str, Any]:
    return _load_archive_json_member(archive_path, manifest_name)


def _load_archive_json_member(archive_path: Path, member_name: str) -> dict[str, Any]:
    if not _is_bundle_member_label(member_name):
        return {}
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            try:
                member = archive.getmember(member_name)
            except KeyError:
                return {}
            if not member.isfile():
                return {}
            source = archive.extractfile(member)
            if source is None:
                return {}
            payload = json.loads(source.read().decode("utf-8"))
    except (
        FileNotFoundError,
        OSError,
        tarfile.TarError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return {}
    return payload if isinstance(payload, dict) else {}


def _report_schemas(reports: list[object]) -> list[str]:
    schemas = []
    for report in reports:
        if isinstance(report, dict) and isinstance(report.get("schema"), str):
            schemas.append(report["schema"])
    return sorted(set(schemas))


def _triage_summary(
    load_member: Callable[[str], dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    triage_summary = manifest.get("triageSummary", {})
    if not isinstance(triage_summary, dict):
        triage_summary = {}
    source = triage_summary.get("source")
    if not isinstance(source, str) or not source:
        return {
            "status": "not-present",
            "graphDiffPolicyFailures": 0,
            "diffTreePolicyFailures": 0,
            "realDataCoveragePolicyFailures": 0,
            "realDataCoverageDiffPolicyFailures": 0,
            "graphDiffFailOnChanges": [],
            "graphDiffMatchedChanges": [],
            "graphDiffFailOnKinds": [],
            "graphDiffMatchedKinds": [],
            "diffTreeFailOnKinds": [],
            "diffTreeMatchedKinds": [],
        }
    payload = load_member(source)
    if not isinstance(payload, dict):
        return {
            "status": "unreadable",
            "graphDiffPolicyFailures": 0,
            "diffTreePolicyFailures": 0,
            "realDataCoveragePolicyFailures": 0,
            "realDataCoverageDiffPolicyFailures": 0,
            "graphDiffFailOnChanges": [],
            "graphDiffMatchedChanges": [],
            "graphDiffFailOnKinds": [],
            "graphDiffMatchedKinds": [],
            "diffTreeFailOnKinds": [],
            "diffTreeMatchedKinds": [],
        }
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    top_findings = payload.get("topFindings")
    if not isinstance(top_findings, dict):
        top_findings = {}
    graph_diff_policies = _object_list(top_findings.get("graphDiffPolicies"))
    diff_tree_policies = _object_list(top_findings.get("diffTreePolicies"))
    return {
        "status": str(payload.get("status") or "unknown"),
        "graphDiffPolicyFailures": int(
            summary.get("graphDiffPolicyFailures", 0) or 0
        ),
        "diffTreePolicyFailures": int(
            summary.get("diffTreePolicyFailures", 0) or 0
        ),
        "realDataCoveragePolicyFailures": int(
            summary.get("realDataCoveragePolicyFailures", 0) or 0
        ),
        "realDataCoverageDiffPolicyFailures": int(
            summary.get("realDataCoverageDiffPolicyFailures", 0) or 0
        ),
        "graphDiffFailOnChanges": _collect_policy_values(
            graph_diff_policies,
            "failOnChange",
        ),
        "graphDiffMatchedChanges": _collect_policy_values(
            graph_diff_policies,
            "matchedChanges",
        ),
        "graphDiffFailOnKinds": _collect_policy_values(
            graph_diff_policies,
            "failOnKind",
        ),
        "graphDiffMatchedKinds": _collect_policy_values(
            graph_diff_policies,
            "matchedKinds",
        ),
        "diffTreeFailOnKinds": _collect_policy_values(
            diff_tree_policies,
            "failOnKind",
        ),
        "diffTreeMatchedKinds": _collect_policy_values(
            diff_tree_policies,
            "matchedKinds",
        ),
    }


def _object_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _collect_policy_values(rows: list[dict[str, Any]], key: str) -> list[str]:
    values: list[str] = []
    for row in rows:
        for value in _string_list(row.get(key)):
            if value not in values:
                values.append(value)
    return values


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _bundle_member_path(bundle_dir: Path, label: str) -> Path:
    if not _is_bundle_member_label(label):
        return bundle_dir / "__invalid_bundle_member__"
    return bundle_dir / label


def _is_bundle_member_label(label: str) -> bool:
    member_path = Path(label)
    return bool(label) and not member_path.is_absolute() and ".." not in member_path.parts


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
        "graphDiffPolicyFailures": sum(
            int(entry.get("graphDiffPolicyFailures", 0) or 0) for entry in entries
        ),
        "diffTreePolicyFailures": sum(
            int(entry.get("diffTreePolicyFailures", 0) or 0) for entry in entries
        ),
        "realDataCoveragePolicyFailures": sum(
            int(entry.get("realDataCoveragePolicyFailures", 0) or 0)
            for entry in entries
        ),
        "realDataCoverageDiffPolicyFailures": sum(
            int(entry.get("realDataCoverageDiffPolicyFailures", 0) or 0)
            for entry in entries
        ),
    }


def _status(summary: dict[str, Any]) -> str:
    if (
        int(summary.get("failedBundles", 0) or 0)
        or int(summary.get("failures", 0) or 0)
        or int(summary.get("triageFail", 0) or 0)
        or int(summary.get("graphDiffPolicyFailures", 0) or 0)
        or int(summary.get("diffTreePolicyFailures", 0) or 0)
        or int(summary.get("realDataCoveragePolicyFailures", 0) or 0)
        or int(summary.get("realDataCoverageDiffPolicyFailures", 0) or 0)
    ):
        return "fail"
    if int(summary.get("triageWarn", 0) or 0):
        return "warn"
    return "pass"


def _source_kind_summary(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        source_kind = str(entry.get("sourceKind") or "unknown")
        row = grouped.setdefault(
            source_kind,
            {
                "sourceKind": source_kind,
                "bundles": 0,
                "reports": 0,
                "failures": 0,
                "triagePass": 0,
                "triageWarn": 0,
                "triageFail": 0,
                "withoutTriage": 0,
                "graphDiffPolicyFailures": 0,
                "diffTreePolicyFailures": 0,
                "realDataCoveragePolicyFailures": 0,
                "realDataCoverageDiffPolicyFailures": 0,
            },
        )
        row["bundles"] += 1
        row["reports"] += int(entry.get("reportCount", 0) or 0)
        row["failures"] += int(entry.get("failureCount", 0) or 0)
        triage_status = str(entry.get("triageStatus") or "unknown")
        if triage_status == "pass":
            row["triagePass"] += 1
        elif triage_status == "warn":
            row["triageWarn"] += 1
        elif triage_status == "fail":
            row["triageFail"] += 1
        elif triage_status == "not-present":
            row["withoutTriage"] += 1
        row["graphDiffPolicyFailures"] += int(
            entry.get("graphDiffPolicyFailures", 0) or 0
        )
        row["diffTreePolicyFailures"] += int(
            entry.get("diffTreePolicyFailures", 0) or 0
        )
        row["realDataCoveragePolicyFailures"] += int(
            entry.get("realDataCoveragePolicyFailures", 0) or 0
        )
        row["realDataCoverageDiffPolicyFailures"] += int(
            entry.get("realDataCoverageDiffPolicyFailures", 0) or 0
        )
    return [grouped[key] for key in sorted(grouped)]
