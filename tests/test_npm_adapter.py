"""npm adapter tests for building CSR graphs from package-lock fixtures."""

import json
from pathlib import Path

from src.adapters.npm import NpmAdapter
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.output.json_export import GraphJsonExporter
from src.reports.npm_summary import build_npm_summary_report


def test_npm_package_lock_v3_builds_csr_graph() -> None:
    resolved = NpmAdapter().parse_lockfile_graph(Path("tests/fixtures/package-lock.json"))

    assert resolved.root_identifier == "demo-app==1.0.0"
    assert resolved.graph.get_dependencies("demo-app==1.0.0") == [
        "@scope/tool==2.1.0",
        "left-pad==1.3.0",
    ]
    assert resolved.graph.get_dependencies("@scope/tool==2.1.0") == [
        "nested==1.0.1",
        "left-pad==1.3.0",
    ]
    assert resolved.graph.get_dependencies("left-pad==1.3.0") == []
    metadata = resolved.graph.get_vertex_metadata("@scope/tool==2.1.0")
    assert metadata["ecosystem"] == "npm"
    assert metadata["name"] == "@scope/tool"
    assert metadata["version"] == "2.1.0"
    assert metadata["purl"] == "pkg:npm/%40scope/tool@2.1.0"
    assert metadata["package_path"] == "node_modules/@scope/tool"
    assert metadata["resolved"] == "https://registry.npmjs.org/@scope/tool/-/tool-2.1.0.tgz"
    assert metadata["source_url"] == metadata["resolved"]
    assert metadata["integrity"] == "sha512-demo-tool"
    assert metadata["checksum"] == "sha512-demo-tool"
    assert metadata["license"] == "MIT"
    assert metadata["classification"] == "direct"
    assert metadata["direct_dependency"] == "True"

    edge_metadata = resolved.graph.get_edge_metadata(
        "demo-app==1.0.0",
        "@scope/tool==2.1.0",
    )
    assert edge_metadata["scope"] == "runtime"
    assert edge_metadata["constraint"] == "^2.0.0"
    assert edge_metadata["resolved_version"] == "2.1.0"
    assert edge_metadata["source_file"] == "tests/fixtures/package-lock.json"
    assert edge_metadata["direct"] == "True"


def test_npm_scope_classification_for_dev_optional_and_peer_dependencies() -> None:
    dev = NpmAdapter().parse_lockfile_graph(
        Path("tests/fixtures/npm/dev-dependencies-package-lock.json")
    )
    assert dev.graph.get_edge_metadata(
        "dev-app==1.0.0",
        "test-runner==2.0.0",
    )["scope"] == "dev"
    assert dev.graph.get_vertex_metadata("test-helper==1.0.0")["classification"] == (
        "transitive"
    )
    assert dev.graph.get_vertex_metadata("test-helper==1.0.0")["dependency_scope"] == "dev"

    optional = NpmAdapter().parse_lockfile_graph(
        Path("tests/fixtures/npm/optional-dependencies-package-lock.json")
    )
    assert optional.graph.get_edge_metadata(
        "optional-app==1.0.0",
        "native-addon==1.0.0",
    )["scope"] == "optional"
    assert optional.graph.get_vertex_metadata("native-addon==1.0.0")[
        "dependency_scope"
    ] == "optional"

    peer = NpmAdapter().parse_lockfile_graph(
        Path("tests/fixtures/npm/peer-dependencies-package-lock.json")
    )
    assert peer.graph.get_edge_metadata("plugin==1.0.0", "react==18.2.0")[
        "scope"
    ] == "peer"
    assert peer.graph.get_vertex_metadata("plugin==1.0.0")["peer_dependencies"] == "react"


def test_npm_summary_report_lists_required_lockfile_outputs() -> None:
    resolved = NpmAdapter().parse_lockfile_graph(
        Path("tests/fixtures/npm/missing-integrity-package-lock.json")
    )

    report = build_npm_summary_report(
        resolved.graph,
        root=resolved.root_identifier,
        source_file="tests/fixtures/npm/missing-integrity-package-lock.json",
    )

    assert report["schema"] == "edgp.npm.summary.v1"
    assert report["summary"]["directDependencies"] == 1
    assert report["summary"]["transitiveDependencies"] == 0
    assert report["summary"]["packagesWithoutIntegrity"] == 1
    assert report["summary"]["packagesWithRemoteTarballUrls"] == 1
    assert report["packagesWithoutIntegrity"][0]["id"] == "no-integrity==1.0.0"
    assert report["remoteTarballDomains"] == [
        {"domain": "registry.npmjs.org", "packages": 1}
    ]


def test_graph_json_export_includes_normalized_npm_package_and_edge_metadata() -> None:
    resolved = NpmAdapter().parse_lockfile_graph(
        Path("tests/fixtures/npm/simple-package-lock.json")
    )

    payload = json.loads(
        GraphJsonExporter.export_to_json(
            resolved.graph,
            root=resolved.root_identifier,
            ecosystem=resolved.ecosystem,
        )
    )

    left_pad = next(node for node in payload["nodes"] if node["id"] == "left-pad==1.3.0")
    edge = next(
        edge
        for edge in payload["edges"]
        if edge["source"] == "simple-app==1.0.0"
        and edge["target"] == "left-pad==1.3.0"
    )
    assert left_pad["purl"] == "pkg:npm/left-pad@1.3.0"
    assert left_pad["package"]["ecosystem"] == "npm"
    assert left_pad["package"]["checksum"] == "sha512-simple-left-pad"
    assert edge["scope"] == "runtime"
    assert edge["constraint"] == "^1.3.0"
    assert edge["resolvedVersion"] == "1.3.0"
    assert edge["direct"] is True


def test_mixed_ecosystem_graph_keeps_npm_as_normal_nodes() -> None:
    graph = CSRDependencyGraph()
    graph.add_vertex("container==demo", metadata={"ecosystem": "oci"})
    graph.add_vertex(
        "bash==5.2.26-6.el10",
        metadata={"ecosystem": "rpm", "name": "bash", "version": "5.2.26-6.el10"},
    )
    graph.add_vertex(
        "left-pad==1.3.0",
        metadata={
            "ecosystem": "npm",
            "name": "left-pad",
            "version": "1.3.0",
            "purl": "pkg:npm/left-pad@1.3.0",
        },
    )
    graph.add_dependency_edge("container==demo", "bash==5.2.26-6.el10")
    graph.add_dependency_edge(
        "bash==5.2.26-6.el10",
        "left-pad==1.3.0",
        metadata={"scope": "runtime"},
    )

    payload = json.loads(
        GraphJsonExporter.export_to_json(graph, root="container==demo", ecosystem="mixed")
    )

    assert payload["stats"] == {"edges": 2, "nodes": 3}
    assert any(node.get("purl") == "pkg:npm/left-pad@1.3.0" for node in payload["nodes"])


def test_npm_package_lock_diagnostics_report_nested_conflicts() -> None:
    payload = NpmAdapter().diagnose_lockfile(
        Path("tests/fixtures/package-lock-conflict.json")
    )

    assert payload["schema"] == "edgp.npm.diagnostics.v1"
    assert payload["summary"] == {
        "packages": 4,
        "duplicatePackageNames": 1,
        "nestedResolutionConflicts": 1,
        "unresolvedDependencies": 1,
    }
    assert payload["duplicatePackageNames"] == [
        {
            "package": "shared",
            "versions": [
                {"paths": ["node_modules/shared"], "version": "1.0.0"},
                {
                    "paths": ["node_modules/tool/node_modules/shared"],
                    "version": "2.0.0",
                },
            ],
        }
    ]
    assert payload["nestedResolutionConflicts"][0]["dependency"] == "shared"
    assert payload["nestedResolutionConflicts"][0]["versions"] == ["1.0.0", "2.0.0"]
    assert payload["unresolvedDependencies"][0]["dependency"] == "missing"
