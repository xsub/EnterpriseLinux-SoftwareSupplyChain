"""ALBS build metadata adapter tests for real build provenance shapes."""

from pathlib import Path

from src.adapters.albs import AlbsBuildAdapter


def test_albs_build_adapter_builds_provenance_graph() -> None:
    resolved = AlbsBuildAdapter().parse_file(Path("tests/fixtures/albs-build.json"))

    assert resolved.ecosystem == "albs"
    assert resolved.root_identifier == "albs-build:17812"
    assert resolved.graph.get_dependencies("albs-build:17812") == [
        "source:nginx",
        "albs-release:7396",
        "albs-task:188080:ppc64le",
        "albs-task:188081:x86_64",
        "albs-sign-task:11754",
        "albs-test-task:985692",
    ]
    assert resolved.graph.get_dependencies("albs-task:188080:ppc64le") == [
        "git-commit:911945c71710c83cf6f760447c32d8d6cae737dc",
        "buildenv:AlmaLinux-9:ppc64le",
        "srpm:3237038:nginx-1.20.1-16.el9_4.1.src.rpm",
        "rpm:3237086:nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm",
    ]
    assert resolved.graph.get_dependents(
        "rpm:3237086:nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm"
    ) == ["albs-task:188080:ppc64le"]

    metadata = resolved.graph.get_vertex_metadata("albs-build:17812")
    assert metadata["package"] == "nginx"
    assert metadata["released"] == "True"
    assert metadata["owner"] == "eabdullin1"

    artifact_metadata = resolved.graph.get_vertex_metadata(
        "rpm:3237086:nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm"
    )
    assert artifact_metadata["artifact_name"] == (
        "nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm"
    )
    assert artifact_metadata["node_type"] == "binary_rpm"
    assert "build-log:3237071:mock.srpm.188080.1725369834.cfg" not in (
        resolved.graph.vertex_map
    )


def test_albs_build_adapter_can_include_build_logs() -> None:
    resolved = AlbsBuildAdapter().parse_file(
        Path("tests/fixtures/albs-build.json"),
        include_logs=True,
    )

    log_id = "build-log:3237071:mock.srpm.188080.1725369834.cfg"
    assert log_id in resolved.graph.vertex_map
    assert log_id in resolved.graph.get_dependencies("albs-task:188080:ppc64le")
    assert resolved.graph.get_vertex_metadata(log_id)["node_type"] == "build_log"
