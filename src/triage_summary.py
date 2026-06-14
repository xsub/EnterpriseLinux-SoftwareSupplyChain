"""Aggregate EDGP report bundles into one machine-readable triage summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

TRIAGE_SUMMARY_SCHEMA = "edgp.triage.summary.v1"


def build_triage_summary_report(
    reports: Sequence[dict[str, Any]],
    *,
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a compact triage rollup from EDGP report payloads."""

    rollup = _empty_rollup()
    report_entries = []
    checks = []
    advisory_findings = []
    license_findings = []
    npm_findings = []
    bundle_catalog_findings = []

    for report in reports:
        schema = str(report.get("schema", ""))
        summary = _summary(report)
        report_entries.append(
            {
                "schema": schema,
                "root": report.get("root"),
                "summary": summary,
            }
        )
        _accumulate_summary(rollup, schema, summary)
        if schema == "edgp.advisory.report.v1":
            findings = int(summary.get("findings", 0))
            checks.append(_check("advisory", findings, "findings"))
            advisory_findings.extend(_advisory_findings(report))
        elif schema == "edgp.license.report.v1":
            denied = int(summary.get("deniedFindings", 0))
            checks.append(_check("license", denied, "deniedFindings"))
            license_findings.extend(_license_findings(report))
        elif schema == "edgp.npm.diagnostics.v1":
            npm_findings.extend(_npm_findings(report, summary))
        elif schema == "edgp.bundle.catalog.v1":
            checks.append(_bundle_catalog_check(summary))
            bundle_catalog_findings.extend(_bundle_catalog_findings(report))

    status = _status(rollup)
    return {
        "schema": TRIAGE_SUMMARY_SCHEMA,
        "source": source or {"kind": "report-list"},
        "status": status,
        "summary": {
            **rollup,
            "reports": len(reports),
            "failedChecks": sum(1 for check in checks if check["status"] == "fail"),
        },
        "checks": checks,
        "topFindings": {
            "advisories": advisory_findings[:10],
            "licenses": license_findings[:10],
            "npm": npm_findings[:10],
            "bundleCatalog": bundle_catalog_findings[:10],
        },
        "reports": report_entries,
    }


def build_triage_summary_from_paths(paths: Sequence[Path]) -> dict[str, Any]:
    """Load EDGP JSON reports from paths and summarize them."""

    return build_triage_summary_report(
        [_load_json(path) for path in paths],
        source={"kind": "report-list", "reports": len(paths)},
    )


def build_triage_summary_from_bundle(
    bundle_dir: Path,
    *,
    manifest_name: str = "manifest.json",
) -> dict[str, Any]:
    """Load report sources listed in a bundle manifest and summarize them."""

    manifest_path = bundle_dir / manifest_name
    manifest = _load_json(manifest_path)
    reports = manifest.get("reports", [])
    if not isinstance(reports, list):
        raise ValueError("Bundle manifest reports must be a list")
    report_paths = []
    for report in reports:
        if not isinstance(report, dict):
            continue
        source = report.get("source")
        if isinstance(source, str) and source:
            report_paths.append(bundle_dir / source)
    summary = build_triage_summary_report(
        [_load_json(path) for path in report_paths],
        source={
            "kind": "bundle",
            "bundleDir": str(bundle_dir),
            "manifest": manifest_name,
            "bundleSha256": manifest.get("bundleSha256"),
            "reports": len(report_paths),
        },
    )
    summary["bundle"] = {
        "schema": manifest.get("schema"),
        "sourceKind": _bundle_source_kind(manifest),
        "reportCount": manifest.get("reportCount", len(report_paths)),
    }
    return summary


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Report must be a JSON object: {path}")
    return payload


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary")
    if isinstance(summary, dict):
        return dict(summary)
    stats = report.get("stats")
    if isinstance(stats, dict):
        return dict(stats)
    return {}


def _empty_rollup() -> dict[str, int]:
    return {
        "graphSnapshots": 0,
        "nodes": 0,
        "edges": 0,
        "impactReports": 0,
        "advisoryReports": 0,
        "advisoryFindings": 0,
        "licenseReports": 0,
        "deniedLicenseFindings": 0,
        "missingLicenses": 0,
        "npmDiagnosticsReports": 0,
        "npmDuplicatePackageNames": 0,
        "npmNestedResolutionConflicts": 0,
        "npmUnresolvedDependencies": 0,
        "bundleCatalogReports": 0,
        "catalogBundles": 0,
        "catalogFailedBundles": 0,
        "catalogFailures": 0,
        "catalogTriageWarn": 0,
        "catalogTriageFail": 0,
    }


def _accumulate_summary(
    rollup: dict[str, int],
    schema: str,
    summary: dict[str, Any],
) -> None:
    if schema == "edgp.graph.snapshot.v1":
        rollup["graphSnapshots"] += 1
        rollup["nodes"] += int(summary.get("nodes", 0))
        rollup["edges"] += int(summary.get("edges", 0))
    elif schema == "edgp.impact.report.v1":
        rollup["impactReports"] += 1
    elif schema == "edgp.advisory.report.v1":
        rollup["advisoryReports"] += 1
        rollup["advisoryFindings"] += int(summary.get("findings", 0))
    elif schema == "edgp.license.report.v1":
        rollup["licenseReports"] += 1
        rollup["deniedLicenseFindings"] += int(summary.get("deniedFindings", 0))
        rollup["missingLicenses"] += int(summary.get("missingLicenses", 0))
    elif schema == "edgp.npm.diagnostics.v1":
        rollup["npmDiagnosticsReports"] += 1
        rollup["npmDuplicatePackageNames"] += int(
            summary.get("duplicatePackageNames", 0)
        )
        rollup["npmNestedResolutionConflicts"] += int(
            summary.get("nestedResolutionConflicts", 0)
        )
        rollup["npmUnresolvedDependencies"] += int(
            summary.get("unresolvedDependencies", 0)
        )
    elif schema == "edgp.bundle.catalog.v1":
        rollup["bundleCatalogReports"] += 1
        rollup["catalogBundles"] += int(summary.get("bundles", 0))
        rollup["catalogFailedBundles"] += int(summary.get("failedBundles", 0))
        rollup["catalogFailures"] += int(summary.get("failures", 0))
        rollup["catalogTriageWarn"] += int(summary.get("triageWarn", 0))
        rollup["catalogTriageFail"] += int(summary.get("triageFail", 0))


def _check(kind: str, count: int, count_key: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "status": "fail" if count else "pass",
        count_key: count,
    }


def _bundle_catalog_check(summary: dict[str, Any]) -> dict[str, Any]:
    failed_bundles = int(summary.get("failedBundles", 0))
    failures = int(summary.get("failures", 0))
    triage_fail = int(summary.get("triageFail", 0))
    triage_warn = int(summary.get("triageWarn", 0))
    status = "pass"
    if failed_bundles or failures or triage_fail:
        status = "fail"
    elif triage_warn:
        status = "warn"
    return {
        "kind": "bundle-catalog",
        "status": status,
        "failedBundles": failed_bundles,
        "failures": failures,
        "triageWarn": triage_warn,
        "triageFail": triage_fail,
    }


def _status(rollup: dict[str, int]) -> str:
    if (
        rollup["advisoryFindings"]
        or rollup["deniedLicenseFindings"]
        or rollup["catalogFailedBundles"]
        or rollup["catalogFailures"]
        or rollup["catalogTriageFail"]
    ):
        return "fail"
    if (
        rollup["missingLicenses"]
        or rollup["npmDuplicatePackageNames"]
        or rollup["npmNestedResolutionConflicts"]
        or rollup["npmUnresolvedDependencies"]
        or rollup["catalogTriageWarn"]
    ):
        return "warn"
    return "pass"


def _advisory_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings = report.get("findings", [])
    if not isinstance(findings, list):
        return []
    rows = []
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        advisory = finding.get("advisory", {})
        advisory = advisory if isinstance(advisory, dict) else {}
        rows.append(
            {
                "id": advisory.get("id"),
                "severity": advisory.get("severity"),
                "package": finding.get("package"),
                "summary": advisory.get("summary"),
            }
        )
    return rows


def _license_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings = report.get("findings", [])
    if not isinstance(findings, list):
        return []
    return [
        {
            "package": finding.get("package"),
            "license": finding.get("license"),
            "matchedDeniedLicenses": finding.get("matchedDeniedLicenses", []),
        }
        for finding in findings
        if isinstance(finding, dict)
    ]


def _npm_findings(
    report: dict[str, Any],
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = []
    for key in (
        "duplicatePackageNames",
        "nestedResolutionConflicts",
        "unresolvedDependencies",
    ):
        count = int(summary.get(key, 0))
        if count:
            rows.append({"kind": key, "count": count, "root": report.get("root")})
    return rows


def _bundle_catalog_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    bundles = report.get("bundles", [])
    if not isinstance(bundles, list):
        return []
    rows = []
    for bundle in bundles:
        if not isinstance(bundle, dict):
            continue
        if (
            bundle.get("ok") is True
            and bundle.get("triageStatus") not in {"warn", "fail"}
        ):
            continue
        rows.append(
            {
                "path": bundle.get("path"),
                "sourceKind": bundle.get("sourceKind"),
                "ok": bundle.get("ok"),
                "failureCount": bundle.get("failureCount"),
                "failureCodes": bundle.get("failureCodes", []),
                "triageStatus": bundle.get("triageStatus"),
            }
        )
    return rows


def _bundle_source_kind(manifest: dict[str, Any]) -> str:
    bundle = manifest.get("bundle", {})
    if isinstance(bundle, dict):
        return str(bundle.get("sourceKind", ""))
    return ""
