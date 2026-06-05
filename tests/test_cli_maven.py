"""CLI tests for Maven dependency tree ingestion."""

import json

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
