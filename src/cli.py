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
    max_paths: int = 20,
    command: str | None = None,
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
    )


def _write_maven_bundle(
    path: Path,
    output_dir: Path,
    *,
    impact_nodes: list[str] | None = None,
    max_paths: int = 20,
    command: str | None = None,
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
    )


def _write_dot_bundle(
    path: Path,
    output_dir: Path,
    *,
    ecosystem: str = "rpm",
    impact_nodes: list[str] | None = None,
    max_paths: int = 20,
    command: str | None = None,
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
    )


def _write_sbom_bundle(
    path: Path,
    output_dir: Path,
    *,
    impact_nodes: list[str] | None = None,
    max_paths: int = 20,
    command: str | None = None,
) -> Path:
    resolved = CycloneDXAdapter().parse_graph(path)
    return write_graph_report_bundle(
        resolved,
        output_dir,
        graph_name="sbom-graph",
        impact_nodes=impact_nodes,
        node_resolver=_resolve_impact_node,
        max_paths=max_paths,
        bundle_metadata={"sourceKind": "cyclonedx-sbom", "command": command},
    )


def _write_rpm_installed_bundle(
    output_dir: Path,
    *,
    limit: int = 100,
    max_requirements: int = 40,
    impact_nodes: list[str] | None = None,
    max_paths: int = 20,
    command: str | None = None,
) -> Path:
    resolved = InstalledRpmAdapter().parse_installed(
        limit=limit,
        max_requirements=max_requirements,
    )
    return write_graph_report_bundle(
        resolved,
        output_dir,
        graph_name="rpm-installed-graph",
        impact_nodes=impact_nodes,
        node_resolver=_resolve_impact_node,
        max_paths=max_paths,
        bundle_metadata={"sourceKind": "rpm-installed", "command": command},
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
    max_paths: int = 20,
    command: str | None = None,
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
    rpm_installed_bundle.add_argument("--report-limit", type=int, default=20)

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
    rpm_repo_bundle.add_argument("--report-limit", type=int, default=20)

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

    albs_build_diff = subparsers.add_parser(
        "albs-build-diff",
        help="Compare two public ALBS builds or local ALBS JSON fixtures",
    )
    albs_build_diff.add_argument("--left-build-id")
    albs_build_diff.add_argument("--left-path", type=Path)
    albs_build_diff.add_argument("--right-build-id")
    albs_build_diff.add_argument("--right-path", type=Path)
    albs_build_diff.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)

    albs_log_intelligence = subparsers.add_parser(
        "albs-log-intelligence",
        help="Extract build-log signals from public ALBS build metadata",
    )
    albs_log_input = albs_log_intelligence.add_mutually_exclusive_group(required=True)
    albs_log_input.add_argument("--build-id")
    albs_log_input.add_argument("--path", type=Path)
    albs_log_intelligence.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)

    albs_release_completeness = subparsers.add_parser(
        "albs-release-completeness",
        help="Summarize architecture, signing, and test coverage across ALBS builds",
    )
    albs_release_completeness.add_argument("--build-id", action="append", default=[])
    albs_release_completeness.add_argument("--path", type=Path, action="append", default=[])
    albs_release_completeness.add_argument("--base-url", default=DEFAULT_ALBS_BASE_URL)

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

    libsolv_bridge = subparsers.add_parser(
        "libsolv-bridge",
        help="Report libsolv command availability and parse transaction output",
    )
    libsolv_bridge.add_argument("--transaction", type=Path)

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
    advisory.add_argument("--limit", type=int, default=20)
    advisory.add_argument("--rpm-limit", type=int, default=100)
    advisory.add_argument("--max-requirements", type=int, default=40)
    _add_rpm_repo_source_options(advisory)

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
        print(
            _write_npm_bundle(
                args.path,
                args.output_dir,
                impact_nodes=args.impact_node,
                advisory_path=args.advisories,
                max_paths=args.limit,
                command=command,
            )
        )
        return 0

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
        print(
            _write_dot_bundle(
                args.path,
                args.output_dir,
                ecosystem=args.ecosystem,
                impact_nodes=args.impact_node,
                max_paths=args.limit,
                command=command,
            )
        )
        return 0

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
        print(
            _write_sbom_bundle(
                args.path,
                args.output_dir,
                impact_nodes=args.impact_node,
                max_paths=args.limit,
                command=command,
            )
        )
        return 0

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
        print(
            _write_maven_bundle(
                args.path,
                args.output_dir,
                impact_nodes=args.impact_node,
                max_paths=args.limit,
                command=command,
            )
        )
        return 0

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
        print(
            _write_rpm_installed_bundle(
                args.output_dir,
                limit=args.limit,
                max_requirements=args.max_requirements,
                impact_nodes=args.impact_node,
                max_paths=args.report_limit,
                command=command,
            )
        )
        return 0

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
        print(
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
                max_paths=args.report_limit,
                command=command,
            )
        )
        return 0

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
        print(
            _write_rpm_repo_diff_bundle(
                _rpm_repo_diff_source(args.left_primary, args.left_source, "left"),
                _rpm_repo_diff_source(args.right_primary, args.right_source, "right"),
                args.output_dir,
                left_repo_id=args.left_repo_id,
                right_repo_id=args.right_repo_id,
                package_limit=args.package_limit,
                requirement_limit=args.requirement_limit,
                command=command,
            )
        )
        return 0

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
        print(
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
            )
        )
        return 0

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

    if args.command == "albs-log-intelligence":
        payload = _load_albs_build_metadata(
            build_id=args.build_id,
            path=args.path,
            base_url=args.base_url,
        )
        print(_json(build_albs_log_intelligence_report(payload)))
        return 0

    if args.command == "albs-release-completeness":
        payloads = _load_albs_build_metadata_list(
            build_ids=args.build_id,
            paths=args.path,
            base_url=args.base_url,
        )
        print(_json(build_albs_release_completeness_report(payloads)))
        return 0

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

    if args.command == "libsolv-bridge":
        print(_json(build_libsolv_bridge_report(args.transaction)))
        return 0

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
        if args.fail_on_findings and advisory_report["summary"]["findings"]:
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
        )
        print(index_path)
        return 0

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
        return 0 if report["ok"] else 1

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
