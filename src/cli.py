"""Command-line entry points for resolving and exporting dependency graphs."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any, Sequence
from urllib.request import Request, urlopen

from src.albs_build_diff import build_albs_build_diff_report
from src.albs_build_timing import build_albs_build_timing_report
from src.albs_artifact_inventory import build_albs_artifact_inventory
from src.albs_log_intelligence import build_albs_log_intelligence_report
from src.albs_release_completeness import build_albs_release_completeness_report
from src.advisory_overlay import build_advisory_report, build_advisory_report_from_file
from src.adapters.albs import DEFAULT_ALBS_BASE_URL, AlbsBuildAdapter
from src.adapters.base import ResolvedProjectGraph
from src.adapters.cargo import CargoAdapter
from src.adapters.cyclonedx import CycloneDXAdapter
from src.adapters.dot import DotAdapter
from src.adapters.maven import MavenTreeAdapter
from src.adapters.npm import NpmAdapter
from src.adapters.poetry import PoetryAdapter
from src.adapters.rpm_repository import RpmRepositoryAdapter
from src.adapters.rpm_installed import InstalledRpmAdapter
from src.benchmark import run_synthetic_benchmark
from src.bundle_catalog import build_bundle_catalog_report
from src.core_graph.accelerators import accelerator_profile
from src.core_graph.artifacts import write_frozen_csr_artifact
from src.core_graph.parallel import run_parallel_reachability_queries
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.export_batch import (
    build_graph_export_batch_submission_plan,
    graph_from_snapshot,
    verify_graph_export_batch,
    verify_graph_export_batch_archive,
    write_graph_export_batch,
    write_graph_export_batch_archive,
)
from src.graph_diff import diff_snapshot_files, diff_tree_snapshot_files
from src.impact_report import build_impact_report
from src.libsolv_bridge import build_libsolv_bridge_report
from src.license_policy import build_license_report
from src.output.cypher_export import CypherExporter
from src.output.graph_bundle import write_graph_report_bundle
from src.output.html_report import write_report_file
from src.output.json_export import GraphJsonExporter
from src.output.report_bundle import (
    build_report_bundle_submission_plan,
    verify_report_bundle,
    verify_report_bundle_archive,
    write_report_bundle,
    write_report_bundle_archive,
)
from src.output.sbom_security import CycloneDXExporter
from src.performance_report import build_performance_report
from src.public_advisory_feed import build_public_advisory_feed_report
from src.query_report import build_query_report
from src.real_data_coverage import build_real_data_coverage_report
from src.real_data_coverage_diff import build_real_data_coverage_diff_report
from src.real_data_replacement_plan import build_real_data_replacement_plan_report
from src.real_data_replacement_plan_diff import (
    build_real_data_replacement_plan_diff_report,
)
from src.resolver.cdcl_engine import CDCLResolver
from src.resolver.registry_mock import RegistryMock
from src.rpm_albs_provenance import build_rpm_albs_provenance_report
from src.rpm_repository_diff import build_rpm_repository_diff_report
from src.rpm_repository_summary import build_rpm_repository_summary_report
from src.schema_validation import validate_target
from src.submission_plan_index import build_submission_plan_index
from src.triage_summary import (
    build_triage_summary_from_bundle,
    build_triage_summary_from_paths,
)
from scripts.generate_fixture_provenance import build_fixture_provenance
from scripts.generate_failure_example_index import (
    build_failure_example_filter_listing,
    build_failure_example_index,
)

DIFF_TREE_CHANGE_KINDS = (
    "added",
    "removed",
    "metadataChange",
    "replacement",
    "upgrade",
    "downgrade",
)

DIFF_CHANGE_KINDS = (
    "added-node",
    "removed-node",
    "added-edge",
    "removed-edge",
    "metadata-change",
)


def _demo_registry() -> RegistryMock:
    return RegistryMock.from_mapping(
        {
            "app": {
                "1.0.0": {
                    "dependencies": {
                        "addon": ">=1.0.0,<3.0.0",
                        "lib": ">=1.0.0,<3.0.0",
                    }
                },
            },
            "addon": {
                "2.0.0": {"dependencies": {"core": ">=3.0.0,<4.0.0"}},
                "1.0.0": {"dependencies": {"core": ">=1.0.0,<2.0.0"}},
            },
            "lib": {
                "2.0.0": {"dependencies": {"core": ">=2.0.0,<3.0.0"}},
                "1.0.0": {"dependencies": {"core": ">=1.0.0,<2.0.0"}},
            },
            "core": {
                "3.1.0": {"dependencies": {}},
                "2.5.0": {"dependencies": {}},
                "1.5.0": {"dependencies": {}},
            },
        }
    )


def _load_registry(path: Path | None) -> RegistryMock:
    if path is None:
        return _demo_registry()
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return RegistryMock.from_mapping(payload)


def _export(
    format_name: str,
    graph,
    root: str | None,
    ecosystem: str = "generic",
) -> str:
    if format_name == "cypher":
        return CypherExporter.export_to_cypher(graph)
    if format_name == "cyclonedx":
        return CycloneDXExporter.export_to_json(graph, root=root, ecosystem=ecosystem)
    if format_name == "json":
        return GraphJsonExporter.export_to_json(graph, root=root, ecosystem=ecosystem)
    raise ValueError(f"Unsupported output format: {format_name}")


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)


def _format_verification_report(report: dict[str, Any]) -> str:
    status = "OK" if report.get("ok") else "FAIL"
    summary = report.get("summary", {})
    reports = summary.get("reports", 0) if isinstance(summary, dict) else 0
    failures = summary.get("failures", 0) if isinstance(summary, dict) else 0
    parts = [
        status,
        f"reports={reports}",
        f"failures={failures}",
    ]
    bundle_sha = report.get("bundleSha256")
    if isinstance(bundle_sha, str) and bundle_sha:
        parts.append(f"bundleSha256={bundle_sha}")
    failure_list = report.get("failures", [])
    if isinstance(failure_list, list) and failure_list:
        first_failure = failure_list[0]
        if isinstance(first_failure, dict):
            parts.append(f"firstFailure={first_failure.get('code', 'unknown')}")
    return " ".join(parts)


def _format_bundle_archive_report(report: dict[str, Any]) -> str:
    status = "OK" if report.get("ok") else "FAIL"
    summary = report.get("summary", {})
    files = summary.get("files", 0) if isinstance(summary, dict) else 0
    bytes_written = summary.get("bytes", 0) if isinstance(summary, dict) else 0
    failures = (
        summary.get("verificationFailures", 0) if isinstance(summary, dict) else 0
    )
    parts = [
        status,
        f"files={files}",
        f"bytes={bytes_written}",
        f"verificationFailures={failures}",
    ]
    bundle_sha = report.get("bundleSha256")
    if isinstance(bundle_sha, str) and bundle_sha:
        parts.append(f"bundleSha256={bundle_sha}")
    archive_sha = report.get("archiveSha256")
    if isinstance(archive_sha, str) and archive_sha:
        parts.append(f"archiveSha256={archive_sha}")
    return " ".join(parts)


def _format_export_batch_verification_report(report: dict[str, Any]) -> str:
    status = "OK" if report.get("ok") else "FAIL"
    summary = report.get("summary", {})
    exports = summary.get("exports", 0) if isinstance(summary, dict) else 0
    bytes_written = summary.get("bytes", 0) if isinstance(summary, dict) else 0
    failures = summary.get("failures", 0) if isinstance(summary, dict) else 0
    parts = [
        status,
        f"exports={exports}",
        f"bytes={bytes_written}",
        f"failures={failures}",
    ]
    manifest_sha = report.get("manifestSha256")
    if isinstance(manifest_sha, str) and manifest_sha:
        parts.append(f"manifestSha256={manifest_sha}")
    failure_list = report.get("failures", [])
    if isinstance(failure_list, list) and failure_list:
        first_failure = failure_list[0]
        if isinstance(first_failure, dict):
            parts.append(f"firstFailure={first_failure.get('code', 'unknown')}")
    return " ".join(parts)


def _format_export_batch_archive_report(report: dict[str, Any]) -> str:
    status = "OK" if report.get("ok") else "FAIL"
    summary = report.get("summary", {})
    files = summary.get("files", 0) if isinstance(summary, dict) else 0
    bytes_written = summary.get("bytes", 0) if isinstance(summary, dict) else 0
    failures = (
        summary.get("verificationFailures", 0) if isinstance(summary, dict) else 0
    )
    parts = [
        status,
        f"files={files}",
        f"bytes={bytes_written}",
        f"verificationFailures={failures}",
    ]
    manifest_sha = report.get("manifestSha256")
    if isinstance(manifest_sha, str) and manifest_sha:
        parts.append(f"manifestSha256={manifest_sha}")
    archive_sha = report.get("archiveSha256")
    if isinstance(archive_sha, str) and archive_sha:
        parts.append(f"archiveSha256={archive_sha}")
    return " ".join(parts)


def _format_export_batch_submission_plan(report: dict[str, Any]) -> str:
    status = "OK" if report.get("ok") else "FAIL"
    summary = report.get("summary", {})
    artifacts = summary.get("artifacts", 0) if isinstance(summary, dict) else 0
    bytes_written = summary.get("bytes", 0) if isinstance(summary, dict) else 0
    failures = summary.get("failures", 0) if isinstance(summary, dict) else 0
    target = report.get("target", {})
    target_kind = target.get("kind", "unknown") if isinstance(target, dict) else "unknown"
    parts = [
        status,
        f"target={target_kind}",
        f"artifacts={artifacts}",
        f"bytes={bytes_written}",
        f"failures={failures}",
    ]
    failure_list = report.get("failures", [])
    if isinstance(failure_list, list) and failure_list:
        first_failure = failure_list[0]
        if isinstance(first_failure, dict):
            parts.append(f"firstFailure={first_failure.get('code', 'unknown')}")
    return " ".join(parts)


def _format_report_bundle_submission_plan(report: dict[str, Any]) -> str:
    status = "OK" if report.get("ok") else "FAIL"
    summary = report.get("summary", {})
    artifacts = summary.get("artifacts", 0) if isinstance(summary, dict) else 0
    bytes_written = summary.get("bytes", 0) if isinstance(summary, dict) else 0
    failures = summary.get("failures", 0) if isinstance(summary, dict) else 0
    reports = summary.get("reports", 0) if isinstance(summary, dict) else 0
    target = report.get("target", {})
    target_kind = target.get("kind", "unknown") if isinstance(target, dict) else "unknown"
    parts = [
        status,
        f"target={target_kind}",
        f"reports={reports}",
        f"artifacts={artifacts}",
        f"bytes={bytes_written}",
        f"failures={failures}",
    ]
    triage_summary = report.get("triageSummary")
    if isinstance(triage_summary, dict):
        triage_status = triage_summary.get("status")
        if isinstance(triage_status, str) and triage_status:
            parts.append(f"triageStatus={triage_status}")
        summary = triage_summary.get("summary", {})
        if isinstance(summary, dict):
            failed_checks = int(summary.get("failedChecks", 0) or 0)
            if failed_checks:
                parts.append(f"failedChecks={failed_checks}")
            parts.extend(_policy_failure_text_parts(summary))
    failure_list = report.get("failures", [])
    if isinstance(failure_list, list) and failure_list:
        first_failure = failure_list[0]
        if isinstance(first_failure, dict):
            parts.append(f"firstFailure={first_failure.get('code', 'unknown')}")
    return " ".join(parts)


def _format_submission_plan_index(index: dict[str, Any]) -> str:
    status = "OK" if index.get("ok") else "FAIL"
    summary = index.get("summary", {})
    plans = summary.get("plans", 0) if isinstance(summary, dict) else 0
    failed_plans = summary.get("failedPlans", 0) if isinstance(summary, dict) else 0
    artifacts = summary.get("artifacts", 0) if isinstance(summary, dict) else 0
    bytes_written = summary.get("bytes", 0) if isinstance(summary, dict) else 0
    failures = summary.get("failures", 0) if isinstance(summary, dict) else 0
    triage_warn = (
        int(summary.get("triageWarn", 0) or 0) if isinstance(summary, dict) else 0
    )
    triage_fail = (
        int(summary.get("triageFail", 0) or 0) if isinstance(summary, dict) else 0
    )
    targets = summary.get("targets", []) if isinstance(summary, dict) else []
    target_text = (
        ",".join(str(target) for target in targets)
        if isinstance(targets, list)
        else ""
    )
    parts = [
        status,
        f"plans={plans}",
        f"failedPlans={failed_plans}",
        f"artifacts={artifacts}",
        f"bytes={bytes_written}",
        f"failures={failures}",
    ]
    if target_text:
        parts.append(f"targets={target_text}")
    if triage_warn or triage_fail:
        parts.append(f"triageWarn={triage_warn}")
        parts.append(f"triageFail={triage_fail}")
    failure_list = index.get("failures", [])
    if isinstance(failure_list, list) and failure_list:
        first_failure = failure_list[0]
        if isinstance(first_failure, dict):
            parts.append(f"firstFailure={first_failure.get('code', 'unknown')}")
    return " ".join(parts)


def _format_validation_report(report: dict[str, Any]) -> str:
    status = "OK" if report.get("ok") else "FAIL"
    summary = report.get("summary", {})
    failures = summary.get("failures", 0) if isinstance(summary, dict) else 0
    parts = [
        status,
        f"targetType={report.get('targetType', 'unknown')}",
        f"failures={failures}",
    ]
    contract = report.get("contract")
    if isinstance(contract, str) and contract:
        parts.append(f"contract={contract}")
    report_status = report.get("reportStatus")
    if isinstance(report_status, str) and report_status:
        parts.append(f"reportStatus={report_status}")
    report_summary = report.get("reportSummary")
    if isinstance(report_summary, dict):
        parts.extend(_policy_failure_text_parts(report_summary))
    triage_summary = report.get("triageSummary")
    if isinstance(triage_summary, dict):
        triage_status = triage_summary.get("status")
        if isinstance(triage_status, str) and triage_status:
            parts.append(f"triageStatus={triage_status}")
        summary = triage_summary.get("summary", {})
        if isinstance(summary, dict):
            parts.extend(_policy_failure_text_parts(summary))
    failure_list = report.get("failures", [])
    if isinstance(failure_list, list) and failure_list:
        first_failure = failure_list[0]
        if isinstance(first_failure, dict):
            parts.append(f"firstFailure={first_failure.get('code', 'unknown')}")
    return " ".join(parts)


def _policy_failure_text_parts(summary: dict[str, Any]) -> list[str]:
    graph_diff_policy_failures = int(
        summary.get("graphDiffPolicyFailures", 0) or 0
    )
    diff_tree_policy_failures = int(summary.get("diffTreePolicyFailures", 0) or 0)
    real_data_policy_failures = int(
        summary.get("realDataCoveragePolicyFailures", 0) or 0
    )
    real_data_diff_policy_failures = int(
        summary.get("realDataCoverageDiffPolicyFailures", 0) or 0
    )
    real_data_replacement_policy_failures = int(
        summary.get("realDataReplacementPlanPolicyFailures", 0) or 0
    )
    real_data_replacement_diff_policy_failures = int(
        summary.get("realDataReplacementPlanDiffPolicyFailures", 0) or 0
    )
    parts = []
    if graph_diff_policy_failures:
        parts.append(f"graphDiffPolicyFailures={graph_diff_policy_failures}")
    if diff_tree_policy_failures:
        parts.append(f"diffTreePolicyFailures={diff_tree_policy_failures}")
    if real_data_policy_failures:
        parts.append(f"realDataCoveragePolicyFailures={real_data_policy_failures}")
    if real_data_diff_policy_failures:
        parts.append(
            "realDataCoverageDiffPolicyFailures="
            f"{real_data_diff_policy_failures}"
        )
    if real_data_replacement_policy_failures:
        parts.append(
            "realDataReplacementPlanPolicyFailures="
            f"{real_data_replacement_policy_failures}"
        )
    if real_data_replacement_diff_policy_failures:
        parts.append(
            "realDataReplacementPlanDiffPolicyFailures="
            f"{real_data_replacement_diff_policy_failures}"
        )
    return parts


def _format_failure_example_index(index: dict[str, Any]) -> str:
    examples = index.get("examples", [])
    if not isinstance(examples, list):
        examples = []
    lines = [
        (
            f"OK examples={index.get('exampleCount', len(examples))} "
            f"schema={index.get('schema', 'unknown')}"
        )
    ]
    for entry in examples:
        if not isinstance(entry, dict):
            continue
        parts = [
            str(entry.get("id", "unknown")),
            f"targetType={entry.get('targetType', 'unknown')}",
            f"contract={entry.get('contract', 'unknown')}",
            (
                "failureCodes="
                f"{','.join(_string_list(entry.get('validationFailureCodes', [])))}"
            ),
        ]
        verifier_codes = _string_list(entry.get("verificationFailureCodes", []))
        if verifier_codes:
            parts.append(f"verifierCodes={','.join(verifier_codes)}")
        parts.append(f"target={entry.get('target', '')}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _format_failure_example_filter_summary(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            (
                f"OK examples={summary.get('exampleCount', 0)} "
                f"schema={summary.get('schema', 'unknown')}"
            ),
            f"ids={','.join(_string_list(summary.get('ids', [])))}",
            f"contracts={','.join(_string_list(summary.get('contracts', [])))}",
            f"targetTypes={','.join(_string_list(summary.get('targetTypes', [])))}",
            f"validationFailureCodes={','.join(_string_list(summary.get('validationFailureCodes', [])))}",
            f"verificationFailureCodes={','.join(_string_list(summary.get('verificationFailureCodes', [])))}",
        ]
    )


def _filter_failure_example_index(
    index: dict[str, Any],
    *,
    ids: Sequence[str],
    codes: Sequence[str],
    contracts: Sequence[str],
    target_types: Sequence[str],
) -> dict[str, Any]:
    wanted_ids = {id_value for id_value in ids if id_value}
    wanted_codes = {code for code in codes if code}
    wanted_contracts = {contract for contract in contracts if contract}
    wanted_target_types = {target_type for target_type in target_types if target_type}
    if (
        not wanted_ids
        and not wanted_codes
        and not wanted_contracts
        and not wanted_target_types
    ):
        return index
    examples = index.get("examples", [])
    if not isinstance(examples, list):
        examples = []
    filtered_examples = [
        entry
        for entry in examples
        if isinstance(entry, dict)
        and _matches_failure_example_filters(
            entry,
            wanted_ids=wanted_ids,
            wanted_codes=wanted_codes,
            wanted_contracts=wanted_contracts,
            wanted_target_types=wanted_target_types,
        )
    ]
    filtered = dict(index)
    filtered["exampleCount"] = len(filtered_examples)
    filtered["examples"] = filtered_examples
    return filtered


def _matches_failure_example_filters(
    entry: dict[str, Any],
    *,
    wanted_ids: set[str],
    wanted_codes: set[str],
    wanted_contracts: set[str],
    wanted_target_types: set[str],
) -> bool:
    if wanted_ids and entry.get("id") not in wanted_ids:
        return False
    if wanted_contracts and entry.get("contract") not in wanted_contracts:
        return False
    if wanted_target_types and entry.get("targetType") not in wanted_target_types:
        return False
    if not wanted_codes:
        return True
    entry_codes = set(_string_list(entry.get("validationFailureCodes", []))) | set(
        _string_list(entry.get("verificationFailureCodes", []))
    )
    return bool(wanted_codes & entry_codes)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def _dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _command_string(argv: list[str]) -> str:
    return shlex.join(["edgp", *argv])


def _write_npm_bundle(
    path: Path,
    output_dir: Path,
    *,
    impact_nodes: list[str] | None = None,
    advisory_path: Path | None = None,
    include_license_report: bool = False,
    denied_licenses: list[str] | None = None,
    max_paths: int = 20,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    adapter = NpmAdapter()
    resolved = adapter.parse_lockfile_graph(path)

    diagnostics_path = output_dir / "npm-diagnostics.json"
    diagnostics_path.write_text(_json(adapter.diagnose_lockfile(path)), encoding="utf-8")
    final_reports = []

    if advisory_path is not None:
        advisory_report_path = output_dir / "advisory-report.json"
        advisory_report_path.write_text(
            _json(
                build_advisory_report_from_file(
                    advisory_path,
                    resolved.graph,
                    root=resolved.root_identifier,
                    ecosystem=resolved.ecosystem,
                    max_paths=max_paths,
                )
            ),
            encoding="utf-8",
        )
        final_reports.append(advisory_report_path)

    final_reports.extend(
        _write_license_report_if_requested(
            output_dir,
            resolved,
            include_license_report=include_license_report,
            denied_licenses=denied_licenses,
        )
    )

    return write_graph_report_bundle(
        resolved,
        output_dir,
        graph_name="npm-graph",
        impact_nodes=impact_nodes,
        node_resolver=_resolve_impact_node,
        max_paths=max_paths,
        extra_reports_after_graph=[diagnostics_path],
        extra_reports=final_reports,
        bundle_metadata={"sourceKind": "npm-lockfile", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_npm_diagnostics_bundle(
    path: Path,
    output_dir: Path,
    *,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_path = output_dir / "npm-diagnostics.json"
    diagnostics_path.write_text(
        _json(NpmAdapter().diagnose_lockfile(path)),
        encoding="utf-8",
    )
    return write_report_bundle(
        [diagnostics_path],
        output_dir,
        bundle_metadata={"sourceKind": "npm-diagnostics", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_maven_bundle(
    path: Path,
    output_dir: Path,
    *,
    impact_nodes: list[str] | None = None,
    max_paths: int = 20,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    resolved = MavenTreeAdapter().parse_tree(path)
    return write_graph_report_bundle(
        resolved,
        output_dir,
        graph_name="maven-graph",
        impact_nodes=impact_nodes,
        node_resolver=_resolve_impact_node,
        max_paths=max_paths,
        bundle_metadata={"sourceKind": "maven-dependency-tree", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_dot_bundle(
    path: Path,
    output_dir: Path,
    *,
    ecosystem: str = "rpm",
    impact_nodes: list[str] | None = None,
    max_paths: int = 20,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    resolved = DotAdapter().parse_graph(path, ecosystem=ecosystem)
    return write_graph_report_bundle(
        resolved,
        output_dir,
        graph_name="dot-graph",
        impact_nodes=impact_nodes,
        node_resolver=_resolve_impact_node,
        max_paths=max_paths,
        bundle_metadata={"sourceKind": "dot", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_sbom_bundle(
    path: Path,
    output_dir: Path,
    *,
    impact_nodes: list[str] | None = None,
    include_license_report: bool = False,
    denied_licenses: list[str] | None = None,
    max_paths: int = 20,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    resolved = CycloneDXAdapter().parse_graph(path)
    return write_graph_report_bundle(
        resolved,
        output_dir,
        graph_name="sbom-graph",
        impact_nodes=impact_nodes,
        node_resolver=_resolve_impact_node,
        max_paths=max_paths,
        extra_reports=_write_license_report_if_requested(
            output_dir,
            resolved,
            include_license_report=include_license_report,
            denied_licenses=denied_licenses,
        ),
        bundle_metadata={"sourceKind": "cyclonedx-sbom", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_rpm_installed_bundle(
    output_dir: Path,
    *,
    limit: int = 100,
    max_requirements: int = 40,
    impact_nodes: list[str] | None = None,
    advisory_path: Path | None = None,
    public_advisory_feed_path: Path | None = None,
    public_advisory_feed_url: str | None = None,
    albs_build_id: str | None = None,
    albs_build_path: Path | None = None,
    albs_build_url: str | None = None,
    albs_base_url: str = DEFAULT_ALBS_BASE_URL,
    libsolv_transaction_path: Path | None = None,
    include_license_report: bool = False,
    denied_licenses: list[str] | None = None,
    max_paths: int = 20,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    resolved = InstalledRpmAdapter().parse_installed(
        limit=limit,
        max_requirements=max_requirements,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    graph_path = output_dir / "rpm-installed-graph.json"
    graph_path.write_text(
        GraphJsonExporter.export_to_json(
            resolved.graph,
            root=resolved.root_identifier,
            ecosystem=resolved.ecosystem,
        ),
        encoding="utf-8",
    )
    final_reports = _write_advisory_reports_if_requested(
        output_dir,
        resolved,
        advisory_path=advisory_path,
        public_advisory_feed_path=public_advisory_feed_path,
        public_advisory_feed_url=public_advisory_feed_url,
        max_paths=max_paths,
    )
    final_reports.extend(
        _write_rpm_albs_provenance_report_if_requested(
            output_dir,
            resolved,
            albs_build_id=albs_build_id,
            albs_build_path=albs_build_path,
            albs_build_url=albs_build_url,
            albs_base_url=albs_base_url,
        )
    )
    if libsolv_transaction_path is not None:
        libsolv_report_path = output_dir / "libsolv-bridge.json"
        libsolv_report_path.write_text(
            _json(build_libsolv_bridge_report(libsolv_transaction_path, graph_path)),
            encoding="utf-8",
        )
        final_reports.append(libsolv_report_path)
    final_reports.extend(
        _write_license_report_if_requested(
            output_dir,
            resolved,
            include_license_report=include_license_report,
            denied_licenses=denied_licenses,
        )
    )
    return write_graph_report_bundle(
        resolved,
        output_dir,
        graph_name="rpm-installed-graph",
        impact_nodes=impact_nodes,
        node_resolver=_resolve_impact_node,
        max_paths=max_paths,
        extra_reports=final_reports,
        bundle_metadata={"sourceKind": "rpm-installed", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _load_rpm_repo_project_graph(
    source: str,
    *,
    repo_id: str = "public-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
) -> ResolvedProjectGraph:
    return RpmRepositoryAdapter().parse_source(
        source,
        repo_id=repo_id,
        package_limit=package_limit,
        requirement_limit=requirement_limit,
    )


def _write_rpm_repo_bundle(
    source: str,
    output_dir: Path,
    *,
    repo_id: str = "public-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
    impact_nodes: list[str] | None = None,
    advisory_path: Path | None = None,
    public_advisory_feed_path: Path | None = None,
    public_advisory_feed_url: str | None = None,
    libsolv_transaction_path: Path | None = None,
    include_license_report: bool = False,
    denied_licenses: list[str] | None = None,
    max_paths: int = 20,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    resolved = _load_rpm_repo_project_graph(
        source,
        repo_id=repo_id,
        package_limit=package_limit,
        requirement_limit=requirement_limit,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    graph_path = output_dir / "rpm-repository-graph.json"
    graph_path.write_text(
        GraphJsonExporter.export_to_json(
            resolved.graph,
            root=resolved.root_identifier,
            ecosystem=resolved.ecosystem,
        ),
        encoding="utf-8",
    )
    summary_path = output_dir / "rpm-repository-summary.json"
    summary_path.write_text(
        _json(
            build_rpm_repository_summary_report(
                resolved.graph,
                root=resolved.root_identifier,
            )
        ),
        encoding="utf-8",
    )
    final_reports = _write_advisory_reports_if_requested(
        output_dir,
        resolved,
        advisory_path=advisory_path,
        public_advisory_feed_path=public_advisory_feed_path,
        public_advisory_feed_url=public_advisory_feed_url,
        max_paths=max_paths,
    )

    if libsolv_transaction_path is not None:
        libsolv_report_path = output_dir / "libsolv-bridge.json"
        libsolv_report_path.write_text(
            _json(build_libsolv_bridge_report(libsolv_transaction_path, graph_path)),
            encoding="utf-8",
        )
        final_reports.append(libsolv_report_path)

    final_reports.extend(
        _write_license_report_if_requested(
            output_dir,
            resolved,
            include_license_report=include_license_report,
            denied_licenses=denied_licenses,
        )
    )

    return write_graph_report_bundle(
        resolved,
        output_dir,
        graph_name="rpm-repository-graph",
        impact_nodes=impact_nodes,
        node_resolver=_resolve_impact_node,
        max_paths=max_paths,
        extra_reports_after_graph=[summary_path],
        extra_reports=final_reports,
        bundle_metadata={"sourceKind": "rpm-repository", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_rpm_repo_summary_bundle(
    source: str,
    output_dir: Path,
    *,
    repo_id: str = "public-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    resolved = _load_rpm_repo_project_graph(
        source,
        repo_id=repo_id,
        package_limit=package_limit,
        requirement_limit=requirement_limit,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "rpm-repository-summary.json"
    summary_path.write_text(
        _json(
            build_rpm_repository_summary_report(
                resolved.graph,
                root=resolved.root_identifier,
            )
        ),
        encoding="utf-8",
    )
    return write_report_bundle(
        [summary_path],
        output_dir,
        bundle_metadata={"sourceKind": "rpm-repository-summary", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_license_report_if_requested(
    output_dir: Path,
    resolved: ResolvedProjectGraph,
    *,
    include_license_report: bool = False,
    denied_licenses: list[str] | None = None,
) -> list[Path]:
    denied_licenses = denied_licenses or []
    if not include_license_report and not denied_licenses:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "license-report.json"
    report_path.write_text(
        _json(
            build_license_report(
                resolved.graph,
                root=resolved.root_identifier,
                ecosystem=resolved.ecosystem,
                denied_licenses=denied_licenses,
            )
        ),
        encoding="utf-8",
    )
    return [report_path]


def _write_advisory_reports_if_requested(
    output_dir: Path,
    resolved: ResolvedProjectGraph,
    *,
    advisory_path: Path | None = None,
    public_advisory_feed_path: Path | None = None,
    public_advisory_feed_url: str | None = None,
    max_paths: int = 20,
) -> list[Path]:
    final_reports = []
    if advisory_path is not None:
        advisory_report_path = output_dir / "advisory-report.json"
        advisory_report_path.write_text(
            _json(
                build_advisory_report_from_file(
                    advisory_path,
                    resolved.graph,
                    root=resolved.root_identifier,
                    ecosystem=resolved.ecosystem,
                    max_paths=max_paths,
                )
            ),
            encoding="utf-8",
        )
        final_reports.append(advisory_report_path)

    if public_advisory_feed_path is not None or public_advisory_feed_url is not None:
        public_feed_report_path = output_dir / "public-advisory-feed.json"
        public_feed_report = build_public_advisory_feed_report(
            _load_public_json_source(
                path=public_advisory_feed_path,
                url=public_advisory_feed_url,
            ),
            ecosystem=resolved.ecosystem,
        )
        public_feed_report_path.write_text(
            _json(public_feed_report),
            encoding="utf-8",
        )
        final_reports.append(public_feed_report_path)

        public_advisory_report_path = output_dir / "public-advisory-report.json"
        public_advisory_report_path.write_text(
            _json(
                build_advisory_report(
                    public_feed_report["overlay"],
                    resolved.graph,
                    root=resolved.root_identifier,
                    ecosystem=resolved.ecosystem,
                    max_paths=max_paths,
                )
            ),
            encoding="utf-8",
        )
        final_reports.append(public_advisory_report_path)

    return final_reports


def _write_rpm_albs_provenance_report_if_requested(
    output_dir: Path,
    resolved: ResolvedProjectGraph,
    *,
    albs_build_id: str | None = None,
    albs_build_path: Path | None = None,
    albs_build_url: str | None = None,
    albs_base_url: str = DEFAULT_ALBS_BASE_URL,
) -> list[Path]:
    if albs_build_id is None and albs_build_path is None and albs_build_url is None:
        return []
    albs_payload = _load_albs_build_metadata(
        build_id=albs_build_id,
        path=albs_build_path,
        url=albs_build_url,
        base_url=albs_base_url,
    )
    report_path = output_dir / "rpm-albs-provenance.json"
    report_path.write_text(
        _json(build_rpm_albs_provenance_report(resolved.graph, albs_payload)),
        encoding="utf-8",
    )
    return [report_path]


def _print_bundle_result(
    index_path: Path,
    *,
    archive_output: Path | None = None,
    fail_on_denied: bool = False,
    fail_on_status: str | None = None,
    output_format: str = "path",
) -> int:
    if output_format == "text":
        print(_format_report_bundle_result(index_path, archive_output=archive_output))
    else:
        print(index_path)
    if fail_on_denied and _bundle_license_report_should_fail(index_path.parent):
        return 2
    if _bundle_triage_summary_should_fail(index_path.parent, min_status=fail_on_status):
        return 2
    return 0


def _print_bundle_catalog_result(
    index_path: Path,
    *,
    output_format: str = "path",
    fail_on_status: str | None = None,
) -> int:
    if output_format == "text":
        print(_format_bundle_catalog_result(index_path))
    else:
        print(index_path)
    if _bundle_triage_summary_should_fail(index_path.parent, min_status=fail_on_status):
        return 2
    return 0


def _format_bundle_catalog_result(index_path: Path) -> str:
    catalog = _load_optional_json(index_path.parent / "bundle-catalog.json")
    summary = catalog.get("summary", {}) if isinstance(catalog, dict) else {}
    if not isinstance(summary, dict):
        summary = {}
    parts = [
        "OK",
        f"index={index_path}",
        f"catalogStatus={catalog.get('status', 'unknown')}",
        f"bundles={int(summary.get('bundles', 0) or 0)}",
        f"okBundles={int(summary.get('okBundles', 0) or 0)}",
        f"failedBundles={int(summary.get('failedBundles', 0) or 0)}",
        f"reports={int(summary.get('reports', 0) or 0)}",
        f"failures={int(summary.get('failures', 0) or 0)}",
        f"triageWarn={int(summary.get('triageWarn', 0) or 0)}",
        f"triageFail={int(summary.get('triageFail', 0) or 0)}",
    ]
    parts.extend(_policy_failure_text_parts(summary))
    triage = _load_optional_json(index_path.parent / "triage-summary.json")
    if isinstance(triage, dict):
        triage_status = triage.get("status")
        if isinstance(triage_status, str) and triage_status:
            parts.append(f"triageStatus={triage_status}")
    return " ".join(parts)


def _format_report_bundle_result(
    index_path: Path,
    *,
    archive_output: Path | None = None,
) -> str:
    manifest = _load_optional_json(index_path.parent / "manifest.json")
    bundle = manifest.get("bundle", {}) if isinstance(manifest, dict) else {}
    if not isinstance(bundle, dict):
        bundle = {}
    parts = [
        "BUNDLE",
        f"index={_text_value(index_path)}",
    ]
    if archive_output is not None:
        parts.append(f"archive={_text_value(archive_output)}")
    parts.extend(
        [
            f"sourceKind={_text_value(bundle.get('sourceKind', 'unknown'))}",
            f"reports={int(manifest.get('reportCount', 0) or 0)}",
        ]
    )
    bundle_sha = manifest.get("bundleSha256")
    if isinstance(bundle_sha, str) and bundle_sha:
        parts.append(f"bundleSha256={bundle_sha}")
    triage = _load_optional_json(index_path.parent / "triage-summary.json")
    triage_status = triage.get("status") if isinstance(triage, dict) else None
    if isinstance(triage_status, str) and triage_status:
        parts.append(f"triageStatus={triage_status}")
    return " ".join(parts)


def _format_rpm_repository_summary_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    architectures = _dict_list(report.get("architectures"))
    source_rpms = _dict_list(report.get("topSourceRpms"))
    unresolved = _dict_list(report.get("unresolvedRequirements"))
    parts = [
        "OK",
        "schema=edgp.rpm.repository_summary.v1",
        f"root={_text_value(report.get('root', ''))}",
        f"packages={int(summary.get('packages', 0) or 0)}",
        f"sourceRpms={int(summary.get('sourceRpms', 0) or 0)}",
        f"architectures={int(summary.get('architectures', 0) or 0)}",
        f"requirementEdges={int(summary.get('requirementEdges', 0) or 0)}",
        (
            "unresolvedRequirements="
            f"{int(summary.get('unresolvedRequirements', 0) or 0)}"
        ),
    ]
    if architectures:
        arch_labels = [
            f"{entry.get('arch', 'unknown')}:{int(entry.get('packages', 0) or 0)}"
            for entry in architectures
        ]
        parts.append(f"archBreakdown={_text_value(','.join(arch_labels))}")
    if source_rpms:
        top_source = source_rpms[0]
        parts.append(f"topSourceRpm={_text_value(top_source.get('sourceRpm', ''))}")
        parts.append(f"topSourceRpmPackages={int(top_source.get('packages', 0) or 0)}")
    if unresolved:
        first = unresolved[0]
        parts.append(f"firstUnresolved={_text_value(first.get('capability', ''))}")
    return " ".join(parts)


def _format_rpm_repository_diff_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    top_findings = report.get("topFindings")
    if not isinstance(top_findings, dict):
        top_findings = {}
    changed = _dict_list(top_findings.get("changedPackages"))
    added = _dict_list(top_findings.get("addedPackages"))
    removed = _dict_list(top_findings.get("removedPackages"))
    parts = [
        "RPM_REPO_DIFF",
        "schema=edgp.rpm.repository_diff.v1",
        f"leftPackages={int(summary.get('leftPackages', 0) or 0)}",
        f"rightPackages={int(summary.get('rightPackages', 0) or 0)}",
        f"addedPackages={int(summary.get('addedPackages', 0) or 0)}",
        f"removedPackages={int(summary.get('removedPackages', 0) or 0)}",
        f"changedPackages={int(summary.get('changedPackages', 0) or 0)}",
        f"unchangedPackages={int(summary.get('unchangedPackages', 0) or 0)}",
        f"addedSourceRpms={int(summary.get('addedSourceRpms', 0) or 0)}",
        f"removedSourceRpms={int(summary.get('removedSourceRpms', 0) or 0)}",
    ]
    if changed:
        first = changed[0]
        left = first.get("left")
        right = first.get("right")
        if not isinstance(left, dict):
            left = {}
        if not isinstance(right, dict):
            right = {}
        parts.append(f"firstChanged={_text_value(first.get('name', ''))}")
        parts.append(f"changedArch={_text_value(first.get('arch', ''))}")
        parts.append(
            "changedFields="
            f"{_text_value(','.join(_string_list(first.get('changedFields'))))}"
        )
        left_version = f"{left.get('version', '')}-{left.get('release', '')}"
        right_version = f"{right.get('version', '')}-{right.get('release', '')}"
        parts.append(f"from={_text_value(left_version)}")
        parts.append(f"to={_text_value(right_version)}")
    if added:
        first = added[0]
        parts.append(f"firstAdded={_text_value(first.get('name', ''))}")
        parts.append(f"firstAddedArch={_text_value(first.get('arch', ''))}")
    if removed:
        first = removed[0]
        parts.append(f"firstRemoved={_text_value(first.get('name', ''))}")
        parts.append(f"firstRemovedArch={_text_value(first.get('arch', ''))}")
    return " ".join(parts)


def _format_albs_artifact_inventory_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    build_architectures = _string_list(report.get("buildArchitectures"))
    packages = _string_list(report.get("packages"))
    by_build_arch = _dict_list(report.get("byBuildArch"))
    parts = [
        "OK",
        "schema=edgp.albs.artifact_inventory.v1",
        f"root={_text_value(report.get('root', ''))}",
        f"artifacts={int(summary.get('artifacts', 0) or 0)}",
        f"buildTasks={int(summary.get('buildTasks', 0) or 0)}",
        f"binaryRpms={int(summary.get('binaryRpms', 0) or 0)}",
        f"sourceRpms={int(summary.get('sourceRpms', 0) or 0)}",
        f"debugArtifacts={int(summary.get('debugArtifacts', 0) or 0)}",
        f"buildLogs={int(summary.get('buildLogs', 0) or 0)}",
        f"architectures={int(summary.get('architectures', 0) or 0)}",
        f"packages={int(summary.get('packages', 0) or 0)}",
    ]
    if build_architectures:
        parts.append(f"buildArchitectures={_text_value(','.join(build_architectures))}")
    if packages:
        parts.append(f"samplePackages={_text_value(','.join(packages[:5]))}")
    if by_build_arch:
        arch_counts = [
            f"{entry.get('buildArch', 'unknown')}:{int(entry.get('totalArtifacts', 0) or 0)}"
            for entry in by_build_arch
        ]
        parts.append(f"artifactsByBuildArch={_text_value(','.join(arch_counts))}")
    return " ".join(parts)


def _format_albs_build_timing_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    artifact_types = report.get("artifactTypes")
    if not isinstance(artifact_types, dict):
        artifact_types = {}
    sign_steps = report.get("signStepTotalsSeconds")
    if not isinstance(sign_steps, dict):
        sign_steps = {}
    task_timings = _dict_list(report.get("taskTimings"))
    parts = [
        "OK",
        "schema=edgp.albs.build_timing.v1",
        f"root={_text_value(report.get('root', ''))}",
        f"buildId={_text_value(report.get('buildId', ''))}",
        f"wallSeconds={float(report.get('wallSeconds', 0.0) or 0.0):.3f}",
        f"buildTasks={int(summary.get('buildTasks', 0) or 0)}",
        f"signTasks={int(summary.get('signTasks', 0) or 0)}",
        f"artifacts={int(summary.get('artifacts', 0) or 0)}",
        (
            "aggregateBuildTaskWallSeconds="
            f"{float(summary.get('aggregateBuildTaskWallSeconds', 0.0) or 0.0):.3f}"
        ),
        (
            "criticalBuildTaskWallSeconds="
            f"{float(summary.get('criticalBuildTaskWallSeconds', 0.0) or 0.0):.3f}"
        ),
        (
            "aggregateSignTaskWallSeconds="
            f"{float(summary.get('aggregateSignTaskWallSeconds', 0.0) or 0.0):.3f}"
        ),
    ]
    if artifact_types:
        artifact_labels = [
            f"{key}:{int(value or 0)}"
            for key, value in sorted(artifact_types.items())
        ]
        parts.append(f"artifactTypes={_text_value(','.join(artifact_labels))}")
    if sign_steps:
        sign_labels = [
            f"{key}:{float(value or 0.0):.3f}"
            for key, value in sorted(sign_steps.items())
        ]
        parts.append(f"signSteps={_text_value(','.join(sign_labels))}")
    if task_timings:
        slowest = max(
            task_timings,
            key=lambda task: float(task.get("wallSeconds", 0.0) or 0.0),
        )
        parts.append(f"slowestTask={_text_value(slowest.get('taskId', ''))}")
        parts.append(f"slowestArch={_text_value(slowest.get('arch', ''))}")
        parts.append(
            f"slowestWallSeconds={float(slowest.get('wallSeconds', 0.0) or 0.0):.3f}"
        )
    return " ".join(parts)


def _format_public_advisory_feed_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    packages = _string_list(report.get("packages"))
    severities = _string_list(report.get("severities"))
    advisories = _dict_list(report.get("advisories"))
    parts = [
        "OK",
        "schema=edgp.public.advisory_feed.v1",
        f"ecosystem={_text_value(report.get('ecosystem', ''))}",
        f"advisories={int(summary.get('advisories', 0) or 0)}",
        f"packages={int(summary.get('packages', 0) or 0)}",
        f"severities={int(summary.get('severities', 0) or 0)}",
    ]
    if packages:
        parts.append(f"samplePackages={_text_value(','.join(packages[:5]))}")
    if severities:
        parts.append(f"severityLabels={_text_value(','.join(severities))}")
    if advisories:
        first = advisories[0]
        parts.append(f"firstAdvisory={_text_value(first.get('id', ''))}")
        parts.append(f"firstPackage={_text_value(first.get('package', ''))}")
        if first.get("severity"):
            parts.append(f"firstSeverity={_text_value(first.get('severity', ''))}")
        versions = _string_list(first.get("versions"))
        if versions:
            parts.append(f"firstVersions={_text_value(','.join(versions[:5]))}")
        ranges = _dict_list(first.get("ranges"))
        if ranges:
            parts.append(f"firstRanges={len(ranges)}")
    return " ".join(parts)


def _format_albs_build_diff_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    left = report.get("left")
    if not isinstance(left, dict):
        left = {}
    right = report.get("right")
    if not isinstance(right, dict):
        right = {}
    timing = report.get("timingDelta")
    if not isinstance(timing, dict):
        timing = {}
    top_findings = report.get("topFindings")
    if not isinstance(top_findings, dict):
        top_findings = {}
    changed = _dict_list(top_findings.get("changedArtifacts"))
    added = _dict_list(top_findings.get("addedArtifacts"))
    removed = _dict_list(top_findings.get("removedArtifacts"))
    parts = [
        "ALBS_BUILD_DIFF",
        "schema=edgp.albs.build_diff.v1",
        f"leftBuild={_text_value(left.get('buildId', ''))}",
        f"rightBuild={_text_value(right.get('buildId', ''))}",
        f"package={_text_value(right.get('package') or left.get('package') or '')}",
        f"addedArtifacts={int(summary.get('addedArtifacts', 0) or 0)}",
        f"removedArtifacts={int(summary.get('removedArtifacts', 0) or 0)}",
        f"changedArtifacts={int(summary.get('changedArtifacts', 0) or 0)}",
        (
            "leftMissingBuildArchitectures="
            f"{int(summary.get('leftMissingBuildArchitectures', 0) or 0)}"
        ),
        (
            "rightMissingBuildArchitectures="
            f"{int(summary.get('rightMissingBuildArchitectures', 0) or 0)}"
        ),
        f"gitCommitChanged={str(bool(summary.get('gitCommitChanged'))).lower()}",
        (
            "wallSecondsDelta="
            f"{float(timing.get('wallSecondsDelta', 0.0) or 0.0):.3f}"
        ),
        (
            "criticalBuildTaskWallSecondsDelta="
            f"{float(summary.get('criticalBuildTaskWallSecondsDelta', 0.0) or 0.0):.3f}"
        ),
    ]
    if changed:
        first = changed[0]
        parts.append(f"firstChanged={_text_value(first.get('packageName', ''))}")
        parts.append(f"firstChangedArch={_text_value(first.get('artifactArch', ''))}")
        parts.append(
            "changedFields="
            f"{_text_value(','.join(_string_list(first.get('changedFields'))))}"
        )
    if added:
        first = added[0]
        parts.append(f"firstAdded={_text_value(first.get('packageName', ''))}")
        parts.append(f"firstAddedArch={_text_value(first.get('artifactArch', ''))}")
    if removed:
        first = removed[0]
        parts.append(f"firstRemoved={_text_value(first.get('packageName', ''))}")
        parts.append(f"firstRemovedArch={_text_value(first.get('artifactArch', ''))}")
    return " ".join(parts)


def _format_albs_log_intelligence_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    signal_counts = report.get("signalCounts")
    if not isinstance(signal_counts, dict):
        signal_counts = {}
    logs = _dict_list(report.get("logs"))
    signal_logs = [
        log
        for log in logs
        if isinstance(log.get("signals"), dict) and log.get("signals")
    ]
    parts = [
        "ALBS_LOG_INTELLIGENCE",
        "schema=edgp.albs.log_intelligence.v1",
        f"root={_text_value(report.get('root', ''))}",
        f"logArtifacts={int(summary.get('logArtifacts', 0) or 0)}",
        (
            "logsWithInlineContent="
            f"{int(summary.get('logsWithInlineContent', 0) or 0)}"
        ),
        f"signalKinds={int(summary.get('signalKinds', 0) or 0)}",
        f"signals={int(summary.get('signals', 0) or 0)}",
    ]
    if signal_counts:
        labels = [
            f"{key}:{int(value or 0)}"
            for key, value in sorted(signal_counts.items())
        ]
        parts.append(f"signalCounts={_text_value(','.join(labels))}")
    if signal_logs:
        first = signal_logs[0]
        signals = first.get("signals")
        if not isinstance(signals, dict):
            signals = {}
        parts.append(f"firstSignalLog={_text_value(first.get('name', ''))}")
        parts.append(f"firstSignalArch={_text_value(first.get('buildArch', ''))}")
        parts.append(
            f"firstSignalKinds={_text_value(','.join(sorted(str(key) for key in signals)))}"
        )
        sample = str(first.get("sample", "") or "")[:160]
        if sample:
            parts.append(f"firstSignalSample={_text_value(sample)}")
    return " ".join(parts)


def _format_albs_release_completeness_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    builds = _dict_list(report.get("builds"))
    builds_missing_arches = [
        build for build in builds if _string_list(build.get("missingBuildArchitectures"))
    ]
    builds_failed_tasks = [
        build for build in builds if int(build.get("failedBuildTasks", 0) or 0)
    ]
    parts = [
        "ALBS_RELEASE_COMPLETENESS",
        "schema=edgp.albs.release_completeness.v1",
        f"builds={int(summary.get('builds', 0) or 0)}",
        f"releasedBuilds={int(summary.get('releasedBuilds', 0) or 0)}",
        (
            "buildsWithMissingArchitectures="
            f"{int(summary.get('buildsWithMissingArchitectures', 0) or 0)}"
        ),
        (
            "missingBuildArchitectures="
            f"{int(summary.get('missingBuildArchitectures', 0) or 0)}"
        ),
        f"failedBuildTasks={int(summary.get('failedBuildTasks', 0) or 0)}",
        (
            "buildsWithoutSignTasks="
            f"{int(summary.get('buildsWithoutSignTasks', 0) or 0)}"
        ),
        (
            "buildsWithoutTestTasks="
            f"{int(summary.get('buildsWithoutTestTasks', 0) or 0)}"
        ),
    ]
    if builds_missing_arches:
        first = builds_missing_arches[0]
        parts.append(f"firstMissingBuild={_text_value(first.get('buildId', ''))}")
        parts.append(f"firstMissingRelease={_text_value(first.get('releaseId', ''))}")
        parts.append(
            "firstMissingArchitectures="
            f"{_text_value(','.join(_string_list(first.get('missingBuildArchitectures'))))}"
        )
    if builds_failed_tasks:
        first = builds_failed_tasks[0]
        parts.append(f"firstFailedBuild={_text_value(first.get('buildId', ''))}")
        parts.append(f"firstFailedTasks={int(first.get('failedBuildTasks', 0) or 0)}")
    return " ".join(parts)


def _format_rpm_albs_provenance_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    installed_packages = int(summary.get("installedPackages", 0) or 0)
    matched_packages = int(summary.get("matchedPackages", 0) or 0)
    match_percent = (
        (matched_packages / installed_packages) * 100.0
        if installed_packages
        else 0.0
    )
    matches = _dict_list(report.get("matches"))
    unmatched = _dict_list(report.get("unmatchedInstalledPackages"))
    parts = [
        "RPM_ALBS_PROVENANCE",
        "schema=edgp.rpm.albs_provenance.v1",
        f"root={_text_value(report.get('root', ''))}",
        f"installedPackages={installed_packages}",
        f"albsArtifacts={int(summary.get('albsArtifacts', 0) or 0)}",
        f"matchedPackages={matched_packages}",
        f"unmatchedPackages={int(summary.get('unmatchedPackages', 0) or 0)}",
        f"matchPercent={match_percent:.3f}",
    ]
    if matches:
        first = matches[0]
        installed = first.get("installedPackage")
        if not isinstance(installed, dict):
            installed = {}
        artifact = first.get("albsArtifact")
        if not isinstance(artifact, dict):
            artifact = {}
        parts.append(f"firstMatch={_text_value(installed.get('name', ''))}")
        parts.append(f"firstMatchArch={_text_value(installed.get('arch', ''))}")
        parts.append(f"firstMatchBuild={_text_value(first.get('buildId', ''))}")
        parts.append(
            f"firstMatchArtifact={_text_value(artifact.get('filename', ''))}"
        )
    if unmatched:
        first = unmatched[0]
        parts.append(f"firstUnmatched={_text_value(first.get('name', ''))}")
        parts.append(f"firstUnmatchedArch={_text_value(first.get('arch', ''))}")
    return " ".join(parts)


def _format_triage_summary_report(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    parts = [
        "TRIAGE",
        f"status={report.get('status', 'unknown')}",
        f"reports={int(summary.get('reports', 0) or 0)}",
        f"failedChecks={int(summary.get('failedChecks', 0) or 0)}",
    ]
    graph_snapshots = int(summary.get("graphSnapshots", 0) or 0)
    if graph_snapshots:
        parts.append(f"graphSnapshots={graph_snapshots}")
        parts.append(f"nodes={int(summary.get('nodes', 0) or 0)}")
        parts.append(f"edges={int(summary.get('edges', 0) or 0)}")
    for key in (
        "advisoryFindings",
        "deniedLicenseFindings",
        "missingLicenses",
    ):
        value = int(summary.get(key, 0) or 0)
        if value:
            parts.append(f"{key}={value}")
    npm_signals = (
        int(summary.get("npmDuplicatePackageNames", 0) or 0)
        + int(summary.get("npmNestedResolutionConflicts", 0) or 0)
        + int(summary.get("npmUnresolvedDependencies", 0) or 0)
    )
    if npm_signals:
        parts.append(f"npmSignals={npm_signals}")
    parts.extend(_policy_failure_text_parts(summary))
    for key in (
        "catalogFailedBundles",
        "catalogFailures",
        "catalogTriageWarn",
        "catalogTriageFail",
    ):
        value = int(summary.get(key, 0) or 0)
        if value:
            parts.append(f"{key}={value}")
    return " ".join(parts)


def _format_graph_diff_report(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    parts = [
        "DIFF",
        f"leftRoot={_text_value(report.get('leftRoot') or '')}",
        f"rightRoot={_text_value(report.get('rightRoot') or '')}",
        f"addedNodes={int(summary.get('addedNodes', 0) or 0)}",
        f"removedNodes={int(summary.get('removedNodes', 0) or 0)}",
        f"metadataChangedNodes={int(summary.get('metadataChangedNodes', 0) or 0)}",
        f"addedEdges={int(summary.get('addedEdges', 0) or 0)}",
        f"removedEdges={int(summary.get('removedEdges', 0) or 0)}",
        f"classifiedChanges={int(summary.get('classifiedChanges', 0) or 0)}",
    ]
    for key in (
        "upgradeChanges",
        "downgradeChanges",
        "replacementChanges",
        "addedOnlyChanges",
        "removedOnlyChanges",
        "metadataOnlyChanges",
    ):
        value = int(summary.get(key, 0) or 0)
        if value:
            parts.append(f"{key}={value}")
    policy = report.get("policy")
    if isinstance(policy, dict):
        parts.extend(
            _policy_text_parts(
                policy,
                requested_key="failOnChange",
                matched_key="matchedChanges",
            )
        )
        parts.extend(
            _policy_list_text_parts(
                policy,
                requested_key="failOnKind",
                matched_key="matchedKinds",
            )
        )
    return " ".join(parts)


def _format_graph_diff_bundle_result(
    index_path: Path,
    report: dict[str, Any],
    *,
    archive_output: Path | None = None,
) -> str:
    details = _format_graph_diff_report(report).removeprefix("DIFF ")
    archive_part = (
        f" archive={_text_value(archive_output)}" if archive_output is not None else ""
    )
    return f"DIFF_BUNDLE index={_text_value(index_path)}{archive_part} {details}"


def _format_graph_diff_tree_report(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    parts = [
        "DIFF_TREE",
        f"selector={_text_value(report.get('selector') or '')}",
        f"direction={_text_value(report.get('direction') or '')}",
        f"depth={int(report.get('depth', 0) or 0)}",
        f"addedNodes={int(summary.get('addedNodes', 0) or 0)}",
        f"removedNodes={int(summary.get('removedNodes', 0) or 0)}",
        f"metadataChangedNodes={int(summary.get('metadataChangedNodes', 0) or 0)}",
        f"addedEdges={int(summary.get('addedEdges', 0) or 0)}",
        f"removedEdges={int(summary.get('removedEdges', 0) or 0)}",
        f"classifiedChanges={int(summary.get('classifiedChanges', 0) or 0)}",
    ]
    for key in (
        "upgradeChanges",
        "downgradeChanges",
        "replacementChanges",
        "addedOnlyChanges",
        "removedOnlyChanges",
        "metadataOnlyChanges",
    ):
        value = int(summary.get(key, 0) or 0)
        if value:
            parts.append(f"{key}={value}")
    policy = report.get("policy")
    if isinstance(policy, dict):
        parts.extend(
            _policy_text_parts(
                policy,
                requested_key="failOnKind",
                matched_key="matchedKinds",
            )
        )
    return " ".join(parts)


def _format_graph_diff_tree_bundle_result(
    index_path: Path,
    report: dict[str, Any],
    *,
    archive_output: Path | None = None,
) -> str:
    details = _format_graph_diff_tree_report(report).removeprefix("DIFF_TREE ")
    archive_part = (
        f" archive={_text_value(archive_output)}" if archive_output is not None else ""
    )
    return f"DIFF_TREE_BUNDLE index={_text_value(index_path)}{archive_part} {details}"


def _policy_text_parts(
    policy: dict[str, Any],
    *,
    requested_key: str,
    matched_key: str,
) -> list[str]:
    parts = []
    status = policy.get("status")
    if isinstance(status, str) and status:
        parts.append(f"policyStatus={status}")
    parts.extend(
        _policy_list_text_parts(
            policy,
            requested_key=requested_key,
            matched_key=matched_key,
        )
    )
    return parts


def _policy_list_text_parts(
    policy: dict[str, Any],
    *,
    requested_key: str,
    matched_key: str,
) -> list[str]:
    parts = []
    requested = _string_list(policy.get(requested_key))
    if requested:
        parts.append(f"{requested_key}={_text_value(','.join(requested))}")
    matched = _string_list(policy.get(matched_key))
    if matched:
        parts.append(f"{matched_key}={_text_value(','.join(matched))}")
    return parts


def _text_value(value: object) -> str:
    return shlex.quote(str(value))


def _format_fixture_provenance_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    synthetic_files = sum(
        int(group.get("fileCount", 0) or 0)
        for group in _dict_list(report.get("syntheticGroups"))
    )
    source_labels = [
        str(source.get("label", ""))
        for source in _dict_list(report.get("sourceUrls"))
        if str(source.get("label", ""))
    ]
    parts = [
        "OK",
        "schema=edgp.fixture.provenance.v1",
        f"fixtureRoot={_text_value(report.get('fixtureRoot', ''))}",
        f"catalogedFiles={int(summary.get('catalogedFiles', 0) or 0)}",
        f"publicDerivedSources={int(summary.get('publicDerivedSources', 0) or 0)}",
        (
            "deterministicPublicDerivedVariants="
            f"{int(summary.get('deterministicPublicDerivedVariants', 0) or 0)}"
        ),
        f"generatedPublicReports={int(summary.get('generatedPublicReports', 0) or 0)}",
        f"syntheticGroups={int(summary.get('syntheticGroups', 0) or 0)}",
        f"syntheticFiles={synthetic_files}",
        f"sourceUrls={int(summary.get('sourceUrls', 0) or 0)}",
    ]
    if source_labels:
        parts.append(f"publicSources={_text_value(','.join(source_labels))}")
    return " ".join(parts)


def _format_benchmark_result(report: dict[str, Any]) -> str:
    parameters = report.get("parameters")
    if not isinstance(parameters, dict):
        parameters = {}
    accelerators = report.get("accelerators")
    if not isinstance(accelerators, dict):
        accelerators = {}
    stats = report.get("stats")
    if not isinstance(stats, dict):
        stats = {}
    storage = report.get("storage")
    if not isinstance(storage, dict):
        storage = {}
    timings = report.get("timingsMs")
    if not isinstance(timings, dict):
        timings = {}
    ranking = _dict_list(report.get("mostDependedUpon"))
    parts = [
        "OK",
        "schema=edgp.benchmark.v1",
        f"nodes={int(stats.get('nodes', 0) or 0)}",
        f"edges={int(stats.get('edges', 0) or 0)}",
        f"fanout={int(parameters.get('fanout', 0) or 0)}",
        f"backend={_text_value(parameters.get('backend', ''))}",
        f"selectedBackend={_text_value(accelerators.get('selectedBackend', ''))}",
        f"layout={_text_value(storage.get('layout', ''))}",
        f"runtime={_text_value(storage.get('runtime', ''))}",
        f"cContiguous={str(bool(storage.get('cContiguous'))).lower()}",
        f"reachableFromRoot={int(stats.get('reachableFromRoot', 0) or 0)}",
        (
            "reverseReachableFromTail="
            f"{int(stats.get('reverseReachableFromTail', 0) or 0)}"
        ),
        f"buildMs={float(timings.get('build', 0.0) or 0.0):.3f}",
        f"freezeMs={float(timings.get('freeze', 0.0) or 0.0):.3f}",
        f"reachableMs={float(timings.get('reachable', 0.0) or 0.0):.3f}",
        (
            "reverseReachableMs="
            f"{float(timings.get('reverseReachable', 0.0) or 0.0):.3f}"
        ),
        (
            "mostDependedUponMs="
            f"{float(timings.get('mostDependedUpon', 0.0) or 0.0):.3f}"
        ),
    ]
    if ranking:
        top = ranking[0]
        parts.append(f"topPackage={_text_value(top.get('package', ''))}")
        parts.append(f"topDependents={int(top.get('dependents', 0) or 0)}")
    return " ".join(parts)


def _format_performance_report_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    results = _dict_list(report.get("results"))
    selected_backends = _string_list(summary.get("selectedBackends"))
    worst_reachable = max(
        (float(result.get("reachableMs", 0.0) or 0.0) for result in results),
        default=0.0,
    )
    worst_reverse = max(
        (float(result.get("reverseReachableMs", 0.0) or 0.0) for result in results),
        default=0.0,
    )
    worst_ranking = max(
        (float(result.get("mostDependedUponMs", 0.0) or 0.0) for result in results),
        default=0.0,
    )
    parts = [
        "OK",
        "schema=edgp.performance.report.v1",
        f"scenarios={int(summary.get('scenarios', 0) or 0)}",
        f"maxNodes={int(summary.get('maxNodes', 0) or 0)}",
        f"maxEdges={int(summary.get('maxEdges', 0) or 0)}",
        f"allContiguous={str(bool(summary.get('allContiguous'))).lower()}",
        f"layout={_text_value(summary.get('layout', ''))}",
        f"backend={_text_value(summary.get('backend', ''))}",
        f"selectedBackends={_text_value(','.join(selected_backends))}",
        f"worstReachableMs={worst_reachable:.3f}",
        f"worstReverseReachableMs={worst_reverse:.3f}",
        f"worstMostDependedUponMs={worst_ranking:.3f}",
    ]
    if results:
        largest = max(results, key=lambda result: int(result.get("nodes", 0) or 0))
        parts.append(f"largestScenario={int(largest.get('nodes', 0) or 0)}")
        parts.append(f"largestFanout={int(largest.get('fanout', 0) or 0)}")
    return " ".join(parts)


def _format_accelerator_status_result(report: dict[str, Any]) -> str:
    numba = report.get("numba")
    if not isinstance(numba, dict):
        numba = {}
    graphblas = report.get("graphblas")
    if not isinstance(graphblas, dict):
        graphblas = {}
    graphblas_kernels = [
        str(kernel)
        for kernel in graphblas.get("candidateKernels", [])
        if str(kernel)
    ]
    parts = [
        "OK",
        "command=accelerator-status",
        f"requestedBackend={_text_value(report.get('requestedBackend', ''))}",
        f"selectedBackend={_text_value(report.get('selectedBackend', ''))}",
        f"numbaAvailable={str(bool(numba.get('available'))).lower()}",
        f"numbaExtra={_text_value(numba.get('installExtra', ''))}",
        f"graphblasAvailable={str(bool(graphblas.get('available'))).lower()}",
        f"graphblasExtra={_text_value(graphblas.get('installExtra', ''))}",
        (
            "graphblasStorageContract="
            f"{_text_value(graphblas.get('storageContract', ''))}"
        ),
    ]
    if graphblas_kernels:
        parts.append(f"graphblasKernels={_text_value(','.join(graphblas_kernels))}")
    return " ".join(parts)


def _format_csr_artifact_manifest(
    manifest: dict[str, Any],
    *,
    output_dir: Path,
) -> str:
    profile = manifest.get("storageProfile")
    if not isinstance(profile, dict):
        profile = {}
    arrays = manifest.get("arrays")
    array_count = len(arrays) if isinstance(arrays, dict) else 0
    parts = [
        "OK",
        f"schema={_text_value(manifest.get('schema', ''))}",
        f"layout={_text_value(manifest.get('layout', ''))}",
        f"layoutVersion={int(manifest.get('layoutVersion', 0) or 0)}",
        f"nodes={int(manifest.get('nodes', 0) or 0)}",
        f"edges={int(manifest.get('edges', 0) or 0)}",
        f"dtype={_text_value(manifest.get('dtype', ''))}",
        f"arrays={array_count}",
        f"totalBytes={int(profile.get('totalBytes', 0) or 0)}",
        f"memoryMappable={str(bool(profile.get('memoryMappable'))).lower()}",
        f"readOnly={str(bool(profile.get('readOnly'))).lower()}",
        f"outputDir={_text_value(output_dir)}",
    ]
    return " ".join(parts)


def _format_parallel_query_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    results = _dict_list(report.get("results"))
    total_nodes = sum(int(result.get("count", 0) or 0) for result in results)
    max_nodes = max(
        (int(result.get("count", 0) or 0) for result in results),
        default=0,
    )
    parts = [
        "OK",
        "schema=edgp.parallel.query.report.v1",
        f"queries={int(summary.get('queries', 0) or 0)}",
        f"workers={int(summary.get('workers', 0) or 0)}",
        f"backend={_text_value(summary.get('backend', ''))}",
        f"selectedBackend={_text_value(summary.get('selectedBackend', ''))}",
        f"durationMs={float(summary.get('durationMs', 0.0) or 0.0):.3f}",
        f"totalResultNodes={total_nodes}",
        f"maxResultNodes={max_nodes}",
    ]
    if results:
        first = results[0]
        parts.append(f"firstQuery={_text_value(first.get('direction', ''))}")
        parts.append(f"firstNode={_text_value(first.get('node', ''))}")
        parts.append(f"firstCount={int(first.get('count', 0) or 0)}")
    return " ".join(parts)


def _format_real_data_coverage_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    parts = [
        str(report.get("status", "unknown")).upper(),
        "schema=edgp.real_data.coverage.v1",
        f"publicEvidenceFiles={int(summary.get('publicEvidenceFiles', 0) or 0)}",
        f"catalogedFiles={int(summary.get('catalogedFiles', 0) or 0)}",
        (
            "publicEvidenceCoveragePercent="
            f"{float(summary.get('publicEvidenceCoveragePercent', 0.0) or 0.0):.2f}"
        ),
        f"directPublicSources={int(summary.get('directPublicSources', 0) or 0)}",
        f"generatedPublicReports={int(summary.get('generatedPublicReports', 0) or 0)}",
        f"syntheticFiles={int(summary.get('syntheticFiles', 0) or 0)}",
        (
            "replacementCandidateGroups="
            f"{int(summary.get('replacementCandidateGroups', 0) or 0)}"
        ),
    ]
    top_candidate = _top_real_data_plan_entry(report.get("replacementPlan"))
    if top_candidate:
        parts.append(f"topCandidate={_text_value(top_candidate)}")
    parts.extend(_real_data_policy_text_parts(report.get("policy")))
    return " ".join(parts)


def _format_real_data_replacement_plan_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    coverage = report.get("coverageSummary")
    if not isinstance(coverage, dict):
        coverage = {}
    parts = [
        str(report.get("status", "unknown")).upper(),
        "schema=edgp.real_data.replacement_plan.v1",
        f"replacementCandidates={int(summary.get('replacementCandidates', 0) or 0)}",
        f"candidateFiles={int(summary.get('candidateFiles', 0) or 0)}",
        f"deferredGroups={int(summary.get('deferredGroups', 0) or 0)}",
        f"highPriorityGroups={int(summary.get('highPriorityGroups', 0) or 0)}",
        f"mediumPriorityGroups={int(summary.get('mediumPriorityGroups', 0) or 0)}",
        f"publicEvidenceFiles={int(summary.get('publicEvidenceFiles', 0) or 0)}",
        (
            "publicEvidenceCoveragePercent="
            f"{float(summary.get('publicEvidenceCoveragePercent', 0.0) or 0.0):.2f}"
        ),
    ]
    coverage_status = coverage.get("coverageStatus")
    if isinstance(coverage_status, str) and coverage_status:
        parts.append(f"coverageStatus={coverage_status}")
    top_candidate = _top_replacement_candidate(report.get("replacementCandidates"))
    if top_candidate:
        parts.append(f"topCandidate={_text_value(top_candidate)}")
    parts.extend(_real_data_policy_text_parts(report.get("policy")))
    return " ".join(parts)


def _top_real_data_plan_entry(value: object) -> str:
    candidates = [
        entry
        for entry in _dict_list(value)
        if str(entry.get("priority", "")) in {"high", "medium"}
    ]
    if not candidates:
        return ""
    candidates.sort(
        key=lambda entry: (
            {"high": 3, "medium": 2, "low": 1}.get(str(entry.get("priority", "")), 0),
            int(entry.get("fileCount", 0) or 0),
            str(entry.get("group", "")),
        ),
        reverse=True,
    )
    return _real_data_candidate_label(candidates[0])


def _top_replacement_candidate(value: object) -> str:
    candidates = _dict_list(value)
    if not candidates:
        return ""
    candidates.sort(key=lambda entry: int(entry.get("rank", 999999) or 999999))
    return _real_data_candidate_label(candidates[0], include_rank=True)


def _real_data_candidate_label(
    entry: dict[str, Any],
    *,
    include_rank: bool = False,
) -> str:
    parts = []
    if include_rank:
        parts.append(f"rank:{int(entry.get('rank', 0) or 0)}")
    parts.extend(
        [
            f"group:{entry.get('group', '')}",
            f"priority:{entry.get('priority', '')}",
            f"files:{int(entry.get('fileCount', 0) or 0)}",
            f"decision:{entry.get('decision', '')}",
        ]
    )
    return " ".join(str(part) for part in parts)


def _real_data_policy_text_parts(value: object) -> list[str]:
    if not isinstance(value, dict):
        return []
    parts = []
    status = value.get("status")
    if isinstance(status, str) and status:
        parts.append(f"policyStatus={status}")
    if "matchedReplacementGroups" in value:
        parts.append(
            "matchedReplacementGroups="
            f"{int(value.get('matchedReplacementGroups', 0) or 0)}"
        )
    if "failOnRegression" in value:
        fail_on_regression = str(bool(value.get("failOnRegression"))).lower()
        parts.append(f"failOnRegression={fail_on_regression}")
    failures = value.get("failures")
    if isinstance(failures, list):
        parts.append(f"policyFailures={len(failures)}")
    if "exitCode" in value:
        parts.append(f"policyExitCode={int(value.get('exitCode', 0) or 0)}")
    return parts


def _format_real_data_coverage_diff_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    left = report.get("left")
    if not isinstance(left, dict):
        left = {}
    right = report.get("right")
    if not isinstance(right, dict):
        right = {}
    parts = [
        str(report.get("status", "unknown")).upper(),
        "schema=edgp.real_data.coverage_diff.v1",
        f"left={_text_value(left.get('label', 'left'))}",
        f"right={_text_value(right.get('label', 'right'))}",
        (
            "publicEvidenceCoveragePercentDelta="
            f"{float(summary.get('publicEvidenceCoveragePercentDelta', 0.0) or 0.0):.2f}"
        ),
        f"publicEvidenceFilesDelta={int(summary.get('publicEvidenceFilesDelta', 0) or 0)}",
        f"directPublicSourcesDelta={int(summary.get('directPublicSourcesDelta', 0) or 0)}",
        (
            "generatedPublicReportsDelta="
            f"{int(summary.get('generatedPublicReportsDelta', 0) or 0)}"
        ),
        f"syntheticFilesDelta={int(summary.get('syntheticFilesDelta', 0) or 0)}",
        f"addedPublicEvidence={int(summary.get('addedPublicEvidence', 0) or 0)}",
        f"removedPublicEvidence={int(summary.get('removedPublicEvidence', 0) or 0)}",
        f"regressions={int(summary.get('regressions', 0) or 0)}",
    ]
    parts.extend(_real_data_policy_text_parts(report.get("policy")))
    return " ".join(parts)


def _format_real_data_replacement_plan_diff_result(report: dict[str, Any]) -> str:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    left = report.get("left")
    if not isinstance(left, dict):
        left = {}
    right = report.get("right")
    if not isinstance(right, dict):
        right = {}
    parts = [
        str(report.get("status", "unknown")).upper(),
        "schema=edgp.real_data.replacement_plan_diff.v1",
        f"left={_text_value(left.get('label', 'left'))}",
        f"right={_text_value(right.get('label', 'right'))}",
        (
            "replacementCandidatesDelta="
            f"{int(summary.get('replacementCandidatesDelta', 0) or 0)}"
        ),
        f"candidateFilesDelta={int(summary.get('candidateFilesDelta', 0) or 0)}",
        f"highPriorityGroupsDelta={int(summary.get('highPriorityGroupsDelta', 0) or 0)}",
        f"mediumPriorityGroupsDelta={int(summary.get('mediumPriorityGroupsDelta', 0) or 0)}",
        f"addedCandidates={int(summary.get('addedCandidates', 0) or 0)}",
        f"removedCandidates={int(summary.get('removedCandidates', 0) or 0)}",
        f"changedCandidates={int(summary.get('changedCandidates', 0) or 0)}",
        f"regressions={int(summary.get('regressions', 0) or 0)}",
    ]
    parts.extend(_real_data_policy_text_parts(report.get("policy")))
    return " ".join(parts)


def _print_graph_diff_bundle_result(
    index_path: Path,
    report: dict[str, Any],
    *,
    archive_output: Path | None = None,
    output_format: str = "path",
    fail_on_status: str | None = None,
) -> int:
    if output_format == "text":
        print(
            _format_graph_diff_bundle_result(
                index_path,
                report,
                archive_output=archive_output,
            )
        )
    else:
        print(index_path)
    if _bundle_triage_summary_should_fail(index_path.parent, min_status=fail_on_status):
        return 2
    if _diff_policy_failed(report):
        return 2
    return 0


def _print_graph_diff_tree_bundle_result(
    index_path: Path,
    report: dict[str, Any],
    *,
    archive_output: Path | None = None,
    output_format: str = "path",
    fail_on_status: str | None = None,
) -> int:
    if output_format == "text":
        print(
            _format_graph_diff_tree_bundle_result(
                index_path,
                report,
                archive_output=archive_output,
            )
        )
    else:
        print(index_path)
    if _bundle_triage_summary_should_fail(index_path.parent, min_status=fail_on_status):
        return 2
    if _diff_tree_policy_failed(report):
        return 2
    return 0


def _load_optional_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _real_data_coverage_policy_should_fail(output_dir: Path) -> bool:
    report = _load_optional_json(output_dir / "real-data-coverage.json")
    policy = report.get("policy")
    return isinstance(policy, dict) and policy.get("status") == "fail"


def _real_data_replacement_plan_policy_should_fail(output_dir: Path) -> bool:
    report = _load_optional_json(output_dir / "real-data-replacement-plan.json")
    policy = report.get("policy")
    return isinstance(policy, dict) and policy.get("status") == "fail"


def _real_data_replacement_plan_diff_policy_should_fail(output_dir: Path) -> bool:
    report = _load_optional_json(output_dir / "real-data-replacement-plan-diff.json")
    policy = report.get("policy")
    return isinstance(policy, dict) and policy.get("status") == "fail"


def _real_data_coverage_diff_policy_should_fail(output_dir: Path) -> bool:
    report = _load_optional_json(output_dir / "real-data-coverage-diff.json")
    policy = report.get("policy")
    return isinstance(policy, dict) and policy.get("status") == "fail"


def _bundle_triage_summary_should_fail(
    output_dir: Path,
    *,
    min_status: str | None = None,
) -> bool:
    if min_status is None:
        return False
    report_path = output_dir / "triage-summary.json"
    if not report_path.exists():
        return False
    return _triage_summary_should_fail(
        json.loads(report_path.read_text(encoding="utf-8")),
        min_status=min_status,
    )


def _validation_report_should_fail_on_status(
    report: dict[str, Any],
    *,
    min_status: str | None = None,
) -> bool:
    if min_status is None:
        return False
    triage_summary = report.get("triageSummary")
    if isinstance(triage_summary, dict):
        status = str(triage_summary.get("status", "pass")).lower()
    else:
        status = str(report.get("reportStatus", "pass")).lower()
    return _TRIAGE_STATUS_RANKS.get(status, 0) >= _TRIAGE_STATUS_RANKS[min_status]


def _submission_plan_should_fail_on_status(
    plan: dict[str, Any],
    *,
    min_status: str | None = None,
) -> bool:
    if min_status is None:
        return False
    triage_summary = plan.get("triageSummary")
    if not isinstance(triage_summary, dict):
        return False
    return _triage_summary_should_fail(triage_summary, min_status=min_status)


def _submission_plan_index_should_fail_on_status(
    index: dict[str, Any],
    *,
    min_status: str | None = None,
) -> bool:
    if min_status is None:
        return False
    plans = index.get("plans", [])
    if not isinstance(plans, list):
        return False
    threshold = _TRIAGE_STATUS_RANKS[min_status]
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        status = str(plan.get("triageStatus", "pass")).lower()
        if _TRIAGE_STATUS_RANKS.get(status, 0) >= threshold:
            return True
    return False


def _attach_diff_tree_policy(
    report: dict[str, Any],
    *,
    fail_on_kind: Sequence[str] = (),
) -> dict[str, Any]:
    requested_kinds = _unique_diff_tree_change_kinds(fail_on_kind)
    if requested_kinds:
        report["policy"] = _diff_tree_policy_verdict(
            report,
            fail_on_kind=requested_kinds,
        )
    return report


def _attach_diff_policy(
    report: dict[str, Any],
    *,
    fail_on_change: Sequence[str] = (),
    fail_on_kind: Sequence[str] = (),
) -> dict[str, Any]:
    requested_changes = _unique_diff_change_kinds(fail_on_change)
    requested_kinds = _unique_diff_tree_change_kinds(fail_on_kind)
    if requested_changes or requested_kinds:
        report["policy"] = _diff_policy_verdict(
            report,
            fail_on_change=requested_changes,
            fail_on_kind=requested_kinds,
        )
    return report


def _diff_policy_verdict(
    report: dict[str, Any],
    *,
    fail_on_change: Sequence[str] = (),
    fail_on_kind: Sequence[str] = (),
) -> dict[str, Any]:
    requested_changes = _unique_diff_change_kinds(fail_on_change)
    requested_kinds = _unique_diff_tree_change_kinds(fail_on_kind)
    observed_changes = _diff_change_kinds(report)
    observed_kinds = _diff_tree_classification_kinds(report)
    matched_changes = [
        change for change in requested_changes if change in observed_changes
    ]
    matched_kinds = [kind for kind in requested_kinds if kind in observed_kinds]
    failed = bool(matched_changes or matched_kinds)
    policy: dict[str, Any] = {
        "status": "fail" if failed else "pass",
        "exitCode": 2 if failed else 0,
    }
    if requested_changes:
        policy["failOnChange"] = requested_changes
        policy["matchedChanges"] = matched_changes
    if requested_kinds:
        policy["failOnKind"] = requested_kinds
        policy["matchedKinds"] = matched_kinds
    return policy


def _unique_diff_change_kinds(kinds: Sequence[str]) -> list[str]:
    unique: list[str] = []
    for kind in kinds:
        if kind not in unique:
            unique.append(kind)
    return unique


def _diff_change_kinds(report: dict[str, Any]) -> set[str]:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return set()
    checks = {
        "added-node": "addedNodes",
        "removed-node": "removedNodes",
        "added-edge": "addedEdges",
        "removed-edge": "removedEdges",
        "metadata-change": "metadataChangedNodes",
    }
    return {
        change
        for change, summary_key in checks.items()
        if int(summary.get(summary_key, 0) or 0) > 0
    }


def _diff_tree_policy_verdict(
    report: dict[str, Any],
    *,
    fail_on_kind: Sequence[str] = (),
) -> dict[str, Any]:
    requested_kinds = _unique_diff_tree_change_kinds(fail_on_kind)
    if not requested_kinds:
        return {
            "failOnKind": [],
            "matchedKinds": [],
            "status": "pass",
            "exitCode": 0,
        }
    observed_kinds = _diff_tree_classification_kinds(report)
    matched_kinds = [kind for kind in requested_kinds if kind in observed_kinds]
    failed = bool(matched_kinds)
    return {
        "failOnKind": requested_kinds,
        "matchedKinds": matched_kinds,
        "status": "fail" if failed else "pass",
        "exitCode": 2 if failed else 0,
    }


def _unique_diff_tree_change_kinds(kinds: Sequence[str]) -> list[str]:
    unique: list[str] = []
    for kind in kinds:
        if kind not in unique:
            unique.append(kind)
    return unique


def _diff_tree_classification_kinds(report: dict[str, Any]) -> set[str]:
    classifications = report.get("classifications", [])
    if not isinstance(classifications, list):
        return set()
    return {
        str(change["kind"])
        for change in classifications
        if isinstance(change, dict) and isinstance(change.get("kind"), str)
    }


def _diff_tree_policy_failed(report: dict[str, Any]) -> bool:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return False
    return policy.get("status") == "fail"


def _diff_policy_failed(report: dict[str, Any]) -> bool:
    policy = report.get("policy")
    if not isinstance(policy, dict):
        return False
    return policy.get("status") == "fail"


def _bundle_license_report_should_fail(output_dir: Path) -> bool:
    report_path = output_dir / "license-report.json"
    if not report_path.exists():
        return False
    return _license_report_should_fail(
        json.loads(report_path.read_text(encoding="utf-8"))
    )


def _build_rpm_repo_diff_report(
    left_source: str,
    right_source: str,
    *,
    left_repo_id: str = "left-rpm-repository",
    right_repo_id: str = "right-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
) -> dict[str, Any]:
    left = _load_rpm_repo_project_graph(
        left_source,
        repo_id=left_repo_id,
        package_limit=package_limit,
        requirement_limit=requirement_limit,
    )
    right = _load_rpm_repo_project_graph(
        right_source,
        repo_id=right_repo_id,
        package_limit=package_limit,
        requirement_limit=requirement_limit,
    )
    return build_rpm_repository_diff_report(
        left.graph,
        right.graph,
        left_root=left.root_identifier,
        right_root=right.root_identifier,
    )


def _write_rpm_repo_diff_bundle(
    left_source: str,
    right_source: str,
    output_dir: Path,
    *,
    left_repo_id: str = "left-rpm-repository",
    right_repo_id: str = "right-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    diff_path = output_dir / "rpm-repository-diff.json"
    diff_path.write_text(
        _json(
            _build_rpm_repo_diff_report(
                left_source,
                right_source,
                left_repo_id=left_repo_id,
                right_repo_id=right_repo_id,
                package_limit=package_limit,
                requirement_limit=requirement_limit,
            )
        ),
        encoding="utf-8",
    )
    return write_report_bundle(
        [diff_path],
        output_dir,
        bundle_metadata={"sourceKind": "rpm-repository-diff", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_albs_build_diff_bundle(
    output_dir: Path,
    *,
    left_build_id: str | None = None,
    left_path: Path | None = None,
    left_url: str | None = None,
    right_build_id: str | None = None,
    right_path: Path | None = None,
    right_url: str | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    left = _load_albs_build_metadata(
        build_id=left_build_id,
        path=left_path,
        url=left_url,
        base_url=base_url,
    )
    right = _load_albs_build_metadata(
        build_id=right_build_id,
        path=right_path,
        url=right_url,
        base_url=base_url,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    diff_path = output_dir / "albs-build-diff.json"
    diff_path.write_text(
        _json(build_albs_build_diff_report(left, right)),
        encoding="utf-8",
    )
    return write_report_bundle(
        [diff_path],
        output_dir,
        bundle_metadata={"sourceKind": "albs-build-diff", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_albs_log_intelligence_bundle(
    output_dir: Path,
    *,
    build_id: str | None = None,
    path: Path | None = None,
    url: str | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    payload = _load_albs_build_metadata(
        build_id=build_id,
        path=path,
        url=url,
        base_url=base_url,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "albs-log-intelligence.json"
    report_path.write_text(
        _json(build_albs_log_intelligence_report(payload)),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "albs-log-intelligence", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_albs_release_completeness_bundle(
    output_dir: Path,
    *,
    build_ids: list[str] | None = None,
    paths: list[Path] | None = None,
    urls: list[str] | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    payloads = _load_albs_build_metadata_list(
        build_ids=build_ids or [],
        paths=paths or [],
        urls=urls or [],
        base_url=base_url,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "albs-release-completeness.json"
    report_path.write_text(
        _json(build_albs_release_completeness_report(payloads)),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={
            "sourceKind": "albs-release-completeness",
            "command": command,
        },
        include_triage_summary=include_triage_summary,
    )


def _write_libsolv_bundle(
    transaction_path: Path,
    output_dir: Path,
    *,
    graph_snapshot_path: Path | None = None,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "libsolv-bridge.json"
    report_path.write_text(
        _json(build_libsolv_bridge_report(transaction_path, graph_snapshot_path)),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "libsolv-transaction", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_public_advisory_feed_bundle(
    output_dir: Path,
    *,
    path: Path | None = None,
    url: str | None = None,
    ecosystem: str = "rpm",
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "public-advisory-feed.json"
    report_path.write_text(
        _json(
            build_public_advisory_feed_report(
                _load_public_json_source(path=path, url=url),
                ecosystem=ecosystem,
            )
        ),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "public-advisory-feed", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_fixture_provenance_bundle(
    output_dir: Path,
    *,
    fixture_dir: Path,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "fixture-provenance.json"
    report_path.write_text(
        _json(build_fixture_provenance(fixture_dir)),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "fixture-provenance", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_real_data_coverage_bundle(
    output_dir: Path,
    *,
    fixture_dir: Path,
    min_public_evidence_percent: float | None = None,
    fail_on_priority: str | None = None,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "real-data-coverage.json"
    report_path.write_text(
        _json(
            build_real_data_coverage_report(
                build_fixture_provenance(fixture_dir),
                min_public_evidence_percent=min_public_evidence_percent,
                fail_on_priority=fail_on_priority,
            )
        ),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "real-data-coverage", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _real_data_replacement_plan_input_report(
    *,
    coverage_path: Path | None,
    fixture_dir: Path | None,
    fail_on_priority: str | None = None,
) -> dict[str, Any]:
    if coverage_path is not None:
        coverage = _load_real_data_coverage_report(coverage_path)
    else:
        coverage = build_real_data_coverage_report(
            build_fixture_provenance(fixture_dir or Path("tests/fixtures"))
        )
    return build_real_data_replacement_plan_report(
        coverage,
        fail_on_priority=fail_on_priority,
    )


def _load_real_data_replacement_plan_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _real_data_replacement_plan_diff_input_report(
    *,
    plan_path: Path | None,
    coverage_path: Path | None,
    fixture_dir: Path | None,
) -> dict[str, Any]:
    if plan_path is not None:
        return _load_real_data_replacement_plan_report(plan_path)
    if coverage_path is not None or fixture_dir is not None:
        return _real_data_replacement_plan_input_report(
            coverage_path=coverage_path,
            fixture_dir=fixture_dir,
        )
    raise ValueError("replacement plan diff requires a plan, coverage, or fixture dir")


def _write_real_data_replacement_plan_diff_bundle(
    output_dir: Path,
    *,
    left_report: dict[str, Any],
    right_report: dict[str, Any],
    left_label: str = "left",
    right_label: str = "right",
    fail_on_regression: bool = False,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "real-data-replacement-plan-diff.json"
    report_path.write_text(
        _json(
            build_real_data_replacement_plan_diff_report(
                left_report,
                right_report,
                left_label=left_label,
                right_label=right_label,
                fail_on_regression=fail_on_regression,
            )
        ),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={
            "sourceKind": "real-data-replacement-plan-diff",
            "command": command,
        },
        include_triage_summary=include_triage_summary,
    )


def _write_real_data_replacement_plan_bundle(
    output_dir: Path,
    *,
    coverage_path: Path | None = None,
    fixture_dir: Path | None = None,
    fail_on_priority: str | None = None,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "real-data-replacement-plan.json"
    report_path.write_text(
        _json(
            _real_data_replacement_plan_input_report(
                coverage_path=coverage_path,
                fixture_dir=fixture_dir,
                fail_on_priority=fail_on_priority,
            )
        ),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={
            "sourceKind": "real-data-replacement-plan",
            "command": command,
        },
        include_triage_summary=include_triage_summary,
    )


def _load_real_data_coverage_report(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _real_data_coverage_input_report(
    *,
    report_path: Path | None,
    fixture_dir: Path | None,
) -> dict[str, Any]:
    if fixture_dir is not None:
        return build_real_data_coverage_report(build_fixture_provenance(fixture_dir))
    if report_path is None:
        raise ValueError("real-data coverage diff requires a report or fixture dir")
    return _load_real_data_coverage_report(report_path)


def _write_real_data_coverage_diff_bundle(
    output_dir: Path,
    *,
    left_report: dict[str, Any],
    right_report: dict[str, Any],
    left_label: str = "left",
    right_label: str = "right",
    fail_on_regression: bool = False,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "real-data-coverage-diff.json"
    report_path.write_text(
        _json(
            build_real_data_coverage_diff_report(
                left_report,
                right_report,
                left_label=left_label,
                right_label=right_label,
                fail_on_regression=fail_on_regression,
            )
        ),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "real-data-coverage-diff", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_graph_diff_bundle(
    left_path: Path,
    right_path: Path,
    output_dir: Path,
    *,
    command: str | None = None,
    include_triage_summary: bool = False,
    fail_on_change: Sequence[str] = (),
    fail_on_kind: Sequence[str] = (),
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "graph-diff.json"
    report = json.loads(diff_snapshot_files(left_path, right_path))
    _attach_diff_policy(
        report,
        fail_on_change=fail_on_change,
        fail_on_kind=fail_on_kind,
    )
    report_path.write_text(
        _json(report),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "graph-diff", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_graph_diff_tree_bundle(
    left_path: Path,
    right_path: Path,
    output_dir: Path,
    *,
    selector: str | None,
    left_selector: str | None,
    right_selector: str | None,
    direction: str,
    depth: int,
    command: str | None = None,
    include_triage_summary: bool = False,
    fail_on_kind: Sequence[str] = (),
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "graph-diff-tree.json"
    report = json.loads(
        diff_tree_snapshot_files(
            left_path,
            right_path,
            selector=selector,
            left_selector=left_selector,
            right_selector=right_selector,
            direction=direction,
            depth=depth,
        )
    )
    _attach_diff_tree_policy(report, fail_on_kind=fail_on_kind)
    report_path.write_text(
        _json(report),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "graph-diff-tree", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_license_report_bundle(
    output_dir: Path,
    *,
    source: str,
    path: Path | None = None,
    albs_url: str | None = None,
    ecosystem: str = "npm",
    denied_licenses: Sequence[str] = (),
    rpm_limit: int = 100,
    max_requirements: int = 40,
    rpm_repo_source: str | None = None,
    repo_id: str = "public-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    root_identifier, graph, resolved_ecosystem = _load_source_project_graph(
        source,
        path,
        ecosystem,
        albs_url=albs_url,
        rpm_limit=rpm_limit,
        max_requirements=max_requirements,
        rpm_repo_source=rpm_repo_source,
        repo_id=repo_id,
        package_limit=package_limit,
        requirement_limit=requirement_limit,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "license-report.json"
    report_path.write_text(
        _json(
            build_license_report(
                graph,
                root=root_identifier,
                ecosystem=resolved_ecosystem,
                denied_licenses=denied_licenses,
            )
        ),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "license-report", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_advisory_report_bundle(
    output_dir: Path,
    *,
    source: str,
    path: Path | None = None,
    albs_url: str | None = None,
    ecosystem: str = "npm",
    advisory_path: Path | None = None,
    public_advisory_feed_path: Path | None = None,
    public_advisory_feed_url: str | None = None,
    max_paths: int = 20,
    rpm_limit: int = 100,
    max_requirements: int = 40,
    rpm_repo_source: str | None = None,
    repo_id: str = "public-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    root_identifier, graph, resolved_ecosystem = _load_source_project_graph(
        source,
        path,
        ecosystem,
        albs_url=albs_url,
        rpm_limit=rpm_limit,
        max_requirements=max_requirements,
        rpm_repo_source=rpm_repo_source,
        repo_id=repo_id,
        package_limit=package_limit,
        requirement_limit=requirement_limit,
    )
    report = build_advisory_report(
        _load_advisory_payload(
            advisory_path=advisory_path,
            public_advisory_feed_path=public_advisory_feed_path,
            public_advisory_feed_url=public_advisory_feed_url,
            ecosystem=resolved_ecosystem,
        ),
        graph,
        root=root_identifier,
        ecosystem=resolved_ecosystem,
        max_paths=max_paths,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "advisory-report.json"
    report_path.write_text(_json(report), encoding="utf-8")
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "advisory-report", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_impact_report_bundle(
    output_dir: Path,
    *,
    source: str,
    path: Path | None = None,
    albs_url: str | None = None,
    ecosystem: str = "npm",
    node: str,
    max_paths: int = 20,
    rpm_limit: int = 100,
    max_requirements: int = 40,
    rpm_repo_source: str | None = None,
    repo_id: str = "public-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    root_identifier, graph, resolved_ecosystem = _load_source_project_graph(
        source,
        path,
        ecosystem,
        albs_url=albs_url,
        rpm_limit=rpm_limit,
        max_requirements=max_requirements,
        rpm_repo_source=rpm_repo_source,
        repo_id=repo_id,
        package_limit=package_limit,
        requirement_limit=requirement_limit,
    )
    resolved_node = _resolve_impact_node(graph, node)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "impact-report.json"
    report_path.write_text(
        _json(
            build_impact_report(
                graph,
                node=resolved_node,
                root=root_identifier,
                ecosystem=resolved_ecosystem,
                max_paths=max_paths,
            )
        ),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "impact-report", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_performance_report_bundle(
    output_dir: Path,
    *,
    scenarios: Sequence[tuple[int, int]],
    backend: str = "python",
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "performance-report.json"
    report_path.write_text(
        _json(build_performance_report(scenarios, backend=backend)),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "performance-report", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_query_report_bundle(
    output_dir: Path,
    *,
    source: str,
    path: Path | None = None,
    albs_url: str | None = None,
    ecosystem: str = "npm",
    operation: str,
    node: str | None = None,
    target: str | None = None,
    direction: str = "dependencies",
    limit: int = 10,
    rpm_limit: int = 100,
    max_requirements: int = 40,
    rpm_repo_source: str | None = None,
    repo_id: str = "public-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    root_identifier, graph, resolved_ecosystem = _load_source_project_graph(
        source,
        path,
        ecosystem,
        albs_url=albs_url,
        rpm_limit=rpm_limit,
        max_requirements=max_requirements,
        rpm_repo_source=rpm_repo_source,
        repo_id=repo_id,
        package_limit=package_limit,
        requirement_limit=requirement_limit,
    )
    query_result = _query_graph(
        graph,
        operation=operation,
        node=node,
        target=target,
        direction=direction,
        limit=limit,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "query-report.json"
    report_path.write_text(
        _json(
            build_query_report(
                query_result,
                source=source,
                root=root_identifier,
                ecosystem=resolved_ecosystem,
                limit=limit,
            )
        ),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "query-report", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_bundle_catalog_bundle(
    output_dir: Path,
    *,
    bundle_dirs: Sequence[Path],
    manifest_name: str = "manifest.json",
    archive_output: Path | None = None,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "bundle-catalog.json"
    report_path.write_text(
        _json(
            build_bundle_catalog_report(
                bundle_dirs,
                manifest_name=manifest_name,
            )
        ),
        encoding="utf-8",
    )
    index_path = write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "bundle-catalog", "command": command},
        include_triage_summary=include_triage_summary,
    )
    if archive_output is not None:
        archive_report = write_report_bundle_archive(
            output_dir,
            archive_output,
            manifest_name=manifest_name,
        )
        if archive_report.get("ok") is not True:
            raise ValueError("Could not archive generated bundle catalog")
    return index_path


def _write_rpm_albs_provenance_bundle(
    output_dir: Path,
    *,
    build_id: str | None = None,
    path: Path | None = None,
    url: str | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
    rpm_limit: int = 100,
    max_requirements: int = 40,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    albs_payload = _load_albs_build_metadata(
        build_id=build_id,
        path=path,
        url=url,
        base_url=base_url,
    )
    installed = InstalledRpmAdapter().parse_installed(
        limit=rpm_limit,
        max_requirements=max_requirements,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "rpm-albs-provenance.json"
    report_path.write_text(
        _json(build_rpm_albs_provenance_report(installed.graph, albs_payload)),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "rpm-albs-provenance", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _load_albs_build_project_graph(
    *,
    build_id: str | None = None,
    path: Path | None = None,
    url: str | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
    task_limit: int = 50,
    artifact_limit: int = 200,
    test_task_limit: int = 50,
    include_logs: bool = False,
) -> tuple[str, CSRDependencyGraph, str]:
    adapter = AlbsBuildAdapter()
    if path is not None:
        resolved = adapter.parse_file(
            path,
            base_url=base_url,
            task_limit=task_limit,
            artifact_limit=artifact_limit,
            test_task_limit=test_task_limit,
            include_logs=include_logs,
        )
    elif url is not None:
        resolved = adapter.parse_url(
            url,
            base_url=base_url,
            task_limit=task_limit,
            artifact_limit=artifact_limit,
            test_task_limit=test_task_limit,
            include_logs=include_logs,
        )
    elif build_id is not None:
        resolved = adapter.parse_build(
            build_id,
            base_url=base_url,
            task_limit=task_limit,
            artifact_limit=artifact_limit,
            test_task_limit=test_task_limit,
            include_logs=include_logs,
        )
    else:
        raise ValueError(
            "Either --build-id, --path, or --url is required for ALBS build input"
        )
    return resolved.root_identifier, resolved.graph, resolved.ecosystem


def _load_albs_build_metadata(
    *,
    build_id: str | None = None,
    path: Path | None = None,
    url: str | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
) -> dict[str, Any]:
    adapter = AlbsBuildAdapter()
    sources = sum(source is not None for source in (build_id, path, url))
    if sources != 1:
        raise ValueError("Exactly one ALBS --build-id, --path, or --url is required")
    if path is not None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"ALBS build fixture must be a JSON object: {path}")
        return payload
    if url is not None:
        return adapter.fetch_metadata_url(url)
    if build_id is not None:
        return adapter.fetch_build_metadata(build_id, base_url=base_url)
    raise ValueError("Exactly one ALBS --build-id, --path, or --url is required")


def _load_albs_build_metadata_list(
    *,
    build_ids: Sequence[str],
    paths: Sequence[Path],
    urls: Sequence[str],
    base_url: str = DEFAULT_ALBS_BASE_URL,
) -> list[dict[str, Any]]:
    payloads = [
        _load_albs_build_metadata(path=path, base_url=base_url)
        for path in paths
    ]
    payloads.extend(
        _load_albs_build_metadata(url=url, base_url=base_url)
        for url in urls
    )
    payloads.extend(
        _load_albs_build_metadata(build_id=build_id, base_url=base_url)
        for build_id in build_ids
    )
    if not payloads:
        raise ValueError("At least one ALBS --path, --url, or --build-id is required")
    return payloads


def _write_albs_build_bundle(
    output_dir: Path,
    *,
    build_id: str | None = None,
    path: Path | None = None,
    url: str | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
    task_limit: int = 50,
    artifact_limit: int = 200,
    test_task_limit: int = 50,
    include_logs: bool = False,
    impact_nodes: list[str] | None = None,
    max_paths: int = 20,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    payload = _load_albs_build_metadata(
        build_id=build_id,
        path=path,
        url=url,
        base_url=base_url,
    )
    resolved = AlbsBuildAdapter().parse_metadata(
        payload,
        base_url=base_url,
        task_limit=task_limit,
        artifact_limit=artifact_limit,
        test_task_limit=test_task_limit,
        include_logs=include_logs,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = output_dir / "albs-artifact-inventory.json"
    inventory_path.write_text(
        _json(build_albs_artifact_inventory(resolved.graph, root=resolved.root_identifier)),
        encoding="utf-8",
    )
    timing_path = output_dir / "albs-build-timing.json"
    timing_path.write_text(
        _json(build_albs_build_timing_report(payload, root=resolved.root_identifier)),
        encoding="utf-8",
    )
    return write_graph_report_bundle(
        resolved=resolved,
        output_dir=output_dir,
        graph_name="albs-build-graph",
        impact_nodes=impact_nodes,
        node_resolver=_resolve_impact_node,
        max_paths=max_paths,
        extra_reports_after_graph=[inventory_path, timing_path],
        bundle_metadata={"sourceKind": "albs-build", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_albs_artifact_inventory_bundle(
    output_dir: Path,
    *,
    build_id: str | None = None,
    path: Path | None = None,
    url: str | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
    task_limit: int = 50,
    artifact_limit: int = 200,
    test_task_limit: int = 50,
    include_logs: bool = False,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    root_identifier, graph, _ = _load_albs_build_project_graph(
        build_id=build_id,
        path=path,
        url=url,
        base_url=base_url,
        task_limit=task_limit,
        artifact_limit=artifact_limit,
        test_task_limit=test_task_limit,
        include_logs=include_logs,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "albs-artifact-inventory.json"
    report_path.write_text(
        _json(build_albs_artifact_inventory(graph, root=root_identifier)),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={
            "sourceKind": "albs-artifact-inventory",
            "command": command,
        },
        include_triage_summary=include_triage_summary,
    )


def _write_albs_build_timing_bundle(
    output_dir: Path,
    *,
    build_id: str | None = None,
    path: Path | None = None,
    url: str | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    payload = _load_albs_build_metadata(
        build_id=build_id,
        path=path,
        url=url,
        base_url=base_url,
    )
    build_id_value = str(payload.get("build_id") or payload.get("id") or "unknown")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "albs-build-timing.json"
    report_path.write_text(
        _json(
            build_albs_build_timing_report(
                payload,
                root=f"albs-build:{build_id_value}",
            )
        ),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "albs-build-timing", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _load_public_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_public_json_url(url: str) -> object:
    request = Request(url, headers={"User-Agent": "edgp-public-advisory-feed/0.1"})
    with urlopen(request, timeout=30.0) as response:
        return json.loads(response.read().decode("utf-8"))


def _load_public_json_source(
    *,
    path: Path | None = None,
    url: str | None = None,
) -> object:
    if (path is None) == (url is None):
        raise ValueError("Exactly one public advisory feed source is required")
    if url is not None:
        return _load_public_json_url(url)
    if path is None:
        raise ValueError("Public advisory feed path is required")
    return _load_public_json(path)


def _load_advisory_payload(
    *,
    advisory_path: Path | None = None,
    public_advisory_feed_path: Path | None = None,
    public_advisory_feed_url: str | None = None,
    ecosystem: str,
) -> object:
    source_count = sum(
        value is not None
        for value in (
            advisory_path,
            public_advisory_feed_path,
            public_advisory_feed_url,
        )
    )
    if source_count != 1:
        raise ValueError(
            "Exactly one of --advisories, --public-advisory-feed, "
            "or --public-advisory-feed-url is required"
        )
    if advisory_path is not None:
        return _load_public_json(advisory_path)
    public_feed_report = build_public_advisory_feed_report(
        _load_public_json_source(
            path=public_advisory_feed_path,
            url=public_advisory_feed_url,
        ),
        ecosystem=ecosystem,
    )
    return public_feed_report["overlay"]


_ADVISORY_SEVERITY_RANKS = {
    "unknown": 0,
    "low": 1,
    "medium": 2,
    "moderate": 2,
    "high": 3,
    "critical": 4,
}


def _advisory_report_should_fail(
    report: dict[str, object],
    *,
    min_severity: str = "unknown",
) -> bool:
    threshold = _ADVISORY_SEVERITY_RANKS[min_severity]
    findings = report.get("findings", [])
    if not isinstance(findings, list):
        return False
    return any(_finding_severity_rank(finding) >= threshold for finding in findings)


def _finding_severity_rank(finding: object) -> int:
    if not isinstance(finding, dict):
        return 0
    advisory = finding.get("advisory", {})
    if not isinstance(advisory, dict):
        return 0
    return _severity_rank(advisory.get("severity"))


def _severity_rank(severity: object) -> int:
    normalized = str(severity or "unknown").strip().lower()
    if normalized in _ADVISORY_SEVERITY_RANKS:
        return _ADVISORY_SEVERITY_RANKS[normalized]
    try:
        return _cvss_score_rank(float(normalized))
    except ValueError:
        return 0


def _cvss_score_rank(score: float) -> int:
    if score <= 0:
        return 0
    if score < 4.0:
        return _ADVISORY_SEVERITY_RANKS["low"]
    if score < 7.0:
        return _ADVISORY_SEVERITY_RANKS["medium"]
    if score < 9.0:
        return _ADVISORY_SEVERITY_RANKS["high"]
    return _ADVISORY_SEVERITY_RANKS["critical"]


def _license_report_should_fail(report: dict[str, Any]) -> bool:
    summary = report.get("summary", {})
    if not isinstance(summary, dict):
        return False
    return int(summary.get("deniedFindings", 0)) > 0


_TRIAGE_STATUS_RANKS = {
    "pass": 0,
    "warn": 1,
    "fail": 2,
}


def _triage_summary_should_fail(
    report: dict[str, Any],
    *,
    min_status: str | None = None,
) -> bool:
    if min_status is None:
        return False
    status = str(report.get("status", "pass")).lower()
    return _TRIAGE_STATUS_RANKS.get(status, 0) >= _TRIAGE_STATUS_RANKS[min_status]


def _performance_scenarios(values: Sequence[str], *, nodes: int, fanout: int) -> list[tuple[int, int]]:
    if not values:
        return [(nodes, fanout)]
    scenarios = []
    for value in values:
        left, separator, right = value.partition(":")
        if not separator:
            raise ValueError("--scenario must use NODES:FANOUT")
        scenarios.append((int(left), int(right)))
    return scenarios


def _parallel_query_specs(values: Sequence[str]) -> list[dict[str, str]]:
    if not values:
        raise ValueError("parallel-query requires at least one --query")
    queries = []
    for value in values:
        direction, separator, node = value.partition(":")
        if not separator or not node:
            raise ValueError("--query must use dependencies:NODE or dependents:NODE")
        queries.append({"direction": direction, "node": node})
    return queries


def _rpm_repo_source(primary: Path | None, source: str | None) -> str:
    if source:
        return source
    if primary is not None:
        return str(primary)
    raise ValueError("Either --source or --primary is required for RPM repository input")


def _rpm_repo_diff_source(primary: Path | None, source: str | None, side: str) -> str:
    if source:
        return source
    if primary is not None:
        return str(primary)
    raise ValueError(f"Either --{side}-source or --{side}-primary is required")


def _load_lockfile_graph(path: Path, ecosystem: str) -> tuple[str, CSRDependencyGraph]:
    root, graph, _ = _load_lockfile_project_graph(path, ecosystem)
    return root, graph


def _load_lockfile_project_graph(
    path: Path, ecosystem: str
) -> tuple[str, CSRDependencyGraph, str]:
    if ecosystem != "npm":
        if ecosystem == "poetry":
            resolved = PoetryAdapter().parse_lockfile_graph(path)
            return resolved.root_identifier, resolved.graph, resolved.ecosystem
        if ecosystem == "cargo":
            resolved = CargoAdapter().parse_lockfile_graph(path)
            return resolved.root_identifier, resolved.graph, resolved.ecosystem
        else:
            raise ValueError(f"Unsupported lockfile ecosystem: {ecosystem}")
    resolved = NpmAdapter().parse_lockfile_graph(path)
    return resolved.root_identifier, resolved.graph, resolved.ecosystem


def _load_source_graph(
    source: str,
    path: Path | None,
    ecosystem: str,
    *,
    albs_url: str | None = None,
    rpm_limit: int = 100,
    max_requirements: int = 40,
    rpm_repo_source: str | None = None,
    repo_id: str = "public-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
) -> tuple[str, CSRDependencyGraph]:
    root, graph, _ = _load_source_project_graph(
        source,
        path,
        ecosystem,
        albs_url=albs_url,
        rpm_limit=rpm_limit,
        max_requirements=max_requirements,
        rpm_repo_source=rpm_repo_source,
        repo_id=repo_id,
        package_limit=package_limit,
        requirement_limit=requirement_limit,
    )
    return root, graph


def _load_source_project_graph(
    source: str,
    path: Path | None,
    ecosystem: str,
    *,
    albs_url: str | None = None,
    rpm_limit: int = 100,
    max_requirements: int = 40,
    rpm_repo_source: str | None = None,
    repo_id: str = "public-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
) -> tuple[str, CSRDependencyGraph, str]:
    if albs_url is not None and source != "albs-build":
        raise ValueError("--albs-url is only valid for albs-build source")
    if source == "lockfile":
        if path is None:
            raise ValueError("--path is required for lockfile source")
        return _load_lockfile_project_graph(path, ecosystem)
    if source == "dot":
        if path is None:
            raise ValueError("--path is required for dot source")
        resolved = DotAdapter().parse_graph(path, ecosystem=ecosystem)
        return resolved.root_identifier, resolved.graph, resolved.ecosystem
    if source == "sbom":
        if path is None:
            raise ValueError("--path is required for sbom source")
        resolved = CycloneDXAdapter().parse_graph(path)
        return resolved.root_identifier, resolved.graph, resolved.ecosystem
    if source == "maven-tree":
        if path is None:
            raise ValueError("--path is required for maven-tree source")
        resolved = MavenTreeAdapter().parse_tree(path)
        return resolved.root_identifier, resolved.graph, resolved.ecosystem
    if source == "rpm-installed":
        resolved = InstalledRpmAdapter().parse_installed(
            limit=rpm_limit,
            max_requirements=max_requirements,
        )
        return resolved.root_identifier, resolved.graph, resolved.ecosystem
    if source == "rpm-repo":
        resolved = _load_rpm_repo_project_graph(
            _source_path_or_value(
                path,
                rpm_repo_source,
                "--path or --rpm-repo-source is required for rpm-repo source",
            ),
            repo_id=repo_id,
            package_limit=package_limit,
            requirement_limit=requirement_limit,
        )
        return resolved.root_identifier, resolved.graph, resolved.ecosystem
    if source == "albs-build":
        if path is None and albs_url is None:
            raise ValueError("--path or --albs-url is required for albs-build source")
        if path is not None and albs_url is not None:
            raise ValueError(
                "Use only one of --path or --albs-url for albs-build source"
            )
        return _load_albs_build_project_graph(path=path, url=albs_url)
    raise ValueError(f"Unsupported graph source: {source}")


def _source_path_or_value(
    path: Path | None,
    source_value: str | None,
    error: str,
) -> str:
    if source_value:
        return source_value
    if path is not None:
        return str(path)
    raise ValueError(error)


def _query_graph(
    graph: CSRDependencyGraph,
    *,
    operation: str,
    node: str | None,
    target: str | None,
    direction: str,
    limit: int,
) -> dict[str, Any]:
    if operation == "most-depended-upon":
        return {
            "operation": operation,
            "result": [
                {"package": package_id, "dependents": count}
                for package_id, count in graph.most_depended_upon(limit)
            ],
        }

    if node is None:
        raise ValueError(f"--node is required for {operation}")

    requested_node = node
    node = _resolve_node_selector(graph, node, role="node")
    requested_target = target
    if target is not None:
        target = _resolve_node_selector(graph, target, role="target")

    if operation == "dependencies":
        result = graph.get_dependencies(node)
        output_direction = "dependencies"
    elif operation == "dependents":
        result = graph.get_dependents(node)
        output_direction = "dependents"
    elif operation == "reachable":
        if direction == "dependents":
            result = graph.reachable_dependents(node)
        else:
            result = graph.reachable_dependencies(node)
        output_direction = direction
    elif operation == "path":
        if target is None:
            raise ValueError("--target is required for path")
        result = graph.shortest_dependency_path(
            node,
            target,
            reverse=direction == "dependents",
        )
        output_direction = direction
    else:
        raise ValueError(f"Unsupported query operation: {operation}")

    return {
        "direction": output_direction,
        "node": node,
        "operation": operation,
        "result": result,
        **({"requestedNode": requested_node} if requested_node != node else {}),
        **(
            {"target": target, "requestedTarget": requested_target}
            if operation == "path" and requested_target != target
            else {"target": target}
            if operation == "path"
            else {}
        ),
    }


def _resolve_node_selector(graph: CSRDependencyGraph, selector: str, *, role: str) -> str:
    if selector in graph.vertex_map:
        return selector

    matches = [
        package_id
        for package_id in sorted(graph.vertex_map)
        if package_id.partition("==")[0] == selector
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        rendered = ", ".join(matches)
        raise ValueError(f"Ambiguous {role} selector {selector!r}; candidates: {rendered}")
    return selector


def _resolve_impact_node(graph: CSRDependencyGraph, selector: str) -> str:
    return _resolve_node_selector(graph, selector, role="impact node")


def _add_rpm_repo_source_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--rpm-repo-source",
        help="RPM repository primary.xml, repomd.xml, or base URL for --source rpm-repo",
    )
    parser.add_argument("--repo-id", default="public-rpm-repository")
    parser.add_argument("--package-limit", type=int, default=5000)
    parser.add_argument("--requirement-limit", type=int, default=40)


def _add_albs_graph_source_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--albs-url",
        help="public ALBS build metadata URL for --source albs-build",
    )


def _add_license_bundle_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--license-report", action="store_true")
    parser.add_argument("--deny-license", action="append", default=[])
    parser.add_argument("--fail-on-denied", action="store_true")


def _add_triage_bundle_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--triage-summary",
        action="store_true",
        help="include generated triage-summary JSON and HTML artifacts in the bundle",
    )
    parser.add_argument(
        "--fail-on-status",
        choices=["warn", "fail"],
        help=(
            "include a triage summary and return status 2 when it reaches this "
            "severity"
        ),
    )


def _include_triage_summary(args: argparse.Namespace) -> bool:
    return bool(args.triage_summary or args.fail_on_status is not None)


def _diff_tree_selector_args(args: argparse.Namespace) -> tuple[str | None, str | None, str | None]:
    selector = getattr(args, "node", None)
    left_selector = getattr(args, "left_node", None)
    right_selector = getattr(args, "right_node", None)
    has_selector = bool(selector)
    has_explicit = bool(left_selector or right_selector)
    if has_selector and has_explicit:
        raise ValueError("use either --node or --left-node/--right-node")
    if not has_selector and not has_explicit:
        raise ValueError("diff-tree requires --node or --left-node/--right-node")
    if has_explicit and not (left_selector and right_selector):
        raise ValueError("diff-tree explicit selectors require both --left-node and --right-node")
    return selector, left_selector, right_selector


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="edgp")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo = subparsers.add_parser("demo", help="Resolve a built-in demo registry")
    demo.add_argument("--format", choices=["cypher", "cyclonedx", "json"], default="cypher")

    resolve = subparsers.add_parser("resolve", help="Resolve a JSON registry")
    resolve.add_argument("--registry", type=Path, required=True)
    resolve.add_argument("--root", required=True)
    resolve.add_argument("--version", required=True)
    resolve.add_argument("--format", choices=["cypher", "cyclonedx", "json"], default="cypher")

    lockfile = subparsers.add_parser("lockfile", help="Export a resolved lockfile graph")
    lockfile.add_argument("--path", type=Path, required=True)
    lockfile.add_argument("--ecosystem", choices=["npm", "poetry", "cargo"], default="npm")
    lockfile.add_argument("--format", choices=["cypher", "cyclonedx", "json"], default="cypher")

    npm_diagnostics = subparsers.add_parser(
        "npm-diagnostics", help="Diagnose npm package-lock dependency paths"
    )
    npm_diagnostics.add_argument("--path", type=Path, required=True)

    npm_diagnostics_bundle = subparsers.add_parser(
        "npm-diagnostics-bundle",
        help="Render npm package-lock diagnostics as a static report bundle",
    )
    npm_diagnostics_bundle.add_argument("--path", type=Path, required=True)
    npm_diagnostics_bundle.add_argument("--output-dir", type=Path, required=True)
    _add_triage_bundle_option(npm_diagnostics_bundle)

    npm_bundle = subparsers.add_parser(
        "npm-bundle", help="Render npm graph and diagnostics bundle from package-lock"
    )
    npm_bundle.add_argument("--path", type=Path, required=True)
    npm_bundle.add_argument("--output-dir", type=Path, required=True)
    npm_bundle.add_argument("--impact-node", action="append", default=[])
    npm_bundle.add_argument("--advisories", type=Path)
    npm_bundle.add_argument("--limit", type=int, default=20)
    _add_license_bundle_options(npm_bundle)
    _add_triage_bundle_option(npm_bundle)

    dot = subparsers.add_parser("dot", help="Export a directed DOT dependency graph")
    dot.add_argument("--path", type=Path, required=True)
    dot.add_argument("--ecosystem", default="rpm")
    dot.add_argument("--format", choices=["cypher", "cyclonedx", "json"], default="json")

    dot_bundle = subparsers.add_parser(
        "dot-bundle", help="Render DOT graph bundle with optional impact reports"
    )
    dot_bundle.add_argument("--path", type=Path, required=True)
    dot_bundle.add_argument("--ecosystem", default="rpm")
    dot_bundle.add_argument("--output-dir", type=Path, required=True)
    dot_bundle.add_argument("--impact-node", action="append", default=[])
    dot_bundle.add_argument("--limit", type=int, default=20)
    _add_triage_bundle_option(dot_bundle)

    sbom = subparsers.add_parser("sbom", help="Export a graph from a CycloneDX JSON SBOM")
    sbom.add_argument("--path", type=Path, required=True)
    sbom.add_argument("--format", choices=["cypher", "cyclonedx", "json"], default="json")

    sbom_bundle = subparsers.add_parser(
        "sbom-bundle", help="Render CycloneDX SBOM graph bundle"
    )
    sbom_bundle.add_argument("--path", type=Path, required=True)
    sbom_bundle.add_argument("--output-dir", type=Path, required=True)
    sbom_bundle.add_argument("--impact-node", action="append", default=[])
    sbom_bundle.add_argument("--limit", type=int, default=20)
    _add_license_bundle_options(sbom_bundle)
    _add_triage_bundle_option(sbom_bundle)

    maven_tree = subparsers.add_parser(
        "maven-tree", help="Export a graph from mvn dependency:tree text"
    )
    maven_tree.add_argument("--path", type=Path, required=True)
    maven_tree.add_argument(
        "--format", choices=["cypher", "cyclonedx", "json"], default="json"
    )

    maven_bundle = subparsers.add_parser(
        "maven-bundle", help="Render Maven dependency-tree graph bundle"
    )
    maven_bundle.add_argument("--path", type=Path, required=True)
    maven_bundle.add_argument("--output-dir", type=Path, required=True)
    maven_bundle.add_argument("--impact-node", action="append", default=[])
    maven_bundle.add_argument("--limit", type=int, default=20)
    _add_triage_bundle_option(maven_bundle)

    rpm_installed = subparsers.add_parser(
        "rpm-installed", help="Export a graph from the local RPM database"
    )
    rpm_installed.add_argument("--limit", type=int, default=100)
    rpm_installed.add_argument("--max-requirements", type=int, default=40)
    rpm_installed.add_argument(
        "--format", choices=["cypher", "cyclonedx", "json"], default="json"
    )

    rpm_installed_bundle = subparsers.add_parser(
        "rpm-installed-bundle",
        help="Render installed RPM database graph bundle with optional impact reports",
    )
    rpm_installed_bundle.add_argument("--output-dir", type=Path, required=True)
    rpm_installed_bundle.add_argument("--impact-node", action="append", default=[])
    rpm_installed_bundle.add_argument("--limit", type=int, default=100)
    rpm_installed_bundle.add_argument("--max-requirements", type=int, default=40)
    rpm_installed_bundle.add_argument("--advisories", type=Path)
    rpm_installed_bundle.add_argument("--public-advisory-feed", type=Path)
    rpm_installed_bundle.add_argument("--public-advisory-feed-url")
    rpm_installed_albs_input = rpm_installed_bundle.add_mutually_exclusive_group()
    rpm_installed_albs_input.add_argument("--albs-build-id")
    rpm_installed_albs_input.add_argument("--albs-build-path", type=Path)
    rpm_installed_albs_input.add_argument("--albs-build-url")
    rpm_installed_bundle.add_argument("--albs-base-url", default=DEFAULT_ALBS_BASE_URL)
    rpm_installed_bundle.add_argument(
        "--libsolv-transaction",
        type=Path,
        help="saved libsolv transaction transcript to match against installed RPM graph",
    )
    rpm_installed_bundle.add_argument("--report-limit", type=int, default=20)
    _add_license_bundle_options(rpm_installed_bundle)
    _add_triage_bundle_option(rpm_installed_bundle)

    rpm_repo = subparsers.add_parser(
        "rpm-repo",
        help="Export a graph from public RPM repomd.xml or primary metadata",
    )
    rpm_repo.add_argument("--primary", type=Path)
    rpm_repo.add_argument("--source")
    rpm_repo.add_argument("--repo-id", default="public-rpm-repository")
    rpm_repo.add_argument("--package-limit", type=int, default=5000)
    rpm_repo.add_argument("--requirement-limit", type=int, default=40)
    rpm_repo.add_argument(
        "--format", choices=["cypher", "cyclonedx", "json"], default="json"
    )

    rpm_repo_summary = subparsers.add_parser(
        "rpm-repo-summary",
        help="Summarize public RPM repository metadata coverage",
    )
    rpm_repo_summary.add_argument("--primary", type=Path)
    rpm_repo_summary.add_argument("--source")
    rpm_repo_summary.add_argument("--repo-id", default="public-rpm-repository")
    rpm_repo_summary.add_argument("--package-limit", type=int, default=5000)
    rpm_repo_summary.add_argument("--requirement-limit", type=int, default=40)
    rpm_repo_summary.add_argument("--format", choices=["json", "text"], default="json")

    rpm_repo_summary_bundle = subparsers.add_parser(
        "rpm-repo-summary-bundle",
        help="Render public RPM repository metadata coverage as a static bundle",
    )
    rpm_repo_summary_bundle.add_argument("--primary", type=Path)
    rpm_repo_summary_bundle.add_argument("--source")
    rpm_repo_summary_bundle.add_argument("--repo-id", default="public-rpm-repository")
    rpm_repo_summary_bundle.add_argument("--package-limit", type=int, default=5000)
    rpm_repo_summary_bundle.add_argument("--requirement-limit", type=int, default=40)
    rpm_repo_summary_bundle.add_argument("--output-dir", type=Path, required=True)
    rpm_repo_summary_bundle.add_argument(
        "--format", choices=["path", "text"], default="path"
    )
    _add_triage_bundle_option(rpm_repo_summary_bundle)

    rpm_repo_bundle = subparsers.add_parser(
        "rpm-repo-bundle",
        help="Render public RPM repository graph and summary bundle",
    )
    rpm_repo_bundle.add_argument("--primary", type=Path)
    rpm_repo_bundle.add_argument("--source")
    rpm_repo_bundle.add_argument("--repo-id", default="public-rpm-repository")
    rpm_repo_bundle.add_argument("--package-limit", type=int, default=5000)
    rpm_repo_bundle.add_argument("--requirement-limit", type=int, default=40)
    rpm_repo_bundle.add_argument("--output-dir", type=Path, required=True)
    rpm_repo_bundle.add_argument("--impact-node", action="append", default=[])
    rpm_repo_bundle.add_argument("--advisories", type=Path)
    rpm_repo_bundle.add_argument("--public-advisory-feed", type=Path)
    rpm_repo_bundle.add_argument("--public-advisory-feed-url")
    rpm_repo_bundle.add_argument(
        "--libsolv-transaction",
        type=Path,
        help="saved libsolv transaction transcript to match against the generated graph",
    )
    rpm_repo_bundle.add_argument("--report-limit", type=int, default=20)
    _add_license_bundle_options(rpm_repo_bundle)
    _add_triage_bundle_option(rpm_repo_bundle)

    rpm_repo_diff = subparsers.add_parser(
        "rpm-repo-diff",
        help="Compare two public RPM repository metadata snapshots",
    )
    rpm_repo_diff.add_argument("--left-primary", type=Path)
    rpm_repo_diff.add_argument("--left-source")
    rpm_repo_diff.add_argument("--right-primary", type=Path)
    rpm_repo_diff.add_argument("--right-source")
    rpm_repo_diff.add_argument("--left-repo-id", default="left-rpm-repository")
    rpm_repo_diff.add_argument("--right-repo-id", default="right-rpm-repository")
    rpm_repo_diff.add_argument("--package-limit", type=int, default=5000)
    rpm_repo_diff.add_argument("--requirement-limit", type=int, default=40)
    rpm_repo_diff.add_argument("--format", choices=["json", "text"], default="json")

    rpm_repo_diff_bundle = subparsers.add_parser(
        "rpm-repo-diff-bundle",
        help="Render public RPM repository snapshot diff as a static bundle",
    )
    rpm_repo_diff_bundle.add_argument("--left-primary", type=Path)
    rpm_repo_diff_bundle.add_argument("--left-source")
    rpm_repo_diff_bundle.add_argument("--right-primary", type=Path)
    rpm_repo_diff_bundle.add_argument("--right-source")
    rpm_repo_diff_bundle.add_argument("--left-repo-id", default="left-rpm-repository")
    rpm_repo_diff_bundle.add_argument("--right-repo-id", default="right-rpm-repository")
    rpm_repo_diff_bundle.add_argument("--package-limit", type=int, default=5000)
    rpm_repo_diff_bundle.add_argument("--requirement-limit", type=int, default=40)
    rpm_repo_diff_bundle.add_argument("--output-dir", type=Path, required=True)
    rpm_repo_diff_bundle.add_argument(
        "--format", choices=["path", "text"], default="path"
    )
    _add_triage_bundle_option(rpm_repo_diff_bundle)

    albs_build = subparsers.add_parser(
        "albs-build",
        help="Export a graph from public ALBS build metadata",
    )
    albs_input = albs_build.add_mutually_exclusive_group(required=True)
    albs_input.add_argument("--build-id")
    albs_input.add_argument("--path", type=Path)
    albs_input.add_argument("--url")
    albs_build.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    albs_build.add_argument("--task-limit", type=int, default=50)
    albs_build.add_argument("--artifact-limit", type=int, default=200)
    albs_build.add_argument("--test-task-limit", type=int, default=50)
    albs_build.add_argument("--include-logs", action="store_true")
    albs_build.add_argument(
        "--format", choices=["cypher", "cyclonedx", "json"], default="json"
    )

    albs_artifact_inventory = subparsers.add_parser(
        "albs-artifact-inventory",
        help="Export ALBS build artifact inventory from public build metadata",
    )
    albs_inventory_input = albs_artifact_inventory.add_mutually_exclusive_group(
        required=True
    )
    albs_inventory_input.add_argument("--build-id")
    albs_inventory_input.add_argument("--path", type=Path)
    albs_inventory_input.add_argument("--url")
    albs_artifact_inventory.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    albs_artifact_inventory.add_argument("--task-limit", type=int, default=50)
    albs_artifact_inventory.add_argument("--artifact-limit", type=int, default=200)
    albs_artifact_inventory.add_argument("--test-task-limit", type=int, default=50)
    albs_artifact_inventory.add_argument("--include-logs", action="store_true")
    albs_artifact_inventory.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    albs_artifact_inventory_bundle = subparsers.add_parser(
        "albs-artifact-inventory-bundle",
        help="Render public ALBS artifact inventory as a static bundle",
    )
    albs_inventory_bundle_input = albs_artifact_inventory_bundle.add_mutually_exclusive_group(
        required=True
    )
    albs_inventory_bundle_input.add_argument("--build-id")
    albs_inventory_bundle_input.add_argument("--path", type=Path)
    albs_inventory_bundle_input.add_argument("--url")
    albs_artifact_inventory_bundle.add_argument(
        "--base-url",
        default=DEFAULT_ALBS_BASE_URL,
    )
    albs_artifact_inventory_bundle.add_argument("--task-limit", type=int, default=50)
    albs_artifact_inventory_bundle.add_argument("--artifact-limit", type=int, default=200)
    albs_artifact_inventory_bundle.add_argument(
        "--test-task-limit",
        type=int,
        default=50,
    )
    albs_artifact_inventory_bundle.add_argument("--include-logs", action="store_true")
    albs_artifact_inventory_bundle.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    albs_artifact_inventory_bundle.add_argument(
        "--format",
        choices=["path", "text"],
        default="path",
    )
    _add_triage_bundle_option(albs_artifact_inventory_bundle)

    albs_build_timing = subparsers.add_parser(
        "albs-build-timing",
        help="Export ALBS build task and artifact timing from public build metadata",
    )
    albs_timing_input = albs_build_timing.add_mutually_exclusive_group(required=True)
    albs_timing_input.add_argument("--build-id")
    albs_timing_input.add_argument("--path", type=Path)
    albs_timing_input.add_argument("--url")
    albs_build_timing.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    albs_build_timing.add_argument("--format", choices=["json", "text"], default="json")

    albs_build_timing_bundle = subparsers.add_parser(
        "albs-build-timing-bundle",
        help="Render public ALBS build timing as a static bundle",
    )
    albs_timing_bundle_input = albs_build_timing_bundle.add_mutually_exclusive_group(
        required=True
    )
    albs_timing_bundle_input.add_argument("--build-id")
    albs_timing_bundle_input.add_argument("--path", type=Path)
    albs_timing_bundle_input.add_argument("--url")
    albs_build_timing_bundle.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    albs_build_timing_bundle.add_argument("--output-dir", type=Path, required=True)
    albs_build_timing_bundle.add_argument(
        "--format",
        choices=["path", "text"],
        default="path",
    )
    _add_triage_bundle_option(albs_build_timing_bundle)

    albs_build_bundle = subparsers.add_parser(
        "albs-build-bundle",
        help="Render public ALBS build metadata as a static graph bundle",
    )
    albs_bundle_input = albs_build_bundle.add_mutually_exclusive_group(required=True)
    albs_bundle_input.add_argument("--build-id")
    albs_bundle_input.add_argument("--path", type=Path)
    albs_bundle_input.add_argument("--url")
    albs_build_bundle.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    albs_build_bundle.add_argument("--output-dir", type=Path, required=True)
    albs_build_bundle.add_argument("--impact-node", action="append", default=[])
    albs_build_bundle.add_argument("--task-limit", type=int, default=50)
    albs_build_bundle.add_argument("--artifact-limit", type=int, default=200)
    albs_build_bundle.add_argument("--test-task-limit", type=int, default=50)
    albs_build_bundle.add_argument("--include-logs", action="store_true")
    albs_build_bundle.add_argument("--report-limit", type=int, default=20)
    _add_triage_bundle_option(albs_build_bundle)

    albs_build_diff = subparsers.add_parser(
        "albs-build-diff",
        help="Compare two public ALBS builds or local ALBS JSON fixtures",
    )
    albs_build_diff.add_argument("--left-build-id")
    albs_build_diff.add_argument("--left-path", type=Path)
    albs_build_diff.add_argument("--left-url")
    albs_build_diff.add_argument("--right-build-id")
    albs_build_diff.add_argument("--right-path", type=Path)
    albs_build_diff.add_argument("--right-url")
    albs_build_diff.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    albs_build_diff.add_argument("--format", choices=["json", "text"], default="json")

    albs_build_diff_bundle = subparsers.add_parser(
        "albs-build-diff-bundle",
        help="Render public ALBS build comparison as a static bundle",
    )
    albs_build_diff_bundle.add_argument("--left-build-id")
    albs_build_diff_bundle.add_argument("--left-path", type=Path)
    albs_build_diff_bundle.add_argument("--left-url")
    albs_build_diff_bundle.add_argument("--right-build-id")
    albs_build_diff_bundle.add_argument("--right-path", type=Path)
    albs_build_diff_bundle.add_argument("--right-url")
    albs_build_diff_bundle.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    albs_build_diff_bundle.add_argument("--output-dir", type=Path, required=True)
    albs_build_diff_bundle.add_argument(
        "--format",
        choices=["path", "text"],
        default="path",
    )
    _add_triage_bundle_option(albs_build_diff_bundle)

    albs_log_intelligence = subparsers.add_parser(
        "albs-log-intelligence",
        help="Extract build-log signals from public ALBS build metadata",
    )
    albs_log_input = albs_log_intelligence.add_mutually_exclusive_group(required=True)
    albs_log_input.add_argument("--build-id")
    albs_log_input.add_argument("--path", type=Path)
    albs_log_input.add_argument("--url")
    albs_log_intelligence.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    albs_log_intelligence.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    albs_log_intelligence_bundle = subparsers.add_parser(
        "albs-log-intelligence-bundle",
        help="Render public ALBS build-log signals as a static bundle",
    )
    albs_log_bundle_input = albs_log_intelligence_bundle.add_mutually_exclusive_group(
        required=True
    )
    albs_log_bundle_input.add_argument("--build-id")
    albs_log_bundle_input.add_argument("--path", type=Path)
    albs_log_bundle_input.add_argument("--url")
    albs_log_intelligence_bundle.add_argument(
        "--base-url",
        default=DEFAULT_ALBS_BASE_URL,
    )
    albs_log_intelligence_bundle.add_argument("--output-dir", type=Path, required=True)
    albs_log_intelligence_bundle.add_argument(
        "--format",
        choices=["path", "text"],
        default="path",
    )
    _add_triage_bundle_option(albs_log_intelligence_bundle)

    albs_release_completeness = subparsers.add_parser(
        "albs-release-completeness",
        help="Summarize architecture, signing, and test coverage across ALBS builds",
    )
    albs_release_completeness.add_argument("--build-id", action="append", default=[])
    albs_release_completeness.add_argument("--path", type=Path, action="append", default=[])
    albs_release_completeness.add_argument("--url", action="append", default=[])
    albs_release_completeness.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    albs_release_completeness.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    albs_release_completeness_bundle = subparsers.add_parser(
        "albs-release-completeness-bundle",
        help="Render public ALBS release coverage as a static bundle",
    )
    albs_release_completeness_bundle.add_argument(
        "--build-id",
        action="append",
        default=[],
    )
    albs_release_completeness_bundle.add_argument(
        "--path",
        type=Path,
        action="append",
        default=[],
    )
    albs_release_completeness_bundle.add_argument(
        "--url",
        action="append",
        default=[],
    )
    albs_release_completeness_bundle.add_argument(
        "--base-url",
        default=DEFAULT_ALBS_BASE_URL,
    )
    albs_release_completeness_bundle.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    albs_release_completeness_bundle.add_argument(
        "--format",
        choices=["path", "text"],
        default="path",
    )
    _add_triage_bundle_option(albs_release_completeness_bundle)

    rpm_albs_provenance = subparsers.add_parser(
        "rpm-albs-provenance",
        help="Join installed RPMs to artifacts from a public ALBS build",
    )
    rpm_albs_input = rpm_albs_provenance.add_mutually_exclusive_group(required=True)
    rpm_albs_input.add_argument("--build-id")
    rpm_albs_input.add_argument("--path", type=Path)
    rpm_albs_input.add_argument("--url")
    rpm_albs_provenance.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    rpm_albs_provenance.add_argument("--rpm-limit", type=int, default=100)
    rpm_albs_provenance.add_argument("--max-requirements", type=int, default=40)
    rpm_albs_provenance.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    rpm_albs_provenance_bundle = subparsers.add_parser(
        "rpm-albs-provenance-bundle",
        help="Render installed RPM to public ALBS artifact provenance as a bundle",
    )
    rpm_albs_bundle_input = rpm_albs_provenance_bundle.add_mutually_exclusive_group(
        required=True
    )
    rpm_albs_bundle_input.add_argument("--build-id")
    rpm_albs_bundle_input.add_argument("--path", type=Path)
    rpm_albs_bundle_input.add_argument("--url")
    rpm_albs_provenance_bundle.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    rpm_albs_provenance_bundle.add_argument("--rpm-limit", type=int, default=100)
    rpm_albs_provenance_bundle.add_argument("--max-requirements", type=int, default=40)
    rpm_albs_provenance_bundle.add_argument("--output-dir", type=Path, required=True)
    rpm_albs_provenance_bundle.add_argument(
        "--format",
        choices=["path", "text"],
        default="path",
    )
    _add_triage_bundle_option(rpm_albs_provenance_bundle)

    libsolv_bridge = subparsers.add_parser(
        "libsolv-bridge",
        help="Report libsolv command availability and parse transaction output",
    )
    libsolv_bridge.add_argument("--transaction", type=Path)
    libsolv_bridge.add_argument(
        "--graph-snapshot",
        type=Path,
        help="EDGP graph snapshot used to match transaction packages to graph nodes",
    )

    libsolv_bundle = subparsers.add_parser(
        "libsolv-bundle",
        help="Render a libsolv transaction bridge report bundle",
    )
    libsolv_bundle.add_argument("--transaction", type=Path, required=True)
    libsolv_bundle.add_argument("--output-dir", type=Path, required=True)
    libsolv_bundle.add_argument(
        "--graph-snapshot",
        type=Path,
        help="EDGP graph snapshot used to match transaction packages to graph nodes",
    )
    _add_triage_bundle_option(libsolv_bundle)

    public_advisory_feed = subparsers.add_parser(
        "public-advisory-feed",
        help="Normalize a public advisory feed into an EDGP advisory overlay",
    )
    public_advisory_feed.add_argument("--path", type=Path)
    public_advisory_feed.add_argument("--url")
    public_advisory_feed.add_argument("--ecosystem", default="rpm")
    public_advisory_feed.add_argument(
        "--format", choices=["report", "overlay", "text"], default="report"
    )
    public_advisory_feed_bundle = subparsers.add_parser(
        "public-advisory-feed-bundle",
        help="Render a public advisory feed normalization report as a static bundle",
    )
    public_advisory_feed_bundle.add_argument("--path", type=Path)
    public_advisory_feed_bundle.add_argument("--url")
    public_advisory_feed_bundle.add_argument("--ecosystem", default="rpm")
    public_advisory_feed_bundle.add_argument("--output-dir", type=Path, required=True)
    public_advisory_feed_bundle.add_argument(
        "--format",
        choices=["path", "text"],
        default="path",
    )
    _add_triage_bundle_option(public_advisory_feed_bundle)

    fixture_provenance = subparsers.add_parser(
        "fixture-provenance",
        help="Generate the EDGP fixture provenance catalog",
    )
    fixture_provenance.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/fixtures"),
        help="fixture directory to catalog",
    )
    fixture_provenance.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    fixture_provenance_bundle = subparsers.add_parser(
        "fixture-provenance-bundle",
        help="Render the EDGP fixture provenance catalog as a static bundle",
    )
    fixture_provenance_bundle.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/fixtures"),
        help="fixture directory to catalog",
    )
    fixture_provenance_bundle.add_argument("--output-dir", type=Path, required=True)
    _add_triage_bundle_option(fixture_provenance_bundle)

    real_data_coverage = subparsers.add_parser(
        "real-data-coverage",
        help="Summarize public-derived, generated, and synthetic fixture coverage",
    )
    real_data_coverage.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/fixtures"),
        help="fixture directory to assess",
    )
    real_data_coverage.add_argument(
        "--min-public-evidence-percent",
        type=float,
        help="return status 2 when public evidence coverage is below this threshold",
    )
    real_data_coverage.add_argument(
        "--fail-on-priority",
        choices=["high", "medium", "low"],
        help=(
            "return status 2 when replacement-plan items exist at this priority "
            "or higher"
        ),
    )
    real_data_coverage.add_argument("--format", choices=["json", "text"], default="json")

    real_data_coverage_bundle = subparsers.add_parser(
        "real-data-coverage-bundle",
        help="Render real-data fixture coverage as a static bundle",
    )
    real_data_coverage_bundle.add_argument(
        "--fixture-dir",
        type=Path,
        default=Path("tests/fixtures"),
        help="fixture directory to assess",
    )
    real_data_coverage_bundle.add_argument(
        "--min-public-evidence-percent",
        type=float,
        help="mark the bundle triage as failed below this public evidence threshold",
    )
    real_data_coverage_bundle.add_argument(
        "--fail-on-priority",
        choices=["high", "medium", "low"],
        help=(
            "mark the bundle triage as failed when replacement-plan items exist "
            "at this priority or higher"
        ),
    )
    real_data_coverage_bundle.add_argument("--output-dir", type=Path, required=True)
    _add_triage_bundle_option(real_data_coverage_bundle)

    real_data_replacement_plan = subparsers.add_parser(
        "real-data-replacement-plan",
        help="Rank synthetic fixture groups that should move toward public data",
    )
    real_data_replacement_plan_input = (
        real_data_replacement_plan.add_mutually_exclusive_group()
    )
    real_data_replacement_plan_input.add_argument(
        "--fixture-dir",
        type=Path,
        help="fixture directory to assess; defaults to tests/fixtures",
    )
    real_data_replacement_plan_input.add_argument(
        "--coverage",
        type=Path,
        help="existing edgp.real_data.coverage.v1 JSON report",
    )
    real_data_replacement_plan.add_argument(
        "--fail-on-priority",
        choices=["high", "medium", "low"],
        help=(
            "return status 2 when replacement candidates exist at this priority "
            "or higher"
        ),
    )
    real_data_replacement_plan.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    real_data_replacement_plan_bundle = subparsers.add_parser(
        "real-data-replacement-plan-bundle",
        help="Render ranked fixture replacement planning as a static bundle",
    )
    real_data_replacement_plan_bundle_input = (
        real_data_replacement_plan_bundle.add_mutually_exclusive_group()
    )
    real_data_replacement_plan_bundle_input.add_argument(
        "--fixture-dir",
        type=Path,
        help="fixture directory to assess; defaults to tests/fixtures",
    )
    real_data_replacement_plan_bundle_input.add_argument(
        "--coverage",
        type=Path,
        help="existing edgp.real_data.coverage.v1 JSON report",
    )
    real_data_replacement_plan_bundle.add_argument(
        "--fail-on-priority",
        choices=["high", "medium", "low"],
        help=(
            "mark the bundle policy as failed when replacement candidates exist "
            "at this priority or higher"
        ),
    )
    real_data_replacement_plan_bundle.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    _add_triage_bundle_option(real_data_replacement_plan_bundle)

    real_data_replacement_plan_diff = subparsers.add_parser(
        "real-data-replacement-plan-diff",
        help="Compare two real-data replacement plans or fixture snapshots",
    )
    replacement_plan_diff_left = (
        real_data_replacement_plan_diff.add_mutually_exclusive_group(required=True)
    )
    replacement_plan_diff_left.add_argument(
        "--left",
        type=Path,
        help="left edgp.real_data.replacement_plan.v1 JSON report",
    )
    replacement_plan_diff_left.add_argument(
        "--left-coverage",
        type=Path,
        help="build the left replacement plan from this coverage JSON report",
    )
    replacement_plan_diff_left.add_argument(
        "--left-fixture-dir",
        type=Path,
        help="build the left replacement plan from this fixture directory",
    )
    replacement_plan_diff_right = (
        real_data_replacement_plan_diff.add_mutually_exclusive_group(required=True)
    )
    replacement_plan_diff_right.add_argument(
        "--right",
        type=Path,
        help="right edgp.real_data.replacement_plan.v1 JSON report",
    )
    replacement_plan_diff_right.add_argument(
        "--right-coverage",
        type=Path,
        help="build the right replacement plan from this coverage JSON report",
    )
    replacement_plan_diff_right.add_argument(
        "--right-fixture-dir",
        type=Path,
        help="build the right replacement plan from this fixture directory",
    )
    real_data_replacement_plan_diff.add_argument("--left-label", default="left")
    real_data_replacement_plan_diff.add_argument("--right-label", default="right")
    real_data_replacement_plan_diff.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="return status 2 when replacement backlog metrics regress",
    )
    real_data_replacement_plan_diff.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    real_data_replacement_plan_diff_bundle = subparsers.add_parser(
        "real-data-replacement-plan-diff-bundle",
        help="Render a real-data replacement plan diff as a static bundle",
    )
    replacement_plan_diff_bundle_left = (
        real_data_replacement_plan_diff_bundle.add_mutually_exclusive_group(
            required=True
        )
    )
    replacement_plan_diff_bundle_left.add_argument(
        "--left",
        type=Path,
        help="left edgp.real_data.replacement_plan.v1 JSON report",
    )
    replacement_plan_diff_bundle_left.add_argument(
        "--left-coverage",
        type=Path,
        help="build the left replacement plan from this coverage JSON report",
    )
    replacement_plan_diff_bundle_left.add_argument(
        "--left-fixture-dir",
        type=Path,
        help="build the left replacement plan from this fixture directory",
    )
    replacement_plan_diff_bundle_right = (
        real_data_replacement_plan_diff_bundle.add_mutually_exclusive_group(
            required=True
        )
    )
    replacement_plan_diff_bundle_right.add_argument(
        "--right",
        type=Path,
        help="right edgp.real_data.replacement_plan.v1 JSON report",
    )
    replacement_plan_diff_bundle_right.add_argument(
        "--right-coverage",
        type=Path,
        help="build the right replacement plan from this coverage JSON report",
    )
    replacement_plan_diff_bundle_right.add_argument(
        "--right-fixture-dir",
        type=Path,
        help="build the right replacement plan from this fixture directory",
    )
    real_data_replacement_plan_diff_bundle.add_argument("--left-label", default="left")
    real_data_replacement_plan_diff_bundle.add_argument("--right-label", default="right")
    real_data_replacement_plan_diff_bundle.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="return status 2 when replacement backlog metrics regress",
    )
    real_data_replacement_plan_diff_bundle.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    _add_triage_bundle_option(real_data_replacement_plan_diff_bundle)

    real_data_coverage_diff = subparsers.add_parser(
        "real-data-coverage-diff",
        help="Compare two real-data coverage reports or fixture directories",
    )
    real_data_coverage_diff_left = real_data_coverage_diff.add_mutually_exclusive_group(
        required=True
    )
    real_data_coverage_diff_left.add_argument(
        "--left",
        type=Path,
        help="left edgp.real_data.coverage.v1 JSON report",
    )
    real_data_coverage_diff_left.add_argument(
        "--left-fixture-dir",
        type=Path,
        help="build the left coverage report from this fixture directory",
    )
    real_data_coverage_diff_right = real_data_coverage_diff.add_mutually_exclusive_group(
        required=True
    )
    real_data_coverage_diff_right.add_argument(
        "--right",
        type=Path,
        help="right edgp.real_data.coverage.v1 JSON report",
    )
    real_data_coverage_diff_right.add_argument(
        "--right-fixture-dir",
        type=Path,
        help="build the right coverage report from this fixture directory",
    )
    real_data_coverage_diff.add_argument("--left-label", default="left")
    real_data_coverage_diff.add_argument("--right-label", default="right")
    real_data_coverage_diff.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="return status 2 when public evidence coverage regresses",
    )
    real_data_coverage_diff.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    real_data_coverage_diff_bundle = subparsers.add_parser(
        "real-data-coverage-diff-bundle",
        help="Render a real-data coverage diff as a static bundle",
    )
    real_data_coverage_diff_bundle_left = (
        real_data_coverage_diff_bundle.add_mutually_exclusive_group(required=True)
    )
    real_data_coverage_diff_bundle_left.add_argument(
        "--left",
        type=Path,
        help="left edgp.real_data.coverage.v1 JSON report",
    )
    real_data_coverage_diff_bundle_left.add_argument(
        "--left-fixture-dir",
        type=Path,
        help="build the left coverage report from this fixture directory",
    )
    real_data_coverage_diff_bundle_right = (
        real_data_coverage_diff_bundle.add_mutually_exclusive_group(required=True)
    )
    real_data_coverage_diff_bundle_right.add_argument(
        "--right",
        type=Path,
        help="right edgp.real_data.coverage.v1 JSON report",
    )
    real_data_coverage_diff_bundle_right.add_argument(
        "--right-fixture-dir",
        type=Path,
        help="build the right coverage report from this fixture directory",
    )
    real_data_coverage_diff_bundle.add_argument("--left-label", default="left")
    real_data_coverage_diff_bundle.add_argument("--right-label", default="right")
    real_data_coverage_diff_bundle.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="mark the bundle triage as failed when coverage regresses",
    )
    real_data_coverage_diff_bundle.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    _add_triage_bundle_option(real_data_coverage_diff_bundle)

    diff = subparsers.add_parser("diff", help="Diff two EDGP JSON graph snapshots")
    diff.add_argument("--left", type=Path, required=True)
    diff.add_argument("--right", type=Path, required=True)
    diff.add_argument("--format", choices=["json", "text"], default="json")
    diff.add_argument(
        "--fail-on-change",
        action="append",
        choices=DIFF_CHANGE_KINDS,
        default=[],
        help="return status 2 when the graph diff includes this change kind",
    )
    diff.add_argument(
        "--fail-on-kind",
        action="append",
        choices=DIFF_TREE_CHANGE_KINDS,
        default=[],
        help="return status 2 when the graph diff includes this package change kind",
    )

    diff_bundle = subparsers.add_parser(
        "diff-bundle",
        help="Render an EDGP graph snapshot diff as a static report bundle",
    )
    diff_bundle.add_argument("--left", type=Path, required=True)
    diff_bundle.add_argument("--right", type=Path, required=True)
    diff_bundle.add_argument("--output-dir", type=Path, required=True)
    diff_bundle.add_argument("--format", choices=["path", "text"], default="path")
    diff_bundle.add_argument(
        "--archive-output",
        type=Path,
        help="also write the generated graph diff bundle as deterministic .tar.gz",
    )
    diff_bundle.add_argument(
        "--fail-on-change",
        action="append",
        choices=DIFF_CHANGE_KINDS,
        default=[],
        help="return status 2 when the graph diff includes this change kind",
    )
    diff_bundle.add_argument(
        "--fail-on-kind",
        action="append",
        choices=DIFF_TREE_CHANGE_KINDS,
        default=[],
        help="return status 2 when the graph diff includes this package change kind",
    )
    _add_triage_bundle_option(diff_bundle)

    diff_tree = subparsers.add_parser(
        "diff-tree",
        help="Diff the dependency or dependent cone around one node in two snapshots",
    )
    diff_tree.add_argument("--left", type=Path, required=True)
    diff_tree.add_argument("--right", type=Path, required=True)
    diff_tree.add_argument("--node")
    diff_tree.add_argument("--left-node")
    diff_tree.add_argument("--right-node")
    diff_tree.add_argument("--format", choices=["json", "text"], default="json")
    diff_tree.add_argument(
        "--direction",
        choices=["dependencies", "dependents"],
        default="dependencies",
    )
    diff_tree.add_argument("--depth", type=int, default=3)
    diff_tree.add_argument(
        "--fail-on-kind",
        action="append",
        choices=DIFF_TREE_CHANGE_KINDS,
        default=[],
        help=(
            "return status 2 when the focused diff includes this classified "
            "change kind"
        ),
    )

    diff_tree_bundle = subparsers.add_parser(
        "diff-tree-bundle",
        help="Render a focused graph cone diff as a static report bundle",
    )
    diff_tree_bundle.add_argument("--left", type=Path, required=True)
    diff_tree_bundle.add_argument("--right", type=Path, required=True)
    diff_tree_bundle.add_argument("--node")
    diff_tree_bundle.add_argument("--left-node")
    diff_tree_bundle.add_argument("--right-node")
    diff_tree_bundle.add_argument(
        "--direction",
        choices=["dependencies", "dependents"],
        default="dependencies",
    )
    diff_tree_bundle.add_argument("--depth", type=int, default=3)
    diff_tree_bundle.add_argument("--output-dir", type=Path, required=True)
    diff_tree_bundle.add_argument("--format", choices=["path", "text"], default="path")
    diff_tree_bundle.add_argument(
        "--archive-output",
        type=Path,
        help="also write the generated graph diff-tree bundle as deterministic .tar.gz",
    )
    diff_tree_bundle.add_argument(
        "--fail-on-kind",
        action="append",
        choices=DIFF_TREE_CHANGE_KINDS,
        default=[],
        help=(
            "return status 2 when the focused diff includes this classified "
            "change kind"
        ),
    )
    _add_triage_bundle_option(diff_tree_bundle)

    impact = subparsers.add_parser("impact", help="Report reverse dependency impact")
    impact.add_argument(
        "--source",
        choices=[
            "lockfile",
            "dot",
            "sbom",
            "maven-tree",
            "rpm-installed",
            "rpm-repo",
            "albs-build",
        ],
        default="lockfile",
    )
    impact.add_argument("--path", type=Path)
    _add_albs_graph_source_options(impact)
    impact.add_argument("--ecosystem", default="npm")
    impact.add_argument("--node", required=True)
    impact.add_argument("--limit", type=int, default=20)
    impact.add_argument("--rpm-limit", type=int, default=100)
    impact.add_argument("--max-requirements", type=int, default=40)
    _add_rpm_repo_source_options(impact)

    impact_bundle = subparsers.add_parser(
        "impact-bundle",
        help="Render reverse dependency impact analysis as a static report bundle",
    )
    impact_bundle.add_argument(
        "--source",
        choices=[
            "lockfile",
            "dot",
            "sbom",
            "maven-tree",
            "rpm-installed",
            "rpm-repo",
            "albs-build",
        ],
        default="lockfile",
    )
    impact_bundle.add_argument("--path", type=Path)
    _add_albs_graph_source_options(impact_bundle)
    impact_bundle.add_argument("--ecosystem", default="npm")
    impact_bundle.add_argument("--node", required=True)
    impact_bundle.add_argument("--limit", type=int, default=20)
    impact_bundle.add_argument("--rpm-limit", type=int, default=100)
    impact_bundle.add_argument("--max-requirements", type=int, default=40)
    impact_bundle.add_argument("--output-dir", type=Path, required=True)
    _add_rpm_repo_source_options(impact_bundle)
    _add_triage_bundle_option(impact_bundle)

    advisory = subparsers.add_parser("advisory", help="Overlay advisories on a graph")
    advisory.add_argument(
        "--source",
        choices=[
            "lockfile",
            "dot",
            "sbom",
            "maven-tree",
            "rpm-installed",
            "rpm-repo",
            "albs-build",
        ],
        default="lockfile",
    )
    advisory.add_argument("--path", type=Path)
    _add_albs_graph_source_options(advisory)
    advisory.add_argument("--ecosystem", default="npm")
    advisory.add_argument("--advisories", type=Path)
    advisory.add_argument("--public-advisory-feed", type=Path)
    advisory.add_argument("--public-advisory-feed-url")
    advisory.add_argument("--fail-on-findings", action="store_true")
    advisory.add_argument(
        "--fail-min-severity",
        choices=["unknown", "low", "medium", "high", "critical"],
        default="unknown",
    )
    advisory.add_argument("--limit", type=int, default=20)
    advisory.add_argument("--rpm-limit", type=int, default=100)
    advisory.add_argument("--max-requirements", type=int, default=40)
    _add_rpm_repo_source_options(advisory)

    advisory_bundle = subparsers.add_parser(
        "advisory-bundle",
        help="Render advisory impact analysis as a static report bundle",
    )
    advisory_bundle.add_argument(
        "--source",
        choices=[
            "lockfile",
            "dot",
            "sbom",
            "maven-tree",
            "rpm-installed",
            "rpm-repo",
            "albs-build",
        ],
        default="lockfile",
    )
    advisory_bundle.add_argument("--path", type=Path)
    _add_albs_graph_source_options(advisory_bundle)
    advisory_bundle.add_argument("--ecosystem", default="npm")
    advisory_bundle.add_argument("--advisories", type=Path)
    advisory_bundle.add_argument("--public-advisory-feed", type=Path)
    advisory_bundle.add_argument("--public-advisory-feed-url")
    advisory_bundle.add_argument("--fail-on-findings", action="store_true")
    advisory_bundle.add_argument(
        "--fail-min-severity",
        choices=["unknown", "low", "medium", "high", "critical"],
        default="unknown",
    )
    advisory_bundle.add_argument("--limit", type=int, default=20)
    advisory_bundle.add_argument("--rpm-limit", type=int, default=100)
    advisory_bundle.add_argument("--max-requirements", type=int, default=40)
    advisory_bundle.add_argument("--output-dir", type=Path, required=True)
    _add_rpm_repo_source_options(advisory_bundle)
    _add_triage_bundle_option(advisory_bundle)

    license_report = subparsers.add_parser(
        "license-report",
        help="Summarize licenses and optionally fail on denied licenses",
    )
    license_report.add_argument(
        "--source",
        choices=[
            "lockfile",
            "dot",
            "sbom",
            "maven-tree",
            "rpm-installed",
            "rpm-repo",
            "albs-build",
        ],
        default="lockfile",
    )
    license_report.add_argument("--path", type=Path)
    _add_albs_graph_source_options(license_report)
    license_report.add_argument("--ecosystem", default="npm")
    license_report.add_argument("--deny-license", action="append", default=[])
    license_report.add_argument("--fail-on-denied", action="store_true")
    license_report.add_argument("--rpm-limit", type=int, default=100)
    license_report.add_argument("--max-requirements", type=int, default=40)
    _add_rpm_repo_source_options(license_report)

    license_report_bundle = subparsers.add_parser(
        "license-report-bundle",
        help="Render a license inventory and deny-list report as a static bundle",
    )
    license_report_bundle.add_argument(
        "--source",
        choices=[
            "lockfile",
            "dot",
            "sbom",
            "maven-tree",
            "rpm-installed",
            "rpm-repo",
            "albs-build",
        ],
        default="lockfile",
    )
    license_report_bundle.add_argument("--path", type=Path)
    _add_albs_graph_source_options(license_report_bundle)
    license_report_bundle.add_argument("--ecosystem", default="npm")
    license_report_bundle.add_argument("--deny-license", action="append", default=[])
    license_report_bundle.add_argument("--fail-on-denied", action="store_true")
    license_report_bundle.add_argument("--rpm-limit", type=int, default=100)
    license_report_bundle.add_argument("--max-requirements", type=int, default=40)
    license_report_bundle.add_argument("--output-dir", type=Path, required=True)
    _add_rpm_repo_source_options(license_report_bundle)
    _add_triage_bundle_option(license_report_bundle)

    triage_summary = subparsers.add_parser(
        "triage-summary",
        help=(
            "Aggregate EDGP reports, a report bundle directory, or a "
            "deterministic bundle archive into one triage summary"
        ),
    )
    triage_input = triage_summary.add_mutually_exclusive_group(required=True)
    triage_input.add_argument(
        "--bundle",
        type=Path,
        help="report bundle directory or deterministic .tar.gz/.tgz archive",
    )
    triage_input.add_argument("--input", type=Path, action="append", default=[])
    triage_summary.add_argument("--manifest-name", default="manifest.json")
    triage_summary.add_argument(
        "--fail-on-status",
        choices=["warn", "fail"],
        help="return status 2 when the triage status is at least this severity",
    )
    triage_summary.add_argument("--format", choices=["json", "text"], default="json")

    report = subparsers.add_parser("report", help="Render a local HTML JSON report")
    report_input = report.add_mutually_exclusive_group(required=True)
    report_input.add_argument("--snapshot", type=Path)
    report_input.add_argument("--input", type=Path)
    report.add_argument("--output", type=Path, required=True)

    export_batch = subparsers.add_parser(
        "export-batch",
        help="Write local Cypher, CycloneDX, or JSON egress artifacts from a graph snapshot",
    )
    export_batch.add_argument("--snapshot", type=Path, required=True)
    export_batch.add_argument("--output-dir", type=Path, required=True)
    export_batch.add_argument(
        "--format",
        action="append",
        choices=["cypher", "cyclonedx", "json"],
        default=[],
        help="egress format to write; may be repeated; defaults to cypher and cyclonedx",
    )
    export_batch.add_argument("--manifest-name", default="manifest.json")

    verify_export_batch = subparsers.add_parser(
        "verify-export-batch",
        help="Verify a local graph export batch manifest and artifact digests",
    )
    verify_export_batch.add_argument("--path", type=Path, required=True)
    verify_export_batch.add_argument("--manifest-name", default="manifest.json")
    verify_export_batch.add_argument("--format", choices=["json", "text"], default="json")

    archive_export_batch = subparsers.add_parser(
        "archive-export-batch",
        help="Verify and package a graph export batch as deterministic tar.gz",
    )
    archive_export_batch.add_argument("--path", type=Path, required=True)
    archive_export_batch.add_argument("--output", type=Path, required=True)
    archive_export_batch.add_argument("--manifest-name", default="manifest.json")
    archive_export_batch.add_argument("--format", choices=["json", "text"], default="json")

    verify_export_batch_archive = subparsers.add_parser(
        "verify-export-batch-archive",
        help="Verify a deterministic tar.gz graph export batch archive",
    )
    verify_export_batch_archive.add_argument("--path", type=Path, required=True)
    verify_export_batch_archive.add_argument("--manifest-name", default="manifest.json")
    verify_export_batch_archive.add_argument(
        "--format", choices=["json", "text"], default="json"
    )

    plan_export_batch_submission = subparsers.add_parser(
        "plan-export-batch-submission",
        help="Build a dry-run submission plan for a verified graph export batch",
    )
    plan_export_batch_submission.add_argument("--path", type=Path, required=True)
    plan_export_batch_submission.add_argument(
        "--target",
        choices=["neo4j", "dependency-track", "generic"],
        required=True,
    )
    plan_export_batch_submission.add_argument("--endpoint", required=True)
    plan_export_batch_submission.add_argument("--manifest-name", default="manifest.json")
    plan_export_batch_submission.add_argument("--output", type=Path)
    plan_export_batch_submission.add_argument(
        "--format", choices=["json", "text"], default="json"
    )

    report_bundle = subparsers.add_parser(
        "report-bundle", help="Render multiple local HTML JSON reports with an index"
    )
    report_bundle.add_argument("--input", type=Path, action="append", required=True)
    report_bundle.add_argument("--output-dir", type=Path, required=True)
    report_bundle.add_argument("--index-name", default="index.html")
    report_bundle.add_argument("--manifest-name", default="manifest.json")
    report_bundle.add_argument(
        "--format",
        choices=["path", "text"],
        default="path",
        help="output the generated index path or a compact text summary",
    )
    report_bundle.add_argument(
        "--archive-output",
        type=Path,
        help="also write the generated report bundle as a deterministic .tar.gz archive",
    )
    _add_triage_bundle_option(report_bundle)

    bundle_catalog = subparsers.add_parser(
        "bundle-catalog",
        help=(
            "Catalog and verify multiple static EDGP report bundles or "
            "deterministic bundle archives"
        ),
    )
    bundle_catalog.add_argument("--bundle", type=Path, action="append", required=True)
    bundle_catalog.add_argument("--manifest-name", default="manifest.json")
    bundle_catalog.add_argument("--output-dir", type=Path, required=True)
    bundle_catalog.add_argument(
        "--archive-output",
        type=Path,
        help="also write the generated catalog bundle as a deterministic .tar.gz archive",
    )
    bundle_catalog.add_argument(
        "--format",
        choices=["path", "text"],
        default="path",
        help="output the generated index path or a compact text summary",
    )
    _add_triage_bundle_option(bundle_catalog)

    verify_bundle = subparsers.add_parser(
        "verify-bundle",
        help="Verify a static report bundle manifest and member digests",
    )
    verify_bundle.add_argument("--path", type=Path, required=True)
    verify_bundle.add_argument("--manifest-name", default="manifest.json")
    verify_bundle.add_argument("--format", choices=["json", "text"], default="json")

    archive_bundle = subparsers.add_parser(
        "archive-bundle",
        help="Verify and package a static report bundle as deterministic tar.gz",
    )
    archive_bundle.add_argument("--path", type=Path, required=True)
    archive_bundle.add_argument("--output", type=Path, required=True)
    archive_bundle.add_argument("--manifest-name", default="manifest.json")
    archive_bundle.add_argument("--format", choices=["json", "text"], default="json")

    verify_bundle_archive = subparsers.add_parser(
        "verify-bundle-archive",
        help="Verify a deterministic tar.gz static report bundle archive",
    )
    verify_bundle_archive.add_argument("--path", type=Path, required=True)
    verify_bundle_archive.add_argument("--manifest-name", default="manifest.json")
    verify_bundle_archive.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    plan_bundle_submission = subparsers.add_parser(
        "plan-bundle-submission",
        help="Build a dry-run submission plan for a verified report bundle",
    )
    plan_bundle_submission.add_argument("--path", type=Path, required=True)
    plan_bundle_submission.add_argument(
        "--target",
        choices=["workbench", "rag", "generic"],
        required=True,
    )
    plan_bundle_submission.add_argument("--endpoint", required=True)
    plan_bundle_submission.add_argument("--manifest-name", default="manifest.json")
    plan_bundle_submission.add_argument("--output", type=Path)
    plan_bundle_submission.add_argument(
        "--fail-on-status",
        choices=["warn", "fail"],
        help="return status 2 when the source bundle triage summary reaches this severity",
    )
    plan_bundle_submission.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    submission_plan_index = subparsers.add_parser(
        "submission-plan-index",
        help="Aggregate dry-run submission plans into one CI/workbench index",
    )
    submission_plan_index.add_argument(
        "--input",
        type=Path,
        action="append",
        required=True,
        help="submission plan JSON file; repeat for multiple plans",
    )
    submission_plan_index.add_argument("--output", type=Path)
    submission_plan_index.add_argument(
        "--fail-on-status",
        choices=["warn", "fail"],
        help="return status 2 when any indexed plan carries this triage severity",
    )
    submission_plan_index.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    validate = subparsers.add_parser(
        "validate",
        help=(
            "Validate a local EDGP JSON report file, static report bundle, "
            "or deterministic bundle archive"
        ),
    )
    validate.add_argument("--path", type=Path, required=True)
    validate.add_argument("--manifest-name", default="manifest.json")
    validate.add_argument("--format", choices=["json", "text"], default="json")
    validate.add_argument(
        "--fail-on-status",
        choices=["warn", "fail"],
        help="return status 2 when a bundle triage summary reaches this severity",
    )

    failure_examples = subparsers.add_parser(
        "failure-examples",
        help="Emit the validation failure example index for workbench ingestion",
    )
    failure_examples.add_argument("--format", choices=["json", "text"], default="json")
    failure_examples.add_argument(
        "--id",
        action="append",
        default=[],
        help="filter examples by stable example id",
    )
    failure_examples.add_argument(
        "--list-codes",
        action="store_true",
        help=(
            "list available ids, contracts, target types, validation codes, "
            "and verifier codes"
        ),
    )
    failure_examples.add_argument(
        "--code",
        action="append",
        default=[],
        help="filter examples by validation or verification failure code",
    )
    failure_examples.add_argument(
        "--contract",
        action="append",
        default=[],
        help="filter examples by documented schema contract",
    )
    failure_examples.add_argument(
        "--target-type",
        action="append",
        choices=[
            "json-file",
            "export-batch",
            "export-batch-archive",
            "report-bundle",
            "report-bundle-archive",
        ],
        default=[],
        help="filter examples by target artifact type",
    )

    benchmark = subparsers.add_parser("benchmark", help="Run a synthetic CSR benchmark")
    benchmark.add_argument("--nodes", type=int, default=1000)
    benchmark.add_argument("--fanout", type=int, default=3)
    benchmark.add_argument(
        "--backend",
        choices=["python", "auto", "numba"],
        default="python",
        help="traversal backend for benchmark reachability queries",
    )
    benchmark.add_argument("--format", choices=["json", "text"], default="json")

    accelerator_status = subparsers.add_parser(
        "accelerator-status",
        help="Report optional traversal accelerator availability",
    )
    accelerator_status.add_argument(
        "--backend",
        choices=["python", "auto", "numba"],
        default="auto",
        help="backend request used to resolve the selected traversal backend",
    )
    accelerator_status.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )

    csr_artifact = subparsers.add_parser(
        "csr-artifact",
        help="Persist an EDGP graph snapshot as memory-mappable CSR arrays",
    )
    csr_artifact.add_argument("--snapshot", type=Path, required=True)
    csr_artifact.add_argument("--output-dir", type=Path, required=True)
    csr_artifact.add_argument("--format", choices=["json", "text"], default="json")

    parallel_query = subparsers.add_parser(
        "parallel-query",
        help="Run independent frozen-CSR reachability queries concurrently",
    )
    parallel_query.add_argument("--snapshot", type=Path, required=True)
    parallel_query.add_argument(
        "--query",
        action="append",
        default=[],
        help="query as dependencies:NODE or dependents:NODE; may be repeated",
    )
    parallel_query.add_argument("--workers", type=int)
    parallel_query.add_argument(
        "--backend",
        choices=["python", "auto", "numba"],
        default="python",
        help="traversal backend for reachability queries",
    )
    parallel_query.add_argument("--format", choices=["json", "text"], default="json")

    performance_report = subparsers.add_parser(
        "performance-report",
        help="Run deterministic CSR benchmark scenarios as an EDGP report",
    )
    performance_report.add_argument("--nodes", type=int, default=1000)
    performance_report.add_argument("--fanout", type=int, default=3)
    performance_report.add_argument(
        "--backend",
        choices=["python", "auto", "numba"],
        default="python",
        help="traversal backend for benchmark reachability queries",
    )
    performance_report.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="benchmark scenario as NODES:FANOUT; may be repeated",
    )
    performance_report.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
    )
    performance_report_bundle = subparsers.add_parser(
        "performance-report-bundle",
        help="Render deterministic CSR benchmark scenarios as a static bundle",
    )
    performance_report_bundle.add_argument("--nodes", type=int, default=1000)
    performance_report_bundle.add_argument("--fanout", type=int, default=3)
    performance_report_bundle.add_argument(
        "--backend",
        choices=["python", "auto", "numba"],
        default="python",
        help="traversal backend for benchmark reachability queries",
    )
    performance_report_bundle.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="benchmark scenario as NODES:FANOUT; may be repeated",
    )
    performance_report_bundle.add_argument("--output-dir", type=Path, required=True)
    performance_report_bundle.add_argument(
        "--format",
        choices=["path", "text"],
        default="path",
    )
    _add_triage_bundle_option(performance_report_bundle)

    query = subparsers.add_parser("query", help="Query a resolved graph")
    query.add_argument(
        "--source",
        choices=[
            "lockfile",
            "dot",
            "sbom",
            "maven-tree",
            "rpm-installed",
            "rpm-repo",
            "albs-build",
        ],
        default="lockfile",
    )
    query.add_argument("--path", type=Path)
    _add_albs_graph_source_options(query)
    query.add_argument("--ecosystem", default="npm")
    query.add_argument(
        "--operation",
        choices=[
            "dependencies",
            "dependents",
            "reachable",
            "path",
            "most-depended-upon",
        ],
        required=True,
    )
    query.add_argument("--node")
    query.add_argument("--target")
    query.add_argument(
        "--direction",
        choices=["dependencies", "dependents"],
        default="dependencies",
    )
    query.add_argument("--limit", type=int, default=10)
    query.add_argument("--rpm-limit", type=int, default=100)
    query.add_argument("--max-requirements", type=int, default=40)
    _add_rpm_repo_source_options(query)

    query_bundle = subparsers.add_parser(
        "query-bundle",
        help="Render a graph traversal query as a static report bundle",
    )
    query_bundle.add_argument(
        "--source",
        choices=[
            "lockfile",
            "dot",
            "sbom",
            "maven-tree",
            "rpm-installed",
            "rpm-repo",
            "albs-build",
        ],
        default="lockfile",
    )
    query_bundle.add_argument("--path", type=Path)
    _add_albs_graph_source_options(query_bundle)
    query_bundle.add_argument("--ecosystem", default="npm")
    query_bundle.add_argument(
        "--operation",
        choices=[
            "dependencies",
            "dependents",
            "reachable",
            "path",
            "most-depended-upon",
        ],
        required=True,
    )
    query_bundle.add_argument("--node")
    query_bundle.add_argument("--target")
    query_bundle.add_argument(
        "--direction",
        choices=["dependencies", "dependents"],
        default="dependencies",
    )
    query_bundle.add_argument("--limit", type=int, default=10)
    query_bundle.add_argument("--rpm-limit", type=int, default=100)
    query_bundle.add_argument("--max-requirements", type=int, default=40)
    query_bundle.add_argument("--output-dir", type=Path, required=True)
    _add_rpm_repo_source_options(query_bundle)
    _add_triage_bundle_option(query_bundle)

    return parser


def main(argv: list[str] | None = None) -> int:
    actual_argv = sys.argv[1:] if argv is None else argv
    command = _command_string(actual_argv)
    args = build_parser().parse_args(actual_argv)

    if args.command == "lockfile":
        root_identifier, graph, resolved_ecosystem = _load_lockfile_project_graph(
            args.path,
            args.ecosystem,
        )
        print(_export(args.format, graph, root=root_identifier, ecosystem=resolved_ecosystem))
        return 0

    if args.command == "npm-diagnostics":
        print(_json(NpmAdapter().diagnose_lockfile(args.path)))
        return 0

    if args.command == "npm-diagnostics-bundle":
        return _print_bundle_result(
            _write_npm_diagnostics_bundle(
                args.path,
                args.output_dir,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "npm-bundle":
        return _print_bundle_result(
            _write_npm_bundle(
                args.path,
                args.output_dir,
                impact_nodes=args.impact_node,
                advisory_path=args.advisories,
                include_license_report=args.license_report or args.fail_on_denied,
                denied_licenses=args.deny_license,
                max_paths=args.limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_denied=args.fail_on_denied,
            fail_on_status=args.fail_on_status,
        )

    if args.command == "dot":
        resolved = DotAdapter().parse_graph(args.path, ecosystem=args.ecosystem)
        print(
            _export(
                args.format,
                resolved.graph,
                root=resolved.root_identifier,
                ecosystem=resolved.ecosystem,
            )
        )
        return 0

    if args.command == "dot-bundle":
        return _print_bundle_result(
            _write_dot_bundle(
                args.path,
                args.output_dir,
                ecosystem=args.ecosystem,
                impact_nodes=args.impact_node,
                max_paths=args.limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "sbom":
        resolved = CycloneDXAdapter().parse_graph(args.path)
        print(
            _export(
                args.format,
                resolved.graph,
                root=resolved.root_identifier,
                ecosystem=resolved.ecosystem,
            )
        )
        return 0

    if args.command == "sbom-bundle":
        return _print_bundle_result(
            _write_sbom_bundle(
                args.path,
                args.output_dir,
                impact_nodes=args.impact_node,
                include_license_report=args.license_report or args.fail_on_denied,
                denied_licenses=args.deny_license,
                max_paths=args.limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_denied=args.fail_on_denied,
            fail_on_status=args.fail_on_status,
        )

    if args.command == "maven-tree":
        resolved = MavenTreeAdapter().parse_tree(args.path)
        print(
            _export(
                args.format,
                resolved.graph,
                root=resolved.root_identifier,
                ecosystem=resolved.ecosystem,
            )
        )
        return 0

    if args.command == "maven-bundle":
        return _print_bundle_result(
            _write_maven_bundle(
                args.path,
                args.output_dir,
                impact_nodes=args.impact_node,
                max_paths=args.limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "rpm-installed":
        resolved = InstalledRpmAdapter().parse_installed(
            limit=args.limit,
            max_requirements=args.max_requirements,
        )
        print(
            _export(
                args.format,
                resolved.graph,
                root=resolved.root_identifier,
                ecosystem=resolved.ecosystem,
            )
        )
        return 0

    if args.command == "rpm-installed-bundle":
        return _print_bundle_result(
            _write_rpm_installed_bundle(
                args.output_dir,
                limit=args.limit,
                max_requirements=args.max_requirements,
                impact_nodes=args.impact_node,
                advisory_path=args.advisories,
                public_advisory_feed_path=args.public_advisory_feed,
                public_advisory_feed_url=args.public_advisory_feed_url,
                albs_build_id=args.albs_build_id,
                albs_build_path=args.albs_build_path,
                albs_build_url=args.albs_build_url,
                albs_base_url=args.albs_base_url,
                libsolv_transaction_path=args.libsolv_transaction,
                include_license_report=args.license_report or args.fail_on_denied,
                denied_licenses=args.deny_license,
                max_paths=args.report_limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_denied=args.fail_on_denied,
            fail_on_status=args.fail_on_status,
        )

    if args.command == "rpm-repo":
        resolved = _load_rpm_repo_project_graph(
            _rpm_repo_source(args.primary, args.source),
            repo_id=args.repo_id,
            package_limit=args.package_limit,
            requirement_limit=args.requirement_limit,
        )
        print(
            _export(
                args.format,
                resolved.graph,
                root=resolved.root_identifier,
                ecosystem=resolved.ecosystem,
            )
        )
        return 0

    if args.command == "rpm-repo-summary":
        resolved = _load_rpm_repo_project_graph(
            _rpm_repo_source(args.primary, args.source),
            repo_id=args.repo_id,
            package_limit=args.package_limit,
            requirement_limit=args.requirement_limit,
        )
        report = build_rpm_repository_summary_report(
            resolved.graph,
            root=resolved.root_identifier,
        )
        if args.format == "text":
            print(_format_rpm_repository_summary_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "rpm-repo-summary-bundle":
        return _print_bundle_result(
            _write_rpm_repo_summary_bundle(
                _rpm_repo_source(args.primary, args.source),
                args.output_dir,
                repo_id=args.repo_id,
                package_limit=args.package_limit,
                requirement_limit=args.requirement_limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
            output_format=args.format,
        )

    if args.command == "rpm-repo-bundle":
        return _print_bundle_result(
            _write_rpm_repo_bundle(
                _rpm_repo_source(args.primary, args.source),
                args.output_dir,
                repo_id=args.repo_id,
                package_limit=args.package_limit,
                requirement_limit=args.requirement_limit,
                impact_nodes=args.impact_node,
                advisory_path=args.advisories,
                public_advisory_feed_path=args.public_advisory_feed,
                public_advisory_feed_url=args.public_advisory_feed_url,
                libsolv_transaction_path=args.libsolv_transaction,
                include_license_report=args.license_report or args.fail_on_denied,
                denied_licenses=args.deny_license,
                max_paths=args.report_limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_denied=args.fail_on_denied,
            fail_on_status=args.fail_on_status,
        )

    if args.command == "rpm-repo-diff":
        report = _build_rpm_repo_diff_report(
            _rpm_repo_diff_source(args.left_primary, args.left_source, "left"),
            _rpm_repo_diff_source(args.right_primary, args.right_source, "right"),
            left_repo_id=args.left_repo_id,
            right_repo_id=args.right_repo_id,
            package_limit=args.package_limit,
            requirement_limit=args.requirement_limit,
        )
        if args.format == "text":
            print(_format_rpm_repository_diff_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "rpm-repo-diff-bundle":
        return _print_bundle_result(
            _write_rpm_repo_diff_bundle(
                _rpm_repo_diff_source(args.left_primary, args.left_source, "left"),
                _rpm_repo_diff_source(args.right_primary, args.right_source, "right"),
                args.output_dir,
                left_repo_id=args.left_repo_id,
                right_repo_id=args.right_repo_id,
                package_limit=args.package_limit,
                requirement_limit=args.requirement_limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
            output_format=args.format,
        )

    if args.command == "albs-build":
        root_identifier, graph, resolved_ecosystem = _load_albs_build_project_graph(
            build_id=args.build_id,
            path=args.path,
            url=args.url,
            base_url=args.base_url,
            task_limit=args.task_limit,
            artifact_limit=args.artifact_limit,
            test_task_limit=args.test_task_limit,
            include_logs=args.include_logs,
        )
        print(
            _export(
                args.format,
                graph,
                root=root_identifier,
                ecosystem=resolved_ecosystem,
            )
        )
        return 0

    if args.command == "albs-artifact-inventory":
        root_identifier, graph, _ = _load_albs_build_project_graph(
            build_id=args.build_id,
            path=args.path,
            url=args.url,
            base_url=args.base_url,
            task_limit=args.task_limit,
            artifact_limit=args.artifact_limit,
            test_task_limit=args.test_task_limit,
            include_logs=args.include_logs,
        )
        report = build_albs_artifact_inventory(graph, root=root_identifier)
        if args.format == "text":
            print(_format_albs_artifact_inventory_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "albs-artifact-inventory-bundle":
        return _print_bundle_result(
            _write_albs_artifact_inventory_bundle(
                args.output_dir,
                build_id=args.build_id,
                path=args.path,
                url=args.url,
                base_url=args.base_url,
                task_limit=args.task_limit,
                artifact_limit=args.artifact_limit,
                test_task_limit=args.test_task_limit,
                include_logs=args.include_logs,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
            output_format=args.format,
        )

    if args.command == "albs-build-timing":
        payload = _load_albs_build_metadata(
            build_id=args.build_id,
            path=args.path,
            url=args.url,
            base_url=args.base_url,
        )
        build_id = str(payload.get("build_id") or payload.get("id") or "unknown")
        report = build_albs_build_timing_report(
            payload,
            root=f"albs-build:{build_id}",
        )
        if args.format == "text":
            print(_format_albs_build_timing_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "albs-build-timing-bundle":
        return _print_bundle_result(
            _write_albs_build_timing_bundle(
                args.output_dir,
                build_id=args.build_id,
                path=args.path,
                url=args.url,
                base_url=args.base_url,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
            output_format=args.format,
        )

    if args.command == "albs-build-bundle":
        return _print_bundle_result(
            _write_albs_build_bundle(
                args.output_dir,
                build_id=args.build_id,
                path=args.path,
                url=args.url,
                base_url=args.base_url,
                task_limit=args.task_limit,
                artifact_limit=args.artifact_limit,
                test_task_limit=args.test_task_limit,
                include_logs=args.include_logs,
                impact_nodes=args.impact_node,
                max_paths=args.report_limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "albs-build-diff":
        left = _load_albs_build_metadata(
            build_id=args.left_build_id,
            path=args.left_path,
            url=args.left_url,
            base_url=args.base_url,
        )
        right = _load_albs_build_metadata(
            build_id=args.right_build_id,
            path=args.right_path,
            url=args.right_url,
            base_url=args.base_url,
        )
        report = build_albs_build_diff_report(left, right)
        if args.format == "text":
            print(_format_albs_build_diff_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "albs-build-diff-bundle":
        return _print_bundle_result(
            _write_albs_build_diff_bundle(
                args.output_dir,
                left_build_id=args.left_build_id,
                left_path=args.left_path,
                left_url=args.left_url,
                right_build_id=args.right_build_id,
                right_path=args.right_path,
                right_url=args.right_url,
                base_url=args.base_url,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
            output_format=args.format,
        )

    if args.command == "albs-log-intelligence":
        payload = _load_albs_build_metadata(
            build_id=args.build_id,
            path=args.path,
            url=args.url,
            base_url=args.base_url,
        )
        report = build_albs_log_intelligence_report(payload)
        if args.format == "text":
            print(_format_albs_log_intelligence_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "albs-log-intelligence-bundle":
        return _print_bundle_result(
            _write_albs_log_intelligence_bundle(
                args.output_dir,
                build_id=args.build_id,
                path=args.path,
                url=args.url,
                base_url=args.base_url,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
            output_format=args.format,
        )

    if args.command == "albs-release-completeness":
        payloads = _load_albs_build_metadata_list(
            build_ids=args.build_id,
            paths=args.path,
            urls=args.url,
            base_url=args.base_url,
        )
        report = build_albs_release_completeness_report(payloads)
        if args.format == "text":
            print(_format_albs_release_completeness_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "albs-release-completeness-bundle":
        return _print_bundle_result(
            _write_albs_release_completeness_bundle(
                args.output_dir,
                build_ids=args.build_id,
                paths=args.path,
                urls=args.url,
                base_url=args.base_url,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
            output_format=args.format,
        )

    if args.command == "rpm-albs-provenance":
        albs_payload = _load_albs_build_metadata(
            build_id=args.build_id,
            path=args.path,
            url=args.url,
            base_url=args.base_url,
        )
        installed = InstalledRpmAdapter().parse_installed(
            limit=args.rpm_limit,
            max_requirements=args.max_requirements,
        )
        report = build_rpm_albs_provenance_report(installed.graph, albs_payload)
        if args.format == "text":
            print(_format_rpm_albs_provenance_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "rpm-albs-provenance-bundle":
        return _print_bundle_result(
            _write_rpm_albs_provenance_bundle(
                args.output_dir,
                build_id=args.build_id,
                path=args.path,
                url=args.url,
                base_url=args.base_url,
                rpm_limit=args.rpm_limit,
                max_requirements=args.max_requirements,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
            output_format=args.format,
        )

    if args.command == "libsolv-bridge":
        print(_json(build_libsolv_bridge_report(args.transaction, args.graph_snapshot)))
        return 0

    if args.command == "libsolv-bundle":
        return _print_bundle_result(
            _write_libsolv_bundle(
                args.transaction,
                args.output_dir,
                graph_snapshot_path=args.graph_snapshot,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "public-advisory-feed":
        report = build_public_advisory_feed_report(
            _load_public_json_source(path=args.path, url=args.url),
            ecosystem=args.ecosystem,
        )
        if args.format == "overlay":
            print(_json(report["overlay"]))
        elif args.format == "text":
            print(_format_public_advisory_feed_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "public-advisory-feed-bundle":
        return _print_bundle_result(
            _write_public_advisory_feed_bundle(
                args.output_dir,
                path=args.path,
                url=args.url,
                ecosystem=args.ecosystem,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
            output_format=args.format,
        )

    if args.command == "fixture-provenance":
        report = build_fixture_provenance(args.fixture_dir)
        if args.format == "text":
            print(_format_fixture_provenance_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "fixture-provenance-bundle":
        return _print_bundle_result(
            _write_fixture_provenance_bundle(
                args.output_dir,
                fixture_dir=args.fixture_dir,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "real-data-coverage":
        report = build_real_data_coverage_report(
            build_fixture_provenance(args.fixture_dir),
            min_public_evidence_percent=args.min_public_evidence_percent,
            fail_on_priority=args.fail_on_priority,
        )
        if args.format == "text":
            print(_format_real_data_coverage_result(report))
        else:
            print(_json(report))
        policy = report.get("policy")
        if isinstance(policy, dict) and policy.get("status") == "fail":
            return 2
        return 0

    if args.command == "real-data-coverage-bundle":
        index_path = _write_real_data_coverage_bundle(
            args.output_dir,
            fixture_dir=args.fixture_dir,
            min_public_evidence_percent=args.min_public_evidence_percent,
            fail_on_priority=args.fail_on_priority,
            command=command,
            include_triage_summary=_include_triage_summary(args),
        )
        result = _print_bundle_result(index_path, fail_on_status=args.fail_on_status)
        if result:
            return result
        if _real_data_coverage_policy_should_fail(index_path.parent):
            return 2
        return 0

    if args.command == "real-data-replacement-plan":
        report = _real_data_replacement_plan_input_report(
            coverage_path=args.coverage,
            fixture_dir=args.fixture_dir,
            fail_on_priority=args.fail_on_priority,
        )
        if args.format == "text":
            print(_format_real_data_replacement_plan_result(report))
        else:
            print(_json(report))
        policy = report.get("policy")
        if isinstance(policy, dict) and policy.get("status") == "fail":
            return 2
        return 0

    if args.command == "real-data-replacement-plan-bundle":
        index_path = _write_real_data_replacement_plan_bundle(
            args.output_dir,
            coverage_path=args.coverage,
            fixture_dir=args.fixture_dir,
            fail_on_priority=args.fail_on_priority,
            command=command,
            include_triage_summary=_include_triage_summary(args),
        )
        result = _print_bundle_result(index_path, fail_on_status=args.fail_on_status)
        if result:
            return result
        if _real_data_replacement_plan_policy_should_fail(index_path.parent):
            return 2
        return 0

    if args.command == "real-data-replacement-plan-diff":
        report = build_real_data_replacement_plan_diff_report(
            _real_data_replacement_plan_diff_input_report(
                plan_path=args.left,
                coverage_path=args.left_coverage,
                fixture_dir=args.left_fixture_dir,
            ),
            _real_data_replacement_plan_diff_input_report(
                plan_path=args.right,
                coverage_path=args.right_coverage,
                fixture_dir=args.right_fixture_dir,
            ),
            left_label=args.left_label,
            right_label=args.right_label,
            fail_on_regression=args.fail_on_regression,
        )
        if args.format == "text":
            print(_format_real_data_replacement_plan_diff_result(report))
        else:
            print(_json(report))
        policy = report.get("policy")
        if isinstance(policy, dict) and policy.get("status") == "fail":
            return 2
        return 0

    if args.command == "real-data-replacement-plan-diff-bundle":
        index_path = _write_real_data_replacement_plan_diff_bundle(
            args.output_dir,
            left_report=_real_data_replacement_plan_diff_input_report(
                plan_path=args.left,
                coverage_path=args.left_coverage,
                fixture_dir=args.left_fixture_dir,
            ),
            right_report=_real_data_replacement_plan_diff_input_report(
                plan_path=args.right,
                coverage_path=args.right_coverage,
                fixture_dir=args.right_fixture_dir,
            ),
            left_label=args.left_label,
            right_label=args.right_label,
            fail_on_regression=args.fail_on_regression,
            command=command,
            include_triage_summary=_include_triage_summary(args),
        )
        result = _print_bundle_result(index_path, fail_on_status=args.fail_on_status)
        if result:
            return result
        if _real_data_replacement_plan_diff_policy_should_fail(index_path.parent):
            return 2
        return 0

    if args.command == "real-data-coverage-diff":
        report = build_real_data_coverage_diff_report(
            _real_data_coverage_input_report(
                report_path=args.left,
                fixture_dir=args.left_fixture_dir,
            ),
            _real_data_coverage_input_report(
                report_path=args.right,
                fixture_dir=args.right_fixture_dir,
            ),
            left_label=args.left_label,
            right_label=args.right_label,
            fail_on_regression=args.fail_on_regression,
        )
        if args.format == "text":
            print(_format_real_data_coverage_diff_result(report))
        else:
            print(_json(report))
        policy = report.get("policy")
        if isinstance(policy, dict) and policy.get("status") == "fail":
            return 2
        return 0

    if args.command == "real-data-coverage-diff-bundle":
        index_path = _write_real_data_coverage_diff_bundle(
            args.output_dir,
            left_report=_real_data_coverage_input_report(
                report_path=args.left,
                fixture_dir=args.left_fixture_dir,
            ),
            right_report=_real_data_coverage_input_report(
                report_path=args.right,
                fixture_dir=args.right_fixture_dir,
            ),
            left_label=args.left_label,
            right_label=args.right_label,
            fail_on_regression=args.fail_on_regression,
            command=command,
            include_triage_summary=_include_triage_summary(args),
        )
        result = _print_bundle_result(index_path, fail_on_status=args.fail_on_status)
        if result:
            return result
        if _real_data_coverage_diff_policy_should_fail(index_path.parent):
            return 2
        return 0

    if args.command == "diff":
        report = json.loads(diff_snapshot_files(args.left, args.right))
        _attach_diff_policy(
            report,
            fail_on_change=args.fail_on_change,
            fail_on_kind=args.fail_on_kind,
        )
        if args.format == "text":
            print(_format_graph_diff_report(report))
        else:
            print(_json(report))
        if _diff_policy_failed(report):
            return 2
        return 0

    if args.command == "diff-bundle":
        index_path = _write_graph_diff_bundle(
            args.left,
            args.right,
            args.output_dir,
            command=command,
            include_triage_summary=_include_triage_summary(args),
            fail_on_change=args.fail_on_change,
            fail_on_kind=args.fail_on_kind,
        )
        report_path = args.output_dir / "graph-diff.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if args.archive_output is not None:
            archive_report = write_report_bundle_archive(
                args.output_dir,
                args.archive_output,
            )
            if archive_report.get("ok") is not True:
                raise ValueError("Could not archive generated graph diff bundle")
        return _print_graph_diff_bundle_result(
            index_path,
            report,
            archive_output=args.archive_output,
            output_format=args.format,
            fail_on_status=args.fail_on_status,
        )

    if args.command == "diff-tree":
        selector, left_selector, right_selector = _diff_tree_selector_args(args)
        report_text = diff_tree_snapshot_files(
            args.left,
            args.right,
            selector=selector,
            left_selector=left_selector,
            right_selector=right_selector,
            direction=args.direction,
            depth=args.depth,
        )
        report = json.loads(report_text)
        _attach_diff_tree_policy(report, fail_on_kind=args.fail_on_kind)
        if args.format == "text":
            print(_format_graph_diff_tree_report(report))
        else:
            print(_json(report))
        if _diff_tree_policy_failed(report):
            return 2
        return 0

    if args.command == "diff-tree-bundle":
        selector, left_selector, right_selector = _diff_tree_selector_args(args)
        index_path = _write_graph_diff_tree_bundle(
            args.left,
            args.right,
            args.output_dir,
            selector=selector,
            left_selector=left_selector,
            right_selector=right_selector,
            direction=args.direction,
            depth=args.depth,
            command=command,
            include_triage_summary=_include_triage_summary(args),
            fail_on_kind=args.fail_on_kind,
        )
        report_path = args.output_dir / "graph-diff-tree.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if args.archive_output is not None:
            archive_report = write_report_bundle_archive(
                args.output_dir,
                args.archive_output,
            )
            if archive_report.get("ok") is not True:
                raise ValueError("Could not archive generated graph diff-tree bundle")
        return _print_graph_diff_tree_bundle_result(
            index_path,
            report,
            archive_output=args.archive_output,
            output_format=args.format,
            fail_on_status=args.fail_on_status,
        )

    if args.command == "impact":
        root_identifier, graph, resolved_ecosystem = _load_source_project_graph(
            args.source,
            args.path,
            args.ecosystem,
            albs_url=args.albs_url,
            rpm_limit=args.rpm_limit,
            max_requirements=args.max_requirements,
            rpm_repo_source=args.rpm_repo_source,
            repo_id=args.repo_id,
            package_limit=args.package_limit,
            requirement_limit=args.requirement_limit,
        )
        node = _resolve_node_selector(graph, args.node, role="node")
        print(
            _json(
                build_impact_report(
                    graph,
                    node=node,
                    root=root_identifier,
                    ecosystem=resolved_ecosystem,
                    max_paths=args.limit,
                )
            )
        )
        return 0

    if args.command == "impact-bundle":
        return _print_bundle_result(
            _write_impact_report_bundle(
                args.output_dir,
                source=args.source,
                path=args.path,
                albs_url=args.albs_url,
                ecosystem=args.ecosystem,
                node=args.node,
                max_paths=args.limit,
                rpm_limit=args.rpm_limit,
                max_requirements=args.max_requirements,
                rpm_repo_source=args.rpm_repo_source,
                repo_id=args.repo_id,
                package_limit=args.package_limit,
                requirement_limit=args.requirement_limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "advisory":
        root_identifier, graph, resolved_ecosystem = _load_source_project_graph(
            args.source,
            args.path,
            args.ecosystem,
            albs_url=args.albs_url,
            rpm_limit=args.rpm_limit,
            max_requirements=args.max_requirements,
            rpm_repo_source=args.rpm_repo_source,
            repo_id=args.repo_id,
            package_limit=args.package_limit,
            requirement_limit=args.requirement_limit,
        )
        advisory_report = build_advisory_report(
            _load_advisory_payload(
                advisory_path=args.advisories,
                public_advisory_feed_path=args.public_advisory_feed,
                public_advisory_feed_url=args.public_advisory_feed_url,
                ecosystem=resolved_ecosystem,
            ),
            graph,
            root=root_identifier,
            ecosystem=resolved_ecosystem,
            max_paths=args.limit,
        )
        print(_json(advisory_report))
        if args.fail_on_findings and _advisory_report_should_fail(
            advisory_report,
            min_severity=args.fail_min_severity,
        ):
            return 2
        return 0

    if args.command == "advisory-bundle":
        index_path = _write_advisory_report_bundle(
            args.output_dir,
            source=args.source,
            path=args.path,
            albs_url=args.albs_url,
            ecosystem=args.ecosystem,
            advisory_path=args.advisories,
            public_advisory_feed_path=args.public_advisory_feed,
            public_advisory_feed_url=args.public_advisory_feed_url,
            max_paths=args.limit,
            rpm_limit=args.rpm_limit,
            max_requirements=args.max_requirements,
            rpm_repo_source=args.rpm_repo_source,
            repo_id=args.repo_id,
            package_limit=args.package_limit,
            requirement_limit=args.requirement_limit,
            command=command,
            include_triage_summary=_include_triage_summary(args),
        )
        report_path = index_path.parent / "advisory-report.json"
        advisory_report = json.loads(report_path.read_text(encoding="utf-8"))
        if args.fail_on_findings and _advisory_report_should_fail(
            advisory_report,
            min_severity=args.fail_min_severity,
        ):
            print(index_path)
            return 2
        return _print_bundle_result(index_path, fail_on_status=args.fail_on_status)

    if args.command == "license-report":
        root_identifier, graph, resolved_ecosystem = _load_source_project_graph(
            args.source,
            args.path,
            args.ecosystem,
            albs_url=args.albs_url,
            rpm_limit=args.rpm_limit,
            max_requirements=args.max_requirements,
            rpm_repo_source=args.rpm_repo_source,
            repo_id=args.repo_id,
            package_limit=args.package_limit,
            requirement_limit=args.requirement_limit,
        )
        license_report = build_license_report(
            graph,
            root=root_identifier,
            ecosystem=resolved_ecosystem,
            denied_licenses=args.deny_license,
        )
        print(_json(license_report))
        if args.fail_on_denied and _license_report_should_fail(license_report):
            return 2
        return 0

    if args.command == "license-report-bundle":
        return _print_bundle_result(
            _write_license_report_bundle(
                args.output_dir,
                source=args.source,
                path=args.path,
                albs_url=args.albs_url,
                ecosystem=args.ecosystem,
                denied_licenses=args.deny_license,
                rpm_limit=args.rpm_limit,
                max_requirements=args.max_requirements,
                rpm_repo_source=args.rpm_repo_source,
                repo_id=args.repo_id,
                package_limit=args.package_limit,
                requirement_limit=args.requirement_limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_denied=args.fail_on_denied,
            fail_on_status=args.fail_on_status,
        )

    if args.command == "triage-summary":
        if args.bundle is not None:
            triage_report = build_triage_summary_from_bundle(
                args.bundle,
                manifest_name=args.manifest_name,
            )
        else:
            triage_report = build_triage_summary_from_paths(args.input)
        if args.format == "text":
            print(_format_triage_summary_report(triage_report))
        else:
            print(_json(triage_report))
        if _triage_summary_should_fail(
            triage_report,
            min_status=args.fail_on_status,
        ):
            return 2
        return 0

    if args.command == "report":
        output_path = write_report_file(args.snapshot or args.input, args.output)
        print(output_path)
        return 0

    if args.command == "export-batch":
        manifest = write_graph_export_batch(
            args.snapshot,
            args.output_dir,
            formats=args.format,
            manifest_name=args.manifest_name,
            command=command,
        )
        print(_json(manifest))
        return 0

    if args.command == "verify-export-batch":
        report = verify_graph_export_batch(args.path, manifest_name=args.manifest_name)
        if args.format == "text":
            print(_format_export_batch_verification_report(report))
        else:
            print(_json(report))
        return 0 if report["ok"] else 1

    if args.command == "archive-export-batch":
        report = write_graph_export_batch_archive(
            args.path,
            args.output,
            manifest_name=args.manifest_name,
        )
        if args.format == "text":
            print(_format_export_batch_archive_report(report))
        else:
            print(_json(report))
        return 0 if report["ok"] else 1

    if args.command == "verify-export-batch-archive":
        report = verify_graph_export_batch_archive(
            args.path,
            manifest_name=args.manifest_name,
        )
        if args.format == "text":
            print(_format_export_batch_archive_report(report))
        else:
            print(_json(report))
        return 0 if report["ok"] else 1

    if args.command == "plan-export-batch-submission":
        plan = build_graph_export_batch_submission_plan(
            args.path,
            target=args.target,
            endpoint=args.endpoint,
            manifest_name=args.manifest_name,
            command=command,
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(_json(plan) + "\n", encoding="utf-8")
        if args.format == "text":
            print(_format_export_batch_submission_plan(plan))
        else:
            print(_json(plan))
        return 0 if plan["ok"] else 1

    if args.command == "report-bundle":
        index_path = write_report_bundle(
            args.input,
            args.output_dir,
            index_name=args.index_name,
            manifest_name=args.manifest_name,
            bundle_metadata={"sourceKind": "edgp-json", "command": command},
            include_triage_summary=_include_triage_summary(args),
        )
        if args.archive_output is not None:
            archive_report = write_report_bundle_archive(
                args.output_dir,
                args.archive_output,
                manifest_name=args.manifest_name,
            )
            if archive_report.get("ok") is not True:
                raise ValueError("Could not archive generated report bundle")
        return _print_bundle_result(
            index_path,
            archive_output=args.archive_output,
            fail_on_status=args.fail_on_status,
            output_format=args.format,
        )

    if args.command == "bundle-catalog":
        index_path = _write_bundle_catalog_bundle(
            args.output_dir,
            bundle_dirs=args.bundle,
            manifest_name=args.manifest_name,
            archive_output=args.archive_output,
            command=command,
            include_triage_summary=_include_triage_summary(args),
        )
        return _print_bundle_catalog_result(
            index_path,
            output_format=args.format,
            fail_on_status=args.fail_on_status,
        )

    if args.command == "verify-bundle":
        report = verify_report_bundle(args.path, manifest_name=args.manifest_name)
        if args.format == "text":
            print(_format_verification_report(report))
        else:
            print(_json(report))
        return 0 if report["ok"] else 1

    if args.command == "archive-bundle":
        report = write_report_bundle_archive(
            args.path,
            args.output,
            manifest_name=args.manifest_name,
        )
        if args.format == "text":
            print(_format_bundle_archive_report(report))
        else:
            print(_json(report))
        return 0 if report["ok"] else 1

    if args.command == "verify-bundle-archive":
        report = verify_report_bundle_archive(
            args.path,
            manifest_name=args.manifest_name,
        )
        if args.format == "text":
            print(_format_bundle_archive_report(report))
        else:
            print(_json(report))
        return 0 if report["ok"] else 1

    if args.command == "plan-bundle-submission":
        plan = build_report_bundle_submission_plan(
            args.path,
            target=args.target,
            endpoint=args.endpoint,
            manifest_name=args.manifest_name,
            command=command,
        )
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(_json(plan) + "\n", encoding="utf-8")
        if args.format == "text":
            print(_format_report_bundle_submission_plan(plan))
        else:
            print(_json(plan))
        if _submission_plan_should_fail_on_status(
            plan,
            min_status=args.fail_on_status,
        ):
            return 2
        return 0 if plan["ok"] else 1

    if args.command == "submission-plan-index":
        index = build_submission_plan_index(args.input, command=command)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(_json(index) + "\n", encoding="utf-8")
        if args.format == "text":
            print(_format_submission_plan_index(index))
        else:
            print(_json(index))
        if _submission_plan_index_should_fail_on_status(
            index,
            min_status=args.fail_on_status,
        ):
            return 2
        return 0 if index["ok"] else 1

    if args.command == "validate":
        report = validate_target(args.path, manifest_name=args.manifest_name)
        if args.format == "text":
            print(_format_validation_report(report))
        else:
            print(_json(report))
        if not report["ok"]:
            return 1
        if _validation_report_should_fail_on_status(
            report,
            min_status=args.fail_on_status,
        ):
            return 2
        return 0

    if args.command == "failure-examples":
        index = _filter_failure_example_index(
            build_failure_example_index(),
            ids=args.id,
            codes=args.code,
            contracts=args.contract,
            target_types=args.target_type,
        )
        if args.list_codes:
            summary = build_failure_example_filter_listing(index)
            if args.format == "text":
                print(_format_failure_example_filter_summary(summary))
            else:
                print(_json(summary))
            return 0
        if args.format == "text":
            print(_format_failure_example_index(index))
        else:
            print(_json(index))
        return 0

    if args.command == "benchmark":
        report = run_synthetic_benchmark(
            nodes=args.nodes,
            fanout=args.fanout,
            backend=args.backend,
        )
        if args.format == "text":
            print(_format_benchmark_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "accelerator-status":
        report = accelerator_profile(requested_backend=args.backend)
        if args.format == "text":
            print(_format_accelerator_status_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "csr-artifact":
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        graph = graph_from_snapshot(snapshot)
        manifest = write_frozen_csr_artifact(graph.freeze(), args.output_dir)
        if args.format == "text":
            print(
                _format_csr_artifact_manifest(
                    manifest,
                    output_dir=args.output_dir,
                )
            )
        else:
            print(_json(manifest))
        return 0

    if args.command == "parallel-query":
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
        graph = graph_from_snapshot(snapshot).freeze()
        report = run_parallel_reachability_queries(
            graph,
            _parallel_query_specs(args.query),
            max_workers=args.workers,
            backend=args.backend,
        )
        if args.format == "text":
            print(_format_parallel_query_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "performance-report":
        report = build_performance_report(
            _performance_scenarios(
                args.scenario,
                nodes=args.nodes,
                fanout=args.fanout,
            ),
            backend=args.backend,
        )
        if args.format == "text":
            print(_format_performance_report_result(report))
        else:
            print(_json(report))
        return 0

    if args.command == "performance-report-bundle":
        return _print_bundle_result(
            _write_performance_report_bundle(
                args.output_dir,
                scenarios=_performance_scenarios(
                    args.scenario,
                    nodes=args.nodes,
                    fanout=args.fanout,
                ),
                backend=args.backend,
                command=command,
                include_triage_summary=(
                    args.triage_summary or args.fail_on_status is not None
                ),
            ),
            fail_on_status=args.fail_on_status,
            output_format=args.format,
        )

    if args.command == "query":
        _, graph = _load_source_graph(
            args.source,
            args.path,
            args.ecosystem,
            albs_url=args.albs_url,
            rpm_limit=args.rpm_limit,
            max_requirements=args.max_requirements,
            rpm_repo_source=args.rpm_repo_source,
            repo_id=args.repo_id,
            package_limit=args.package_limit,
            requirement_limit=args.requirement_limit,
        )
        print(
            _json(
                _query_graph(
                    graph,
                    operation=args.operation,
                    node=args.node,
                    target=args.target,
                    direction=args.direction,
                    limit=args.limit,
                )
            )
        )
        return 0

    if args.command == "query-bundle":
        return _print_bundle_result(
            _write_query_report_bundle(
                args.output_dir,
                source=args.source,
                path=args.path,
                albs_url=args.albs_url,
                ecosystem=args.ecosystem,
                operation=args.operation,
                node=args.node,
                target=args.target,
                direction=args.direction,
                limit=args.limit,
                rpm_limit=args.rpm_limit,
                max_requirements=args.max_requirements,
                rpm_repo_source=args.rpm_repo_source,
                repo_id=args.repo_id,
                package_limit=args.package_limit,
                requirement_limit=args.requirement_limit,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "demo":
        registry = _demo_registry()
        root = "app"
        version = "1.0.0"
    else:
        registry = _load_registry(args.registry)
        root = args.root
        version = args.version

    resolver = CDCLResolver(registry)
    graph = resolver.solve(root, version)
    print(_export(args.format, graph, root=f"{root}=={version}"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
