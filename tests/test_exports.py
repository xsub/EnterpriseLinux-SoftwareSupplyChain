"""Exporter tests for Cypher and CycloneDX graph serialization."""

import json

from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.output.cypher_export import CypherExporter
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
    assert component["externalReferences"] == [
        {
            "type": "distribution",
            "url": "https://registry.npmjs.org/@scope/tool/-/tool-2.1.0.tgz",
        }
    ]
    assert component["licenses"] == [{"license": {"name": "MIT"}}]
    assert {"name": "edgp:integrity", "value": "sha512-demo"} in component["properties"]
