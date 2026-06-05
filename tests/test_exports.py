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
