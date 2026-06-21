"""Aggregate EDGP report bundles into one machine-readable triage summary."""

from __future__ import annotations

import json
import tarfile
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
    diff_policy_findings = []
    diff_tree_policy_findings = []
    real_data_coverage_findings = []
    real_data_coverage_diff_findings = []
    real_data_replacement_plan_findings = []
    real_data_replacement_plan_diff_findings = []

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
        elif schema == "edgp.graph.diff.v1":
            policy_check = _diff_policy_check(report)
            if policy_check is not None:
                checks.append(policy_check)
                diff_policy_findings.extend(_diff_policy_findings(report))
        elif schema == "edgp.graph.diff_tree.v1":
            policy_check = _diff_tree_policy_check(report)
            if policy_check is not None:
                checks.append(policy_check)
                diff_tree_policy_findings.extend(_diff_tree_policy_findings(report))
        elif schema == "edgp.real_data.coverage.v1":
            policy_check = _real_data_coverage_policy_check(report)
            if policy_check is not None:
                checks.append(policy_check)
                real_data_coverage_findings.extend(
                    _real_data_coverage_policy_findings(report)
                )
        elif schema == "edgp.real_data.coverage_diff.v1":
            policy_check = _real_data_coverage_diff_policy_check(report)
            if policy_check is not None:
                checks.append(policy_check)
                real_data_coverage_diff_findings.extend(
                    _real_data_coverage_diff_policy_findings(report)
                )
        elif schema == "edgp.real_data.replacement_plan.v1":
            policy_check = _real_data_replacement_plan_policy_check(report)
            if policy_check is not None:
                checks.append(policy_check)
                real_data_replacement_plan_findings.extend(
                    _real_data_replacement_plan_policy_findings(report)
                )
        elif schema == "edgp.real_data.replacement_plan_diff.v1":
            policy_check = _real_data_replacement_plan_diff_policy_check(report)
            if policy_check is not None:
                checks.append(policy_check)
                real_data_replacement_plan_diff_findings.extend(
                    _real_data_replacement_plan_diff_policy_findings(report)
                )
        elif schema == "edgp.performance.report.v1":
            _accumulate_performance_report(rollup, summary)
        elif schema == "edgp.parallel.query.report.v1":
            _accumulate_parallel_query_report(rollup, report, summary)
        elif schema == "edgp.bundle.catalog.v1":
            checks.append(_bundle_catalog_check(summary))
            bundle_catalog_findings.extend(_bundle_catalog_findings(report))

    status = _status(rollup)
    top_findings = {
        "advisories": advisory_findings[:10],
        "licenses": license_findings[:10],
        "npm": npm_findings[:10],
        "bundleCatalog": bundle_catalog_findings[:10],
        "graphDiffPolicies": diff_policy_findings[:10],
        "diffTreePolicies": diff_tree_policy_findings[:10],
    }
    if real_data_coverage_findings:
        top_findings["realDataCoverage"] = real_data_coverage_findings[:10]
    if real_data_coverage_diff_findings:
        top_findings["realDataCoverageDiff"] = real_data_coverage_diff_findings[:10]
    if real_data_replacement_plan_findings:
        top_findings["realDataReplacementPlan"] = (
            real_data_replacement_plan_findings[:10]
        )
    if real_data_replacement_plan_diff_findings:
        top_findings["realDataReplacementPlanDiff"] = (
            real_data_replacement_plan_diff_findings[:10]
        )
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
        "topFindings": top_findings,
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
    if _is_report_bundle_archive(bundle_dir):
        return build_triage_summary_from_bundle_archive(
            bundle_dir,
            manifest_name=manifest_name,
        )

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


def build_triage_summary_from_bundle_archive(
    archive_path: Path,
    *,
    manifest_name: str = "manifest.json",
) -> dict[str, Any]:
    """Load report sources listed in a verified deterministic bundle archive."""

    from src.output.report_bundle import verify_report_bundle_archive

    archive_path = archive_path.resolve()
    archive_report = verify_report_bundle_archive(
        archive_path,
        manifest_name=manifest_name,
    )
    if archive_report.get("ok") is not True:
        raise ValueError(_archive_failure_message(archive_report))

    manifest = _load_archive_manifest(archive_path, manifest_name=manifest_name)
    archive_source = _archive_source(
        archive_path,
        archive_report=archive_report,
        manifest=manifest,
        manifest_name=manifest_name,
    )
    embedded_summary = _load_archive_triage_summary(archive_path, manifest)
    if embedded_summary is not None:
        embedded_summary["source"] = archive_source
        embedded_summary["bundle"] = _bundle_summary(manifest)
        return embedded_summary

    manifest, reports = _load_archive_bundle_reports(
        archive_path,
        manifest_name=manifest_name,
    )
    summary = build_triage_summary_report(
        reports,
        source={**archive_source, "reports": len(reports)},
    )
    summary["bundle"] = _bundle_summary(manifest, report_count=len(reports))
    return summary


def _is_report_bundle_archive(path: Path) -> bool:
    suffixes = path.suffixes
    return path.suffix == ".tgz" or suffixes[-2:] == [".tar", ".gz"]


def _load_archive_bundle_reports(
    archive_path: Path,
    *,
    manifest_name: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with tarfile.open(archive_path, "r:gz") as archive:
        manifest = _load_archive_json_member(archive, manifest_name)
        reports = manifest.get("reports", [])
        if not isinstance(reports, list):
            raise ValueError("Bundle manifest reports must be a list")
        report_payloads = []
        for report in reports:
            if not isinstance(report, dict):
                continue
            source = report.get("source")
            if isinstance(source, str) and source:
                report_payloads.append(_load_archive_json_member(archive, source))
    return manifest, report_payloads


def _load_archive_manifest(archive_path: Path, *, manifest_name: str) -> dict[str, Any]:
    with tarfile.open(archive_path, "r:gz") as archive:
        return _load_archive_json_member(archive, manifest_name)


def _load_archive_triage_summary(
    archive_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any] | None:
    triage_summary = manifest.get("triageSummary")
    if not isinstance(triage_summary, dict):
        return None
    source = triage_summary.get("source")
    if not isinstance(source, str) or not source:
        return None
    with tarfile.open(archive_path, "r:gz") as archive:
        return _load_archive_json_member(archive, source)


def _load_archive_json_member(
    archive: tarfile.TarFile,
    member_name: str,
) -> dict[str, Any]:
    if not _is_bundle_member_label(member_name):
        raise ValueError(f"Archive member path must be bundle-local: {member_name}")
    try:
        member = archive.getmember(member_name)
    except KeyError as error:
        raise ValueError(f"Archive member is missing: {member_name}") from error
    if not member.isfile():
        raise ValueError(f"Archive member is not a regular file: {member_name}")
    source = archive.extractfile(member)
    if source is None:
        raise ValueError(f"Archive member is unreadable: {member_name}")
    payload = json.loads(source.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Report must be a JSON object: {member_name}")
    return payload


def _archive_source(
    archive_path: Path,
    *,
    archive_report: dict[str, Any],
    manifest: dict[str, Any],
    manifest_name: str,
) -> dict[str, Any]:
    return {
        "kind": "bundle-archive",
        "archive": str(archive_path),
        "manifest": manifest_name,
        "archiveSha256": archive_report.get("archiveSha256"),
        "bundleSha256": manifest.get("bundleSha256"),
        "reports": int(manifest.get("reportCount", 0) or 0),
    }


def _bundle_summary(
    manifest: dict[str, Any],
    *,
    report_count: int | None = None,
) -> dict[str, Any]:
    return {
        "schema": manifest.get("schema"),
        "sourceKind": _bundle_source_kind(manifest),
        "reportCount": manifest.get(
            "reportCount",
            0 if report_count is None else report_count,
        ),
    }


def _is_bundle_member_label(label: str) -> bool:
    member_path = Path(label)
    return bool(label) and not member_path.is_absolute() and ".." not in member_path.parts


def _archive_failure_message(archive_report: dict[str, Any]) -> str:
    verification = archive_report.get("verification", {})
    failures = verification.get("failures", []) if isinstance(verification, dict) else []
    if isinstance(failures, list) and failures and isinstance(failures[0], dict):
        code = failures[0].get("code", "unknown")
        message = failures[0].get("message", "")
        return f"Bundle archive verification failed: {code}: {message}"
    return "Bundle archive verification failed"


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Report must be a JSON object: {path}")
    return payload


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary")
    if isinstance(summary, dict):
        payload_summary = dict(summary)
        if report.get("schema") == "edgp.graph.diff.v1":
            payload_summary["policyFailures"] = _diff_policy_failure_count(report)
        if report.get("schema") == "edgp.graph.diff_tree.v1":
            payload_summary["policyFailures"] = _diff_tree_policy_failure_count(report)
        if report.get("schema") == "edgp.real_data.coverage.v1":
            payload_summary["policyFailures"] = (
                _real_data_coverage_policy_failure_count(report)
            )
        if report.get("schema") == "edgp.real_data.coverage_diff.v1":
            payload_summary["policyFailures"] = (
                _real_data_coverage_diff_policy_failure_count(report)
            )
        if report.get("schema") == "edgp.real_data.replacement_plan.v1":
            payload_summary["policyFailures"] = (
                _real_data_replacement_plan_policy_failure_count(report)
            )
        if report.get("schema") == "edgp.real_data.replacement_plan_diff.v1":
            payload_summary["policyFailures"] = (
                _real_data_replacement_plan_diff_policy_failure_count(report)
            )
        return payload_summary
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
        "graphDiffReports": 0,
        "graphDiffPolicyFailures": 0,
        "diffTreeReports": 0,
        "diffTreePolicyFailures": 0,
        "diffTreeNodeChurn": 0,
        "diffTreeEdgeChurn": 0,
        "diffTreeNetNodeDelta": 0,
        "diffTreeNetEdgeDelta": 0,
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
    elif schema == "edgp.graph.diff.v1":
        rollup["graphDiffReports"] += 1
        rollup["graphDiffPolicyFailures"] += int(
            summary.get("policyFailures", 0)
        )
    elif schema == "edgp.graph.diff_tree.v1":
        rollup["diffTreeReports"] += 1
        rollup["diffTreePolicyFailures"] += int(
            summary.get("policyFailures", 0)
        )
        rollup["diffTreeNodeChurn"] += int(summary.get("nodeChurn", 0) or 0)
        rollup["diffTreeEdgeChurn"] += int(summary.get("edgeChurn", 0) or 0)
        rollup["diffTreeNetNodeDelta"] += int(summary.get("nodeDelta", 0) or 0)
        rollup["diffTreeNetEdgeDelta"] += int(summary.get("edgeDelta", 0) or 0)
    elif schema == "edgp.real_data.coverage.v1":
        rollup["realDataCoverageReports"] = (
            rollup.get("realDataCoverageReports", 0) + 1
        )
        rollup["realDataCoveragePolicyFailures"] = (
            rollup.get("realDataCoveragePolicyFailures", 0)
            + int(summary.get("policyFailures", 0))
        )
    elif schema == "edgp.real_data.coverage_diff.v1":
        rollup["realDataCoverageDiffReports"] = (
            rollup.get("realDataCoverageDiffReports", 0) + 1
        )
        rollup["realDataCoverageDiffPolicyFailures"] = (
            rollup.get("realDataCoverageDiffPolicyFailures", 0)
            + int(summary.get("policyFailures", 0))
        )
    elif schema == "edgp.real_data.replacement_plan.v1":
        rollup["realDataReplacementPlanReports"] = (
            rollup.get("realDataReplacementPlanReports", 0) + 1
        )
        rollup["realDataReplacementPlanPolicyFailures"] = (
            rollup.get("realDataReplacementPlanPolicyFailures", 0)
            + int(summary.get("policyFailures", 0))
        )
    elif schema == "edgp.real_data.replacement_plan_diff.v1":
        rollup["realDataReplacementPlanDiffReports"] = (
            rollup.get("realDataReplacementPlanDiffReports", 0) + 1
        )
        rollup["realDataReplacementPlanDiffPolicyFailures"] = (
            rollup.get("realDataReplacementPlanDiffPolicyFailures", 0)
            + int(summary.get("policyFailures", 0))
        )
    elif schema == "edgp.bundle.catalog.v1":
        rollup["bundleCatalogReports"] += 1
        rollup["catalogBundles"] += int(summary.get("bundles", 0))
        rollup["catalogFailedBundles"] += int(summary.get("failedBundles", 0))
        rollup["catalogFailures"] += int(summary.get("failures", 0))
        rollup["parallelQueryReports"] = rollup.get("parallelQueryReports", 0) + int(
            summary.get("parallelQueryReports", 0) or 0
        )
        rollup["parallelQueryQueries"] = rollup.get("parallelQueryQueries", 0) + int(
            summary.get("parallelQueryQueries", 0) or 0
        )
        rollup["parallelQueryResultNodes"] = (
            rollup.get("parallelQueryResultNodes", 0)
            + int(summary.get("parallelQueryResultNodes", 0) or 0)
        )
        rollup["parallelQueryMemoryMappedReports"] = (
            rollup.get("parallelQueryMemoryMappedReports", 0)
            + int(summary.get("parallelQueryMemoryMappedReports", 0) or 0)
        )
        rollup["graphDiffPolicyFailures"] += int(
            summary.get("graphDiffPolicyFailures", 0)
        )
        rollup["diffTreePolicyFailures"] += int(
            summary.get("diffTreePolicyFailures", 0)
        )
        rollup["diffTreeNodeChurn"] += int(
            summary.get("diffTreeNodeChurn", 0) or 0
        )
        rollup["diffTreeEdgeChurn"] += int(
            summary.get("diffTreeEdgeChurn", 0) or 0
        )
        rollup["diffTreeNetNodeDelta"] += int(
            summary.get("diffTreeNetNodeDelta", 0) or 0
        )
        rollup["diffTreeNetEdgeDelta"] += int(
            summary.get("diffTreeNetEdgeDelta", 0) or 0
        )
        rollup["realDataCoveragePolicyFailures"] = (
            rollup.get("realDataCoveragePolicyFailures", 0)
            + int(summary.get("realDataCoveragePolicyFailures", 0))
        )
        rollup["realDataCoverageDiffPolicyFailures"] = (
            rollup.get("realDataCoverageDiffPolicyFailures", 0)
            + int(summary.get("realDataCoverageDiffPolicyFailures", 0))
        )
        rollup["realDataReplacementPlanPolicyFailures"] = (
            rollup.get("realDataReplacementPlanPolicyFailures", 0)
            + int(summary.get("realDataReplacementPlanPolicyFailures", 0))
        )
        rollup["realDataReplacementPlanDiffPolicyFailures"] = (
            rollup.get("realDataReplacementPlanDiffPolicyFailures", 0)
            + int(summary.get("realDataReplacementPlanDiffPolicyFailures", 0))
        )
        rollup["catalogTriageWarn"] += int(summary.get("triageWarn", 0))
        rollup["catalogTriageFail"] += int(summary.get("triageFail", 0))


def _accumulate_performance_report(
    rollup: dict[str, int],
    summary: dict[str, Any],
) -> None:
    rollup["performanceReports"] = rollup.get("performanceReports", 0) + 1
    rollup["performanceScenarios"] = rollup.get("performanceScenarios", 0) + int(
        summary.get("scenarios", 0) or 0
    )
    rollup["performanceMaxNodes"] = max(
        rollup.get("performanceMaxNodes", 0),
        int(summary.get("maxNodes", 0) or 0),
    )
    rollup["performanceMaxEdges"] = max(
        rollup.get("performanceMaxEdges", 0),
        int(summary.get("maxEdges", 0) or 0),
    )
    rollup["performanceContiguousReports"] = (
        rollup.get("performanceContiguousReports", 0)
        + (1 if bool(summary.get("allContiguous")) else 0)
    )


def _accumulate_parallel_query_report(
    rollup: dict[str, int],
    report: dict[str, Any],
    summary: dict[str, Any],
) -> None:
    rollup["parallelQueryReports"] = rollup.get("parallelQueryReports", 0) + 1
    rollup["parallelQueryQueries"] = rollup.get("parallelQueryQueries", 0) + int(
        summary.get("queries", 0) or 0
    )
    rollup["parallelQueryResultNodes"] = (
        rollup.get("parallelQueryResultNodes", 0)
        + _parallel_query_result_nodes(report)
    )
    rollup["parallelQueryMemoryMappedReports"] = (
        rollup.get("parallelQueryMemoryMappedReports", 0)
        + (1 if bool(summary.get("memoryMapped")) else 0)
    )


def _parallel_query_result_nodes(report: dict[str, Any]) -> int:
    results = report.get("results", [])
    if not isinstance(results, list):
        return 0
    return sum(
        int(result.get("count", 0) or 0)
        for result in results
        if isinstance(result, dict)
    )


def _check(kind: str, count: int, count_key: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "status": "fail" if count else "pass",
        count_key: count,
    }


def _bundle_catalog_check(summary: dict[str, Any]) -> dict[str, Any]:
    failed_bundles = int(summary.get("failedBundles", 0))
    failures = int(summary.get("failures", 0))
    real_data_policy_failures = int(
        summary.get("realDataCoveragePolicyFailures", 0) or 0
    )
    real_data_diff_policy_failures = int(
        summary.get("realDataCoverageDiffPolicyFailures", 0) or 0
    )
    replacement_plan_policy_failures = int(
        summary.get("realDataReplacementPlanPolicyFailures", 0) or 0
    )
    replacement_plan_diff_policy_failures = int(
        summary.get("realDataReplacementPlanDiffPolicyFailures", 0) or 0
    )
    triage_fail = int(summary.get("triageFail", 0))
    triage_warn = int(summary.get("triageWarn", 0))
    status = "pass"
    if (
        failed_bundles
        or failures
        or triage_fail
        or real_data_policy_failures
        or real_data_diff_policy_failures
        or replacement_plan_policy_failures
        or replacement_plan_diff_policy_failures
    ):
        status = "fail"
    elif triage_warn:
        status = "warn"
    check = {
        "kind": "bundle-catalog",
        "status": status,
        "failedBundles": failed_bundles,
        "failures": failures,
        "graphDiffPolicyFailures": int(
            summary.get("graphDiffPolicyFailures", 0) or 0
        ),
        "diffTreePolicyFailures": int(
            summary.get("diffTreePolicyFailures", 0) or 0
        ),
        "realDataCoveragePolicyFailures": int(
            summary.get("realDataCoveragePolicyFailures", 0) or 0
        ),
        "realDataCoverageDiffPolicyFailures": real_data_diff_policy_failures,
        "realDataReplacementPlanPolicyFailures": replacement_plan_policy_failures,
        "realDataReplacementPlanDiffPolicyFailures": (
            replacement_plan_diff_policy_failures
        ),
        "triageWarn": triage_warn,
        "triageFail": triage_fail,
    }
    parallel_query_reports = int(summary.get("parallelQueryReports", 0) or 0)
    if parallel_query_reports:
        check.update(
            {
                "parallelQueryReports": parallel_query_reports,
                "parallelQueryQueries": int(
                    summary.get("parallelQueryQueries", 0) or 0
                ),
                "parallelQueryResultNodes": int(
                    summary.get("parallelQueryResultNodes", 0) or 0
                ),
                "parallelQueryMemoryMappedReports": int(
                    summary.get("parallelQueryMemoryMappedReports", 0) or 0
                ),
            }
        )
    return check


def _diff_policy_check(report: dict[str, Any]) -> dict[str, Any] | None:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return None
    status = str(policy.get("status") or "pass")
    matched_changes = _string_list(policy.get("matchedChanges"))
    return {
        "kind": "graph-diff-policy",
        "status": "fail" if status == "fail" else "pass",
        "failOnChange": _string_list(policy.get("failOnChange")),
        "matchedChanges": matched_changes,
        "failOnKind": _string_list(policy.get("failOnKind")),
        "matchedKinds": _string_list(policy.get("matchedKinds")),
        "exitCode": int(policy.get("exitCode", 0) or 0),
    }


def _diff_tree_policy_check(report: dict[str, Any]) -> dict[str, Any] | None:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return None
    status = str(policy.get("status") or "pass")
    matched_kinds = _string_list(policy.get("matchedKinds"))
    return {
        "kind": "diff-tree-policy",
        "status": "fail" if status == "fail" else "pass",
        "failOnKind": _string_list(policy.get("failOnKind")),
        "matchedKinds": matched_kinds,
        "exitCode": int(policy.get("exitCode", 0) or 0),
    }


def _real_data_coverage_policy_check(report: dict[str, Any]) -> dict[str, Any] | None:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return None
    status = str(policy.get("status") or "pass")
    return {
        "kind": "real-data-coverage-policy",
        "status": "fail" if status == "fail" else "pass",
        "minPublicEvidenceCoveragePercent": policy.get(
            "minPublicEvidenceCoveragePercent"
        ),
        "failOnPriority": policy.get("failOnPriority"),
        "matchedReplacementGroups": int(
            policy.get("matchedReplacementGroups", 0) or 0
        ),
        "exitCode": int(policy.get("exitCode", 0) or 0),
    }


def _real_data_coverage_diff_policy_check(
    report: dict[str, Any],
) -> dict[str, Any] | None:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return None
    status = str(policy.get("status") or "pass")
    return {
        "kind": "real-data-coverage-diff-policy",
        "status": "fail" if status == "fail" else "pass",
        "failOnRegression": bool(policy.get("failOnRegression", False)),
        "exitCode": int(policy.get("exitCode", 0) or 0),
    }


def _real_data_replacement_plan_policy_check(
    report: dict[str, Any],
) -> dict[str, Any] | None:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return None
    status = str(policy.get("status") or "pass")
    return {
        "kind": "real-data-replacement-plan-policy",
        "status": "fail" if status == "fail" else "pass",
        "failOnPriority": policy.get("failOnPriority"),
        "matchedReplacementGroups": int(
            policy.get("matchedReplacementGroups", 0) or 0
        ),
        "exitCode": int(policy.get("exitCode", 0) or 0),
    }


def _real_data_replacement_plan_diff_policy_check(
    report: dict[str, Any],
) -> dict[str, Any] | None:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return None
    status = str(policy.get("status") or "pass")
    return {
        "kind": "real-data-replacement-plan-diff-policy",
        "status": "fail" if status == "fail" else "pass",
        "failOnRegression": bool(policy.get("failOnRegression", False)),
        "exitCode": int(policy.get("exitCode", 0) or 0),
    }


def _diff_policy_failure_count(report: dict[str, Any]) -> int:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return 0
    return 1 if policy.get("status") == "fail" else 0


def _diff_tree_policy_failure_count(report: dict[str, Any]) -> int:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return 0
    return 1 if policy.get("status") == "fail" else 0


def _real_data_coverage_policy_failure_count(report: dict[str, Any]) -> int:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return 0
    return 1 if policy.get("status") == "fail" else 0


def _real_data_coverage_diff_policy_failure_count(report: dict[str, Any]) -> int:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return 0
    return 1 if policy.get("status") == "fail" else 0


def _real_data_replacement_plan_policy_failure_count(report: dict[str, Any]) -> int:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return 0
    return 1 if policy.get("status") == "fail" else 0


def _real_data_replacement_plan_diff_policy_failure_count(
    report: dict[str, Any],
) -> int:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return 0
    return 1 if policy.get("status") == "fail" else 0


def _status(rollup: dict[str, int]) -> str:
    if (
        rollup["advisoryFindings"]
        or rollup["deniedLicenseFindings"]
        or rollup["graphDiffPolicyFailures"]
        or rollup["diffTreePolicyFailures"]
        or rollup.get("realDataCoveragePolicyFailures", 0)
        or rollup.get("realDataCoverageDiffPolicyFailures", 0)
        or rollup.get("realDataReplacementPlanPolicyFailures", 0)
        or rollup.get("realDataReplacementPlanDiffPolicyFailures", 0)
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


def _diff_policy_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    policy = report.get("policy")
    if not isinstance(policy, dict) or policy.get("status") != "fail":
        return []
    return [
        {
            "leftRoot": report.get("leftRoot"),
            "rightRoot": report.get("rightRoot"),
            "failOnChange": _string_list(policy.get("failOnChange")),
            "matchedChanges": _string_list(policy.get("matchedChanges")),
            "failOnKind": _string_list(policy.get("failOnKind")),
            "matchedKinds": _string_list(policy.get("matchedKinds")),
            "exitCode": int(policy.get("exitCode", 0) or 0),
        }
    ]


def _diff_tree_policy_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    policy = report.get("policy")
    if not isinstance(policy, dict) or policy.get("status") != "fail":
        return []
    return [
        {
            "selector": report.get("selector"),
            "direction": report.get("direction"),
            "depth": report.get("depth"),
            "failOnKind": _string_list(policy.get("failOnKind")),
            "matchedKinds": _string_list(policy.get("matchedKinds")),
            "exitCode": int(policy.get("exitCode", 0) or 0),
        }
    ]


def _real_data_coverage_policy_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    policy = report.get("policy")
    if not isinstance(policy, dict) or policy.get("status") != "fail":
        return []
    failures = policy.get("failures", [])
    if not isinstance(failures, list):
        failures = []
    return [
        {
            "fixtureRoot": report.get("fixtureRoot"),
            "minPublicEvidenceCoveragePercent": policy.get(
                "minPublicEvidenceCoveragePercent"
            ),
            "failOnPriority": policy.get("failOnPriority"),
            "matchedReplacementGroups": policy.get("matchedReplacementGroups", 0),
            "failures": failures,
            "exitCode": int(policy.get("exitCode", 0) or 0),
        }
    ]


def _real_data_coverage_diff_policy_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    policy = report.get("policy")
    if not isinstance(policy, dict) or policy.get("status") != "fail":
        return []
    failures = policy.get("failures", [])
    if not isinstance(failures, list):
        failures = []
    return [
        {
            "left": report.get("left"),
            "right": report.get("right"),
            "failOnRegression": policy.get("failOnRegression"),
            "failures": failures,
            "exitCode": int(policy.get("exitCode", 0) or 0),
        }
    ]


def _real_data_replacement_plan_policy_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    policy = report.get("policy")
    if not isinstance(policy, dict) or policy.get("status") != "fail":
        return []
    failures = policy.get("failures", [])
    if not isinstance(failures, list):
        failures = []
    return [
        {
            "fixtureRoot": report.get("fixtureRoot"),
            "failOnPriority": policy.get("failOnPriority"),
            "matchedReplacementGroups": policy.get("matchedReplacementGroups", 0),
            "failures": failures,
            "exitCode": int(policy.get("exitCode", 0) or 0),
        }
    ]


def _real_data_replacement_plan_diff_policy_findings(
    report: dict[str, Any],
) -> list[dict[str, Any]]:
    policy = report.get("policy")
    if not isinstance(policy, dict) or policy.get("status") != "fail":
        return []
    failures = policy.get("failures", [])
    if not isinstance(failures, list):
        failures = []
    return [
        {
            "left": report.get("left"),
            "right": report.get("right"),
            "failOnRegression": policy.get("failOnRegression"),
            "failures": failures,
            "exitCode": int(policy.get("exitCode", 0) or 0),
        }
    ]


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


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
                "graphDiffPolicyFailures": bundle.get("graphDiffPolicyFailures", 0),
                "diffTreePolicyFailures": bundle.get("diffTreePolicyFailures", 0),
                "diffTreeNodeChurn": bundle.get("diffTreeNodeChurn", 0),
                "diffTreeEdgeChurn": bundle.get("diffTreeEdgeChurn", 0),
                "diffTreeNetNodeDelta": bundle.get("diffTreeNetNodeDelta", 0),
                "diffTreeNetEdgeDelta": bundle.get("diffTreeNetEdgeDelta", 0),
                "parallelQueryReports": bundle.get("parallelQueryReports", 0),
                "parallelQueryQueries": bundle.get("parallelQueryQueries", 0),
                "parallelQueryResultNodes": bundle.get(
                    "parallelQueryResultNodes",
                    0,
                ),
                "parallelQueryMemoryMappedReports": bundle.get(
                    "parallelQueryMemoryMappedReports",
                    0,
                ),
                "realDataCoveragePolicyFailures": bundle.get(
                    "realDataCoveragePolicyFailures",
                    0,
                ),
                "realDataCoverageDiffPolicyFailures": bundle.get(
                    "realDataCoverageDiffPolicyFailures",
                    0,
                ),
                "realDataReplacementPlanPolicyFailures": bundle.get(
                    "realDataReplacementPlanPolicyFailures",
                    0,
                ),
                "realDataReplacementPlanDiffPolicyFailures": bundle.get(
                    "realDataReplacementPlanDiffPolicyFailures",
                    0,
                ),
                "realDataCoverageFailureCodes": _string_list(
                    bundle.get("realDataCoverageFailureCodes")
                ),
                "realDataCoverageDiffFailureCodes": _string_list(
                    bundle.get("realDataCoverageDiffFailureCodes")
                ),
                "realDataReplacementPlanFailureCodes": _string_list(
                    bundle.get("realDataReplacementPlanFailureCodes")
                ),
                "realDataReplacementPlanDiffFailureCodes": _string_list(
                    bundle.get("realDataReplacementPlanDiffFailureCodes")
                ),
                "graphDiffFailOnChanges": _string_list(
                    bundle.get("graphDiffFailOnChanges")
                ),
                "graphDiffMatchedChanges": _string_list(
                    bundle.get("graphDiffMatchedChanges")
                ),
                "graphDiffFailOnKinds": _string_list(
                    bundle.get("graphDiffFailOnKinds")
                ),
                "graphDiffMatchedKinds": _string_list(
                    bundle.get("graphDiffMatchedKinds")
                ),
                "diffTreeFailOnKinds": _string_list(bundle.get("diffTreeFailOnKinds")),
                "diffTreeMatchedKinds": _string_list(
                    bundle.get("diffTreeMatchedKinds")
                ),
            }
        )
    return rows


def _bundle_source_kind(manifest: dict[str, Any]) -> str:
    bundle = manifest.get("bundle", {})
    if isinstance(bundle, dict):
        return str(bundle.get("sourceKind", ""))
    return ""
