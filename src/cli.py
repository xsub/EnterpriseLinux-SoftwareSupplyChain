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
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.graph_diff import diff_snapshot_files
from src.impact_report import build_impact_report
from src.libsolv_bridge import build_libsolv_bridge_report
from src.license_policy import build_license_report
from src.output.cypher_export import CypherExporter
from src.output.graph_bundle import write_graph_report_bundle
from src.output.html_report import write_report_file
from src.output.json_export import GraphJsonExporter
from src.output.report_bundle import verify_report_bundle, write_report_bundle
from src.output.sbom_security import CycloneDXExporter
from src.performance_report import build_performance_report
from src.public_advisory_feed import build_public_advisory_feed_report
from src.resolver.cdcl_engine import CDCLResolver
from src.resolver.registry_mock import RegistryMock
from src.rpm_albs_provenance import build_rpm_albs_provenance_report
from src.rpm_repository_diff import build_rpm_repository_diff_report
from src.rpm_repository_summary import build_rpm_repository_summary_report
from src.schema_validation import validate_target
from src.triage_summary import (
    build_triage_summary_from_bundle,
    build_triage_summary_from_paths,
)
from scripts.generate_failure_example_index import (
    build_failure_example_filter_listing,
    build_failure_example_index,
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
    failure_list = report.get("failures", [])
    if isinstance(failure_list, list) and failure_list:
        first_failure = failure_list[0]
        if isinstance(first_failure, dict):
            parts.append(f"firstFailure={first_failure.get('code', 'unknown')}")
    return " ".join(parts)


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
    albs_base_url: str = DEFAULT_ALBS_BASE_URL,
) -> list[Path]:
    if albs_build_id is None and albs_build_path is None:
        return []
    albs_payload = _load_albs_build_metadata(
        build_id=albs_build_id,
        path=albs_build_path,
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
    fail_on_denied: bool = False,
    fail_on_status: str | None = None,
) -> int:
    print(index_path)
    if fail_on_denied and _bundle_license_report_should_fail(index_path.parent):
        return 2
    if _bundle_triage_summary_should_fail(index_path.parent, min_status=fail_on_status):
        return 2
    return 0


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
    if not isinstance(triage_summary, dict):
        return False
    status = str(triage_summary.get("status", "pass")).lower()
    return _TRIAGE_STATUS_RANKS.get(status, 0) >= _TRIAGE_STATUS_RANKS[min_status]


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
    right_build_id: str | None = None,
    right_path: Path | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    left = _load_albs_build_metadata(
        build_id=left_build_id,
        path=left_path,
        base_url=base_url,
    )
    right = _load_albs_build_metadata(
        build_id=right_build_id,
        path=right_path,
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
    base_url: str = DEFAULT_ALBS_BASE_URL,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    payload = _load_albs_build_metadata(
        build_id=build_id,
        path=path,
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
    base_url: str = DEFAULT_ALBS_BASE_URL,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    payloads = _load_albs_build_metadata_list(
        build_ids=build_ids or [],
        paths=paths or [],
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


def _write_performance_report_bundle(
    output_dir: Path,
    *,
    scenarios: Sequence[tuple[int, int]],
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "performance-report.json"
    report_path.write_text(
        _json(build_performance_report(scenarios)),
        encoding="utf-8",
    )
    return write_report_bundle(
        [report_path],
        output_dir,
        bundle_metadata={"sourceKind": "performance-report", "command": command},
        include_triage_summary=include_triage_summary,
    )


def _write_rpm_albs_provenance_bundle(
    output_dir: Path,
    *,
    build_id: str | None = None,
    path: Path | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
    rpm_limit: int = 100,
    max_requirements: int = 40,
    command: str | None = None,
    include_triage_summary: bool = False,
) -> Path:
    albs_payload = _load_albs_build_metadata(
        build_id=build_id,
        path=path,
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
        raise ValueError("Either --build-id or --path is required for ALBS build input")
    return resolved.root_identifier, resolved.graph, resolved.ecosystem


def _load_albs_build_metadata(
    *,
    build_id: str | None = None,
    path: Path | None = None,
    base_url: str = DEFAULT_ALBS_BASE_URL,
) -> dict[str, Any]:
    adapter = AlbsBuildAdapter()
    if path is not None:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"ALBS build fixture must be a JSON object: {path}")
        return payload
    if build_id is not None:
        return adapter.fetch_build_metadata(build_id, base_url=base_url)
    raise ValueError("Either --build-id or --path is required for ALBS build input")


def _load_albs_build_metadata_list(
    *,
    build_ids: Sequence[str],
    paths: Sequence[Path],
    base_url: str = DEFAULT_ALBS_BASE_URL,
) -> list[dict[str, Any]]:
    payloads = [
        _load_albs_build_metadata(path=path, base_url=base_url)
        for path in paths
    ]
    payloads.extend(
        _load_albs_build_metadata(build_id=build_id, base_url=base_url)
        for build_id in build_ids
    )
    if not payloads:
        raise ValueError("At least one ALBS --path or --build-id is required")
    return payloads


def _write_albs_build_bundle(
    output_dir: Path,
    *,
    build_id: str | None = None,
    path: Path | None = None,
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
    payload = _load_albs_build_metadata(build_id=build_id, path=path, base_url=base_url)
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
    rpm_limit: int = 100,
    max_requirements: int = 40,
    rpm_repo_source: str | None = None,
    repo_id: str = "public-rpm-repository",
    package_limit: int = 5000,
    requirement_limit: int = 40,
) -> tuple[str, CSRDependencyGraph, str]:
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
        if path is None:
            raise ValueError("--path is required for albs-build source")
        return _load_albs_build_project_graph(path=path)
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
    _add_triage_bundle_option(rpm_repo_diff_bundle)

    albs_build = subparsers.add_parser(
        "albs-build",
        help="Export a graph from public ALBS build metadata",
    )
    albs_input = albs_build.add_mutually_exclusive_group(required=True)
    albs_input.add_argument("--build-id")
    albs_input.add_argument("--path", type=Path)
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
    albs_artifact_inventory.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    albs_artifact_inventory.add_argument("--task-limit", type=int, default=50)
    albs_artifact_inventory.add_argument("--artifact-limit", type=int, default=200)
    albs_artifact_inventory.add_argument("--test-task-limit", type=int, default=50)
    albs_artifact_inventory.add_argument("--include-logs", action="store_true")

    albs_build_timing = subparsers.add_parser(
        "albs-build-timing",
        help="Export ALBS build task and artifact timing from public build metadata",
    )
    albs_timing_input = albs_build_timing.add_mutually_exclusive_group(required=True)
    albs_timing_input.add_argument("--build-id")
    albs_timing_input.add_argument("--path", type=Path)
    albs_build_timing.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)

    albs_build_bundle = subparsers.add_parser(
        "albs-build-bundle",
        help="Render public ALBS build metadata as a static graph bundle",
    )
    albs_bundle_input = albs_build_bundle.add_mutually_exclusive_group(required=True)
    albs_bundle_input.add_argument("--build-id")
    albs_bundle_input.add_argument("--path", type=Path)
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
    albs_build_diff.add_argument("--right-build-id")
    albs_build_diff.add_argument("--right-path", type=Path)
    albs_build_diff.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)

    albs_build_diff_bundle = subparsers.add_parser(
        "albs-build-diff-bundle",
        help="Render public ALBS build comparison as a static bundle",
    )
    albs_build_diff_bundle.add_argument("--left-build-id")
    albs_build_diff_bundle.add_argument("--left-path", type=Path)
    albs_build_diff_bundle.add_argument("--right-build-id")
    albs_build_diff_bundle.add_argument("--right-path", type=Path)
    albs_build_diff_bundle.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    albs_build_diff_bundle.add_argument("--output-dir", type=Path, required=True)
    _add_triage_bundle_option(albs_build_diff_bundle)

    albs_log_intelligence = subparsers.add_parser(
        "albs-log-intelligence",
        help="Extract build-log signals from public ALBS build metadata",
    )
    albs_log_input = albs_log_intelligence.add_mutually_exclusive_group(required=True)
    albs_log_input.add_argument("--build-id")
    albs_log_input.add_argument("--path", type=Path)
    albs_log_intelligence.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)

    albs_log_intelligence_bundle = subparsers.add_parser(
        "albs-log-intelligence-bundle",
        help="Render public ALBS build-log signals as a static bundle",
    )
    albs_log_bundle_input = albs_log_intelligence_bundle.add_mutually_exclusive_group(
        required=True
    )
    albs_log_bundle_input.add_argument("--build-id")
    albs_log_bundle_input.add_argument("--path", type=Path)
    albs_log_intelligence_bundle.add_argument(
        "--base-url",
        default=DEFAULT_ALBS_BASE_URL,
    )
    albs_log_intelligence_bundle.add_argument("--output-dir", type=Path, required=True)
    _add_triage_bundle_option(albs_log_intelligence_bundle)

    albs_release_completeness = subparsers.add_parser(
        "albs-release-completeness",
        help="Summarize architecture, signing, and test coverage across ALBS builds",
    )
    albs_release_completeness.add_argument("--build-id", action="append", default=[])
    albs_release_completeness.add_argument("--path", type=Path, action="append", default=[])
    albs_release_completeness.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)

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
        "--base-url",
        default=DEFAULT_ALBS_BASE_URL,
    )
    albs_release_completeness_bundle.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    _add_triage_bundle_option(albs_release_completeness_bundle)

    rpm_albs_provenance = subparsers.add_parser(
        "rpm-albs-provenance",
        help="Join installed RPMs to artifacts from a public ALBS build",
    )
    rpm_albs_input = rpm_albs_provenance.add_mutually_exclusive_group(required=True)
    rpm_albs_input.add_argument("--build-id")
    rpm_albs_input.add_argument("--path", type=Path)
    rpm_albs_provenance.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    rpm_albs_provenance.add_argument("--rpm-limit", type=int, default=100)
    rpm_albs_provenance.add_argument("--max-requirements", type=int, default=40)

    rpm_albs_provenance_bundle = subparsers.add_parser(
        "rpm-albs-provenance-bundle",
        help="Render installed RPM to public ALBS artifact provenance as a bundle",
    )
    rpm_albs_bundle_input = rpm_albs_provenance_bundle.add_mutually_exclusive_group(
        required=True
    )
    rpm_albs_bundle_input.add_argument("--build-id")
    rpm_albs_bundle_input.add_argument("--path", type=Path)
    rpm_albs_provenance_bundle.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)
    rpm_albs_provenance_bundle.add_argument("--rpm-limit", type=int, default=100)
    rpm_albs_provenance_bundle.add_argument("--max-requirements", type=int, default=40)
    rpm_albs_provenance_bundle.add_argument("--output-dir", type=Path, required=True)
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
        "--format", choices=["report", "overlay"], default="report"
    )

    diff = subparsers.add_parser("diff", help="Diff two EDGP JSON graph snapshots")
    diff.add_argument("--left", type=Path, required=True)
    diff.add_argument("--right", type=Path, required=True)

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
    impact.add_argument("--ecosystem", default="npm")
    impact.add_argument("--node", required=True)
    impact.add_argument("--limit", type=int, default=20)
    impact.add_argument("--rpm-limit", type=int, default=100)
    impact.add_argument("--max-requirements", type=int, default=40)
    _add_rpm_repo_source_options(impact)

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
    license_report.add_argument("--ecosystem", default="npm")
    license_report.add_argument("--deny-license", action="append", default=[])
    license_report.add_argument("--fail-on-denied", action="store_true")
    license_report.add_argument("--rpm-limit", type=int, default=100)
    license_report.add_argument("--max-requirements", type=int, default=40)
    _add_rpm_repo_source_options(license_report)

    triage_summary = subparsers.add_parser(
        "triage-summary",
        help="Aggregate EDGP reports or a report bundle into one triage summary",
    )
    triage_input = triage_summary.add_mutually_exclusive_group(required=True)
    triage_input.add_argument("--bundle", type=Path)
    triage_input.add_argument("--input", type=Path, action="append", default=[])
    triage_summary.add_argument("--manifest-name", default="manifest.json")
    triage_summary.add_argument(
        "--fail-on-status",
        choices=["warn", "fail"],
        help="return status 2 when the triage status is at least this severity",
    )

    report = subparsers.add_parser("report", help="Render a local HTML JSON report")
    report_input = report.add_mutually_exclusive_group(required=True)
    report_input.add_argument("--snapshot", type=Path)
    report_input.add_argument("--input", type=Path)
    report.add_argument("--output", type=Path, required=True)

    report_bundle = subparsers.add_parser(
        "report-bundle", help="Render multiple local HTML JSON reports with an index"
    )
    report_bundle.add_argument("--input", type=Path, action="append", required=True)
    report_bundle.add_argument("--output-dir", type=Path, required=True)
    report_bundle.add_argument("--index-name", default="index.html")
    report_bundle.add_argument("--manifest-name", default="manifest.json")
    _add_triage_bundle_option(report_bundle)

    verify_bundle = subparsers.add_parser(
        "verify-bundle",
        help="Verify a static report bundle manifest and member digests",
    )
    verify_bundle.add_argument("--path", type=Path, required=True)
    verify_bundle.add_argument("--manifest-name", default="manifest.json")
    verify_bundle.add_argument("--format", choices=["json", "text"], default="json")

    validate = subparsers.add_parser(
        "validate",
        help="Validate a local EDGP JSON report file or static report bundle",
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
        choices=["json-file", "report-bundle"],
        default=[],
        help="filter examples by target artifact type",
    )

    benchmark = subparsers.add_parser("benchmark", help="Run a synthetic CSR benchmark")
    benchmark.add_argument("--nodes", type=int, default=1000)
    benchmark.add_argument("--fanout", type=int, default=3)

    performance_report = subparsers.add_parser(
        "performance-report",
        help="Run deterministic CSR benchmark scenarios as an EDGP report",
    )
    performance_report.add_argument("--nodes", type=int, default=1000)
    performance_report.add_argument("--fanout", type=int, default=3)
    performance_report.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="benchmark scenario as NODES:FANOUT; may be repeated",
    )
    performance_report_bundle = subparsers.add_parser(
        "performance-report-bundle",
        help="Render deterministic CSR benchmark scenarios as a static bundle",
    )
    performance_report_bundle.add_argument("--nodes", type=int, default=1000)
    performance_report_bundle.add_argument("--fanout", type=int, default=3)
    performance_report_bundle.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="benchmark scenario as NODES:FANOUT; may be repeated",
    )
    performance_report_bundle.add_argument("--output-dir", type=Path, required=True)
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
    query.add_argument("--direction", choices=["dependencies", "dependents"], default="dependencies")
    query.add_argument("--limit", type=int, default=10)
    query.add_argument("--rpm-limit", type=int, default=100)
    query.add_argument("--max-requirements", type=int, default=40)
    _add_rpm_repo_source_options(query)

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
        print(
            _json(
                build_rpm_repository_summary_report(
                    resolved.graph,
                    root=resolved.root_identifier,
                )
            )
        )
        return 0

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
        print(
            _json(
                _build_rpm_repo_diff_report(
                    _rpm_repo_diff_source(args.left_primary, args.left_source, "left"),
                    _rpm_repo_diff_source(args.right_primary, args.right_source, "right"),
                    left_repo_id=args.left_repo_id,
                    right_repo_id=args.right_repo_id,
                    package_limit=args.package_limit,
                    requirement_limit=args.requirement_limit,
                )
            )
        )
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
        )

    if args.command == "albs-build":
        root_identifier, graph, resolved_ecosystem = _load_albs_build_project_graph(
            build_id=args.build_id,
            path=args.path,
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
            base_url=args.base_url,
            task_limit=args.task_limit,
            artifact_limit=args.artifact_limit,
            test_task_limit=args.test_task_limit,
            include_logs=args.include_logs,
        )
        print(_json(build_albs_artifact_inventory(graph, root=root_identifier)))
        return 0

    if args.command == "albs-build-timing":
        payload = _load_albs_build_metadata(
            build_id=args.build_id,
            path=args.path,
            base_url=args.base_url,
        )
        build_id = str(payload.get("build_id") or payload.get("id") or "unknown")
        print(
            _json(
                build_albs_build_timing_report(
                    payload,
                    root=f"albs-build:{build_id}",
                )
            )
        )
        return 0

    if args.command == "albs-build-bundle":
        return _print_bundle_result(
            _write_albs_build_bundle(
                args.output_dir,
                build_id=args.build_id,
                path=args.path,
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
            base_url=args.base_url,
        )
        right = _load_albs_build_metadata(
            build_id=args.right_build_id,
            path=args.right_path,
            base_url=args.base_url,
        )
        print(_json(build_albs_build_diff_report(left, right)))
        return 0

    if args.command == "albs-build-diff-bundle":
        return _print_bundle_result(
            _write_albs_build_diff_bundle(
                args.output_dir,
                left_build_id=args.left_build_id,
                left_path=args.left_path,
                right_build_id=args.right_build_id,
                right_path=args.right_path,
                base_url=args.base_url,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "albs-log-intelligence":
        payload = _load_albs_build_metadata(
            build_id=args.build_id,
            path=args.path,
            base_url=args.base_url,
        )
        print(_json(build_albs_log_intelligence_report(payload)))
        return 0

    if args.command == "albs-log-intelligence-bundle":
        return _print_bundle_result(
            _write_albs_log_intelligence_bundle(
                args.output_dir,
                build_id=args.build_id,
                path=args.path,
                base_url=args.base_url,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "albs-release-completeness":
        payloads = _load_albs_build_metadata_list(
            build_ids=args.build_id,
            paths=args.path,
            base_url=args.base_url,
        )
        print(_json(build_albs_release_completeness_report(payloads)))
        return 0

    if args.command == "albs-release-completeness-bundle":
        return _print_bundle_result(
            _write_albs_release_completeness_bundle(
                args.output_dir,
                build_ids=args.build_id,
                paths=args.path,
                base_url=args.base_url,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "rpm-albs-provenance":
        albs_payload = _load_albs_build_metadata(
            build_id=args.build_id,
            path=args.path,
            base_url=args.base_url,
        )
        installed = InstalledRpmAdapter().parse_installed(
            limit=args.rpm_limit,
            max_requirements=args.max_requirements,
        )
        print(_json(build_rpm_albs_provenance_report(installed.graph, albs_payload)))
        return 0

    if args.command == "rpm-albs-provenance-bundle":
        return _print_bundle_result(
            _write_rpm_albs_provenance_bundle(
                args.output_dir,
                build_id=args.build_id,
                path=args.path,
                base_url=args.base_url,
                rpm_limit=args.rpm_limit,
                max_requirements=args.max_requirements,
                command=command,
                include_triage_summary=_include_triage_summary(args),
            ),
            fail_on_status=args.fail_on_status,
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
        else:
            print(_json(report))
        return 0

    if args.command == "diff":
        print(diff_snapshot_files(args.left, args.right))
        return 0

    if args.command == "impact":
        root_identifier, graph, resolved_ecosystem = _load_source_project_graph(
            args.source,
            args.path,
            args.ecosystem,
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

    if args.command == "advisory":
        root_identifier, graph, resolved_ecosystem = _load_source_project_graph(
            args.source,
            args.path,
            args.ecosystem,
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

    if args.command == "license-report":
        root_identifier, graph, resolved_ecosystem = _load_source_project_graph(
            args.source,
            args.path,
            args.ecosystem,
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

    if args.command == "triage-summary":
        if args.bundle is not None:
            triage_report = build_triage_summary_from_bundle(
                args.bundle,
                manifest_name=args.manifest_name,
            )
        else:
            triage_report = build_triage_summary_from_paths(args.input)
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

    if args.command == "report-bundle":
        index_path = write_report_bundle(
            args.input,
            args.output_dir,
            index_name=args.index_name,
            manifest_name=args.manifest_name,
            bundle_metadata={"sourceKind": "edgp-json", "command": command},
            include_triage_summary=_include_triage_summary(args),
        )
        return _print_bundle_result(index_path, fail_on_status=args.fail_on_status)

    if args.command == "verify-bundle":
        report = verify_report_bundle(args.path, manifest_name=args.manifest_name)
        if args.format == "text":
            print(_format_verification_report(report))
        else:
            print(_json(report))
        return 0 if report["ok"] else 1

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
        print(_json(run_synthetic_benchmark(nodes=args.nodes, fanout=args.fanout)))
        return 0

    if args.command == "performance-report":
        print(
            _json(
                build_performance_report(
                    _performance_scenarios(
                        args.scenario,
                        nodes=args.nodes,
                        fanout=args.fanout,
                    )
                )
            )
        )
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
                command=command,
                include_triage_summary=(
                    args.triage_summary or args.fail_on_status is not None
                ),
            ),
            fail_on_status=args.fail_on_status,
        )

    if args.command == "query":
        _, graph = _load_source_graph(
            args.source,
            args.path,
            args.ecosystem,
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
