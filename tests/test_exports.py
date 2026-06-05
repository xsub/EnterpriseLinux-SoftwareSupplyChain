"""Exporter tests for Cypher and CycloneDX graph serialization."""

import json

from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.output.cypher_export import CypherExporter
from src.output.json_export import GraphJsonExporter
from src.output.sbom_security import CycloneDXExporter


def test_cypher_export_contains_nodes_and_relationships() -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")

    cypher = CypherExporter.export_to_cypher(graph)

    assert "CREATE CONSTRAINT package_id_unique" in cypher
    assert 'MERGE (:Package {id: "app==1.0.0"});' in cypher
    assert "DEPENDS_ON" in cypher


def test_cyclonedx_export_contains_dependency_references() -> None:
    graph = CSRDependencyGraph()
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")

    payload = json.loads(CycloneDXExporter.export_to_json(graph, root="app==1.0.0"))

    assert payload["bomFormat"] == "CycloneDX"
    assert payload["metadata"]["component"]["bom-ref"] == "app==1.0.0"
    assert {"ref": "app==1.0.0", "dependsOn": ["lib==1.0.0"]} in payload[
        "dependencies"
    ]


def test_cyclonedx_export_uses_npm_purls_for_scoped_packages() -> None:
    graph = CSRDependencyGraph()
    graph.add_vertex(
        "@scope/tool==2.1.0",
        metadata={
            "ecosystem": "npm",
            "resolved": "https://registry.npmjs.org/@scope/tool/-/tool-2.1.0.tgz",
            "integrity": "sha512-demo",
            "license": "MIT",
        },
    )

    payload = json.loads(
        CycloneDXExporter.export_to_json(
            graph,
            root="@scope/tool==2.1.0",
            ecosystem="npm",
        )
    )
    component = payload["components"][0]

    assert component["purl"] == "pkg:npm/%40scope/tool@2.1.0"
    assert component["type"] == "library"
    assert component["externalReferences"] == [
        {
            "type": "distribution",
            "url": "https://registry.npmjs.org/@scope/tool/-/tool-2.1.0.tgz",
        }
    ]
    assert component["licenses"] == [{"license": {"name": "MIT"}}]
    assert {"name": "edgp:integrity", "value": "sha512-demo"} in component["properties"]
    assert {"name": "edgp:purl", "value": "pkg:npm/%40scope/tool@2.1.0"} not in component[
        "properties"
    ]


def test_graph_json_export_contains_nodes_edges_and_rankings() -> None:
    graph = CSRDependencyGraph()
    graph.add_vertex("app==1.0.0", metadata={"ecosystem": "npm"})
    graph.add_vertex("lib==1.0.0", metadata={"ecosystem": "npm"})
    graph.add_dependency_edge("app==1.0.0", "lib==1.0.0")

    payload = json.loads(
        GraphJsonExporter.export_to_json(
            graph,
            root="app==1.0.0",
            ecosystem="npm",
        )
    )

    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["stats"] == {"edges": 1, "nodes": 2}
    assert {"source": "app==1.0.0", "target": "lib==1.0.0", "relationshipType": 1} in payload[
        "edges"
    ]
    assert {
        "id": "lib==1.0.0",
        "name": "lib",
        "version": "1.0.0",
        "dependencies": [],
        "dependents": ["app==1.0.0"],
        "metadata": {"ecosystem": "npm"},
    } in payload["nodes"]
    assert payload["rankings"]["mostDependedUpon"] == [
        {"package": "lib==1.0.0", "dependents": 1}
    ]


def test_cyclonedx_export_uses_rpm_purls_with_qualifiers() -> None:
    graph = CSRDependencyGraph()
    graph.add_vertex(
        "curl==7.50.3-1.fc25",
        metadata={
            "ecosystem": "rpm",
            "vendor": "Fedora",
            "arch": "i386",
            "distro": "fedora-25",
        },
    )

    payload = json.loads(
        CycloneDXExporter.export_to_json(
            graph,
            root="curl==7.50.3-1.fc25",
            ecosystem="rpm",
        )
    )

    assert payload["components"][0]["purl"] == (
        "pkg:rpm/fedora/curl@7.50.3-1.fc25?arch=i386&distro=fedora-25"
    )


def test_cyclonedx_export_uses_pypi_purls() -> None:
    graph = CSRDependencyGraph()
    graph.add_vertex("Requests==2.31.0", metadata={"ecosystem": "pypi"})

    payload = json.loads(
        CycloneDXExporter.export_to_json(
            graph,
            root="Requests==2.31.0",
            ecosystem="pypi",
        )
    )

    assert payload["components"][0]["purl"] == "pkg:pypi/requests@2.31.0"


def test_cyclonedx_export_uses_cargo_purls() -> None:
    graph = CSRDependencyGraph()
    graph.add_vertex("Serde==1.0.197", metadata={"ecosystem": "cargo"})

    payload = json.loads(
        CycloneDXExporter.export_to_json(
            graph,
            root="Serde==1.0.197",
            ecosystem="cargo",
        )
    )

    assert payload["components"][0]["purl"] == "pkg:cargo/serde@1.0.197"
