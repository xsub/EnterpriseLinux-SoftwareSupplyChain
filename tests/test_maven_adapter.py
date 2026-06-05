"""Maven dependency tree adapter tests for Java graph ingestion."""

from pathlib import Path

from src.adapters.maven import MavenTreeAdapter


def test_maven_tree_adapter_builds_resolved_graph() -> None:
    resolved = MavenTreeAdapter().parse_tree(Path("tests/fixtures/maven-tree.txt"))

    assert resolved.root_identifier == "com.example:demo-app==1.0.0"
    assert resolved.ecosystem == "maven"
    assert resolved.graph.get_dependencies("com.example:demo-app==1.0.0") == [
        "com.fasterxml.jackson.core:jackson-databind==2.17.0",
        "junit:junit==4.13.2",
        "org.slf4j:slf4j-api==1.7.36",
    ]
    assert resolved.graph.get_dependencies(
        "com.fasterxml.jackson.core:jackson-databind==2.17.0"
    ) == ["com.fasterxml.jackson.core:jackson-core==2.17.0"]
    assert resolved.graph.get_vertex_metadata("junit:junit==4.13.2") == {
        "ecosystem": "maven",
        "source": "maven-dependency-tree",
        "group": "junit",
        "artifact": "junit",
        "packaging": "jar",
        "scope": "test",
    }
