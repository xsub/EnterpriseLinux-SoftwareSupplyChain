"""Maven dependency tree adapter tests for Java graph ingestion."""

from pathlib import Path

from src.adapters.maven import (
    MAVEN_RELATIONSHIP_OMITTED,
    MAVEN_RELATIONSHIP_OPTIONAL,
    MavenTreeAdapter,
)


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
        "coordinate": "junit:junit:jar:4.13.2:test",
        "scope": "test",
    }


def test_maven_tree_adapter_disambiguates_classifier_artifacts() -> None:
    resolved = MavenTreeAdapter().parse_tree(
        Path("tests/fixtures/maven-tree-classifier.txt")
    )

    assert resolved.root_identifier == "com.example:classifier-app==1.0.0"
    assert resolved.graph.get_dependencies("com.example:classifier-app==1.0.0") == [
        "com.example:native-lib==1.0.0",
        "com.example:native-lib:linux-x86_64==1.0.0",
        "com.example:toolkit:test-fixtures==2.0.0",
    ]
    assert resolved.graph.get_vertex_metadata(
        "com.example:native-lib:linux-x86_64==1.0.0"
    ) == {
        "ecosystem": "maven",
        "source": "maven-dependency-tree",
        "group": "com.example",
        "artifact": "native-lib",
        "packaging": "jar",
        "coordinate": "com.example:native-lib:jar:linux-x86_64:1.0.0:runtime",
        "scope": "runtime",
        "classifier": "linux-x86_64",
    }


def test_maven_tree_adapter_disambiguates_non_jar_artifacts() -> None:
    resolved = MavenTreeAdapter().parse_tree(
        Path("tests/fixtures/maven-tree-packaging.txt")
    )

    assert resolved.root_identifier == "com.example:packaging-app==1.0.0"
    assert resolved.graph.get_dependencies("com.example:packaging-app==1.0.0") == [
        "com.example:platform==1.0.0",
        "com.example:platform:pom==1.0.0",
    ]
    assert resolved.graph.get_vertex_metadata("com.example:platform:pom==1.0.0") == {
        "ecosystem": "maven",
        "source": "maven-dependency-tree",
        "group": "com.example",
        "artifact": "platform",
        "packaging": "pom",
        "coordinate": "com.example:platform:pom:1.0.0:import",
        "scope": "import",
    }


def test_maven_tree_adapter_preserves_optional_and_omitted_markers() -> None:
    resolved = MavenTreeAdapter().parse_tree(Path("tests/fixtures/maven-tree-markers.txt"))

    assert resolved.root_identifier == "com.example:marker-app==1.0.0"
    assert resolved.graph.get_dependencies("com.example:marker-app==1.0.0") == [
        "org.example:optional-lib==1.2.3",
        "org.example:conflict-lib==1.0.0",
        "org.example:runtime-lib==2.0.0",
    ]
    assert resolved.graph.get_vertex_metadata("org.example:optional-lib==1.2.3") == {
        "ecosystem": "maven",
        "source": "maven-dependency-tree",
        "group": "org.example",
        "artifact": "optional-lib",
        "packaging": "jar",
        "coordinate": "org.example:optional-lib:jar:1.2.3:compile",
        "scope": "compile",
        "optional": "true",
    }
    assert resolved.graph.get_vertex_metadata("org.example:conflict-lib==1.0.0") == {
        "ecosystem": "maven",
        "source": "maven-dependency-tree",
        "group": "org.example",
        "artifact": "conflict-lib",
        "packaging": "jar",
        "coordinate": "org.example:conflict-lib:jar:1.0.0:compile",
        "scope": "compile",
        "omitted": "true",
        "omittedReason": "conflict with 2.0.0",
    }
    edge_types = {
        edge.target: edge.relationship_type
        for edge in resolved.graph.edges()
        if edge.source == "com.example:marker-app==1.0.0"
    }
    assert edge_types["org.example:optional-lib==1.2.3"] == MAVEN_RELATIONSHIP_OPTIONAL
    assert edge_types["org.example:conflict-lib==1.0.0"] == MAVEN_RELATIONSHIP_OMITTED
