"""Shared graph and impact artifact writer for static EDGP bundles."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Sequence

from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.impact_report import build_impact_report
from src.output.json_export import GraphJsonExporter
from src.output.report_bundle import write_report_bundle

NodeResolver = Callable[[CSRDependencyGraph, str], str]


def write_graph_report_bundle(
    resolved: ResolvedProjectGraph,
    output_dir: Path,
    *,
    graph_name: str,
    impact_nodes: Sequence[str] | None = None,
    node_resolver: NodeResolver | None = None,
    max_paths: int = 20,
    extra_reports_after_graph: Sequence[Path] = (),
    extra_reports: Sequence[Path] = (),
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_paths = []

    graph_path = output_dir / f"{graph_name}.json"
    graph_path.write_text(
        GraphJsonExporter.export_to_json(
            resolved.graph,
            root=resolved.root_identifier,
            ecosystem=resolved.ecosystem,
        ),
        encoding="utf-8",
    )
    report_paths.append(graph_path)
    report_paths.extend(extra_reports_after_graph)

    for selector in impact_nodes or []:
        node = node_resolver(resolved.graph, selector) if node_resolver else selector
        impact_path = output_dir / f"impact-{safe_artifact_stem(node)}.json"
        impact_path.write_text(
            _json(
                build_impact_report(
                    resolved.graph,
                    node=node,
                    root=resolved.root_identifier,
                    ecosystem=resolved.ecosystem,
                    max_paths=max_paths,
                )
            ),
            encoding="utf-8",
        )
        report_paths.append(impact_path)

    report_paths.extend(extra_reports)
    return write_report_bundle(report_paths, output_dir)


def safe_artifact_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-_")
    return stem or "report"


def _json(payload: dict[str, object]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True)
