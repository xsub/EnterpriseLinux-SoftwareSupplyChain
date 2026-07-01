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
        "org.slf4j:slf4j-api==1.7.36",
        "com.fasterxml.jackson.core:jackson-databind==2.17.0",
        "junit:junit==4.13.2",
    ]
    assert resolved.graph.get_dependencies(
        "com.fasterxml.jackson.core:jackson-databind==2.17.0"
    ) == ["com.fasterxml.jackson.core:jackson-core==2.17.0"]
    metadata = resolved.graph.get_vertex_metadata("junit:junit==4.13.2")
    assert metadata["ecosystem"] == "maven"
    assert metadata["source"] == "maven-tree.txt"
    assert metadata["package_manager"] == "maven"
    assert metadata["purl"] == "pkg:maven/junit/junit@4.13.2"
    assert metadata["group"] == "junit"
    assert metadata["artifact"] == "junit"
    assert metadata["packaging"] == "jar"
    assert metadata["coordinate"] == "junit:junit:jar:4.13.2:test"
    assert metadata["scope"] == "test"
    assert metadata["classification"] == "direct"
    assert resolved.graph.get_edge_metadata("com.example:demo-app==1.0.0", "junit:junit==4.13.2")[
        "scope"
    ] == "test"


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
    metadata = resolved.graph.get_vertex_metadata(
        "com.example:native-lib:linux-x86_64==1.0.0"
    )
    assert metadata["purl"] == "pkg:maven/com.example/native-lib@1.0.0"
    assert metadata["group"] == "com.example"
    assert metadata["artifact"] == "native-lib"
    assert metadata["packaging"] == "jar"
    assert metadata["coordinate"] == (
        "com.example:native-lib:jar:linux-x86_64:1.0.0:runtime"
    )
    assert metadata["scope"] == "runtime"
    assert metadata["classifier"] == "linux-x86_64"


def test_maven_tree_adapter_disambiguates_non_jar_artifacts() -> None:
    resolved = MavenTreeAdapter().parse_tree(
        Path("tests/fixtures/maven-tree-packaging.txt")
    )

    assert resolved.root_identifier == "com.example:packaging-app==1.0.0"
    assert resolved.graph.get_dependencies("com.example:packaging-app==1.0.0") == [
        "com.example:platform==1.0.0",
        "com.example:platform:pom==1.0.0",
    ]
    metadata = resolved.graph.get_vertex_metadata("com.example:platform:pom==1.0.0")
    assert metadata["purl"] == "pkg:maven/com.example/platform@1.0.0"
    assert metadata["group"] == "com.example"
    assert metadata["artifact"] == "platform"
    assert metadata["packaging"] == "pom"
    assert metadata["coordinate"] == "com.example:platform:pom:1.0.0:import"
    assert metadata["scope"] == "import"


def test_maven_tree_adapter_preserves_optional_and_omitted_markers() -> None:
    resolved = MavenTreeAdapter().parse_tree(Path("tests/fixtures/maven-tree-markers.txt"))

    assert resolved.root_identifier == "com.example:marker-app==1.0.0"
    assert resolved.graph.get_dependencies("com.example:marker-app==1.0.0") == [
        "org.example:optional-lib==1.2.3",
        "org.example:conflict-lib==1.0.0",
        "org.example:runtime-lib==2.0.0",
    ]
    optional = resolved.graph.get_vertex_metadata("org.example:optional-lib==1.2.3")
    assert optional["purl"] == "pkg:maven/org.example/optional-lib@1.2.3"
    assert optional["coordinate"] == "org.example:optional-lib:jar:1.2.3:compile"
    assert optional["scope"] == "compile"
    assert optional["optional"] == "true"
    conflict = resolved.graph.get_vertex_metadata("org.example:conflict-lib==1.0.0")
    assert conflict["purl"] == "pkg:maven/org.example/conflict-lib@1.0.0"
    assert conflict["coordinate"] == "org.example:conflict-lib:jar:1.0.0:compile"
    assert conflict["scope"] == "compile"
    assert conflict["omitted"] == "true"
    assert conflict["omittedReason"] == "conflict with 2.0.0"
    edge_types = {
        edge.target: edge.relationship_type
        for edge in resolved.graph.edges()
        if edge.source == "com.example:marker-app==1.0.0"
    }
    assert edge_types["org.example:optional-lib==1.2.3"] == MAVEN_RELATIONSHIP_OPTIONAL
    assert edge_types["org.example:conflict-lib==1.0.0"] == MAVEN_RELATIONSHIP_OMITTED
