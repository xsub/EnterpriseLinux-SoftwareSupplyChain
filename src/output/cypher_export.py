from __future__ import annotations

import json

from src.core_graph.sparse_matrix import CSRDependencyGraph


class CypherExporter:
    """Translate a CSR dependency graph into deterministic Neo4j Cypher."""

    @staticmethod
    def export_to_cypher(csr_graph: CSRDependencyGraph) -> str:
        queries = [
            "CREATE CONSTRAINT package_id_unique IF NOT EXISTS "
            "FOR (p:Package) REQUIRE p.id IS UNIQUE;"
        ]

        for vertex_id in sorted(csr_graph.reverse_vertex_map):
            package_id = csr_graph.reverse_vertex_map[vertex_id]
            queries.append(f"MERGE (:Package {{id: {json.dumps(package_id)}}});")

        for edge in csr_graph.edges():
            queries.append(
                "MATCH (s:Package {id: "
                f"{json.dumps(edge.source)}"
                "}) MATCH (t:Package {id: "
                f"{json.dumps(edge.target)}"
                "}) MERGE (s)-[:DEPENDS_ON {type: "
                f"{edge.relationship_type}"
                "}]->(t);"
            )

        return "\n".join(queries)
