"""CLI tests for Maven dependency tree ingestion."""

import json
from pathlib import Path

from src.cli import main


def test_cli_maven_tree_exports_json(capsys) -> None:
    assert (
        main(
            [
                "maven-tree",
                "--path",
                "tests/fixtures/maven-tree.txt",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["ecosystem"] == "maven"
    assert payload["root"] == "com.example:demo-app==1.0.0"
    assert payload["stats"] == {"edges": 5, "nodes": 6}


def test_cli_query_maven_tree_path(capsys) -> None:
    assert (
        main(
            [
                "query",
                "--source",
                "maven-tree",
                "--path",
                "tests/fixtures/maven-tree.txt",
                "--operation",
                "path",
                "--node",
                "com.example:demo-app",
                "--target",
                "org.hamcrest:hamcrest-core",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["node"] == "com.example:demo-app==1.0.0"
    assert payload["target"] == "org.hamcrest:hamcrest-core==1.3"
    assert payload["result"] == [
        "com.example:demo-app==1.0.0",
        "junit:junit==4.13.2",
        "org.hamcrest:hamcrest-core==1.3",
    ]


def test_cli_maven_tree_disambiguates_classifier_artifacts(capsys) -> None:
    assert (
        main(
            [
                "maven-tree",
                "--path",
                "tests/fixtures/maven-tree-classifier.txt",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    node_ids = {node["id"] for node in payload["nodes"]}
    assert payload["stats"] == {"edges": 3, "nodes": 4}
    assert "com.example:native-lib==1.0.0" in node_ids
    assert "com.example:native-lib:linux-x86_64==1.0.0" in node_ids
    classifier_node = next(
        node
        for node in payload["nodes"]
        if node["id"] == "com.example:native-lib:linux-x86_64==1.0.0"
    )
    assert classifier_node["metadata"]["classifier"] == "linux-x86_64"


def test_cli_maven_tree_disambiguates_non_jar_artifacts(capsys) -> None:
    assert (
        main(
            [
                "maven-tree",
                "--path",
                "tests/fixtures/maven-tree-packaging.txt",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    node_ids = {node["id"] for node in payload["nodes"]}
    assert payload["stats"] == {"edges": 2, "nodes": 3}
    assert "com.example:platform==1.0.0" in node_ids
    assert "com.example:platform:pom==1.0.0" in node_ids


def test_cli_maven_tree_preserves_optional_and_omitted_markers(capsys) -> None:
    assert (
        main(
            [
                "maven-tree",
                "--path",
                "tests/fixtures/maven-tree-markers.txt",
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    nodes = {node["id"]: node for node in payload["nodes"]}
    edge_types = {edge["target"]: edge["relationshipType"] for edge in payload["edges"]}
    assert payload["stats"] == {"edges": 3, "nodes": 4}
    assert nodes["org.example:optional-lib==1.2.3"]["metadata"]["optional"] == "true"
    assert nodes["org.example:conflict-lib==1.0.0"]["metadata"]["omitted"] == "true"
    assert (
        nodes["org.example:conflict-lib==1.0.0"]["metadata"]["omittedReason"]
        == "conflict with 2.0.0"
    )
    assert edge_types["org.example:optional-lib==1.2.3"] == 2
    assert edge_types["org.example:conflict-lib==1.0.0"] == 3


def test_cli_ingest_maven_tree_outputs_normalized_graph(capsys) -> None:
    assert main(["ingest", "maven-tree", "tests/fixtures/maven-tree.txt"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ecosystem"] == "maven"
    assert payload["root"] == "com.example:demo-app==1.0.0"
    assert any(
        node.get("purl") == "pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.17.0"
        for node in payload["nodes"]
    )
    junit_edge = next(
        edge
        for edge in payload["edges"]
        if edge["source"] == "com.example:demo-app==1.0.0"
        and edge["target"] == "junit:junit==4.13.2"
    )
    assert junit_edge["scope"] == "test"


def test_cli_export_cyclonedx_from_maven_tree(capsys) -> None:
    assert (
        main(
            [
                "export",
                "cyclonedx",
                "--source",
                "maven-tree",
                "--path",
                "tests/fixtures/maven-tree.txt",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["bomFormat"] == "CycloneDX"
    assert any(
        component.get("purl") == (
            "pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.17.0"
        )
        for component in payload["components"]
    )


def test_cli_maven_bundle_writes_graph_and_impact_reports(tmp_path, capsys) -> None:
    output_dir = tmp_path / "maven-bundle"

    assert (
        main(
            [
                "maven-bundle",
                "--path",
                "tests/fixtures/maven-tree-classifier.txt",
                "--impact-node",
                "com.example:native-lib:linux-x86_64",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    graph = json.loads((output_dir / "maven-graph.json").read_text(encoding="utf-8"))
    impact = json.loads(
        (
            output_dir
            / "impact-com.example-native-lib-linux-x86_64-1.0.0.json"
        ).read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert graph["schema"] == "edgp.graph.snapshot.v1"
    assert "com.example:native-lib:linux-x86_64==1.0.0" == impact["node"]
    assert manifest["bundle"]["sourceKind"] == "maven-dependency-tree"
    assert manifest["bundle"]["command"].startswith("edgp maven-bundle ")
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.impact.report.v1",
    ]
    graph_html = (output_dir / "001-maven-graph.html").read_text(encoding="utf-8")
    assert "com.example:native-lib:linux-x86_64==1.0.0" in graph_html
    assert (
        output_dir / "002-impact-com.example-native-lib-linux-x86_64-1.0.0.html"
    ).exists()
