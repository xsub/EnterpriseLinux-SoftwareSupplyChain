"""Command-line entry points for resolving and exporting dependency graphs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.adapters.dot import DotAdapter
from src.adapters.npm import NpmAdapter
from src.adapters.rpm_installed import InstalledRpmAdapter
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.output.cypher_export import CypherExporter
from src.output.json_export import GraphJsonExporter
from src.output.sbom_security import CycloneDXExporter
from src.resolver.cdcl_engine import CDCLResolver
from src.resolver.registry_mock import RegistryMock


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


def _load_lockfile_graph(path: Path, ecosystem: str) -> tuple[str, CSRDependencyGraph]:
    if ecosystem != "npm":
        raise ValueError(f"Unsupported lockfile ecosystem: {ecosystem}")
    resolved = NpmAdapter().parse_lockfile_graph(path)
    return resolved.root_identifier, resolved.graph


def _load_source_graph(
    source: str,
    path: Path,
    ecosystem: str,
) -> tuple[str, CSRDependencyGraph]:
    if source == "lockfile":
        return _load_lockfile_graph(path, ecosystem)
    if source == "dot":
        resolved = DotAdapter().parse_graph(path, ecosystem=ecosystem)
        return resolved.root_identifier, resolved.graph
    raise ValueError(f"Unsupported graph source: {source}")


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
    }


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
    lockfile.add_argument("--ecosystem", choices=["npm"], default="npm")
    lockfile.add_argument("--format", choices=["cypher", "cyclonedx", "json"], default="cypher")

    dot = subparsers.add_parser("dot", help="Export a directed DOT dependency graph")
    dot.add_argument("--path", type=Path, required=True)
    dot.add_argument("--ecosystem", default="rpm")
    dot.add_argument("--format", choices=["cypher", "cyclonedx", "json"], default="json")

    rpm_installed = subparsers.add_parser(
        "rpm-installed", help="Export a graph from the local RPM database"
    )
    rpm_installed.add_argument("--limit", type=int, default=100)
    rpm_installed.add_argument("--max-requirements", type=int, default=40)
    rpm_installed.add_argument(
        "--format", choices=["cypher", "cyclonedx", "json"], default="json"
    )

    query = subparsers.add_parser("query", help="Query a resolved graph")
    query.add_argument("--source", choices=["lockfile", "dot"], default="lockfile")
    query.add_argument("--path", type=Path, required=True)
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

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "lockfile":
        root_identifier, graph = _load_lockfile_graph(args.path, args.ecosystem)
        print(_export(args.format, graph, root=root_identifier, ecosystem=args.ecosystem))
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

    if args.command == "query":
        _, graph = _load_source_graph(args.source, args.path, args.ecosystem)
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
