"""DOT adapter tests for AlmaLinux/RPM universe graph ingestion."""

from pathlib import Path

from src.adapters.dot import DotAdapter


def test_dot_adapter_parses_repograph_block_edges() -> None:
    resolved = DotAdapter().parse_graph(Path("tests/fixtures/repograph.dot"))

    assert resolved.ecosystem == "rpm"
    assert resolved.root_identifier == "nginx-core==unknown"
    assert resolved.graph.get_dependencies("nginx-core==unknown") == [
        "openssl-libs==unknown",
        "glibc==unknown",
    ]
    assert resolved.graph.get_dependencies("openssl-libs==unknown") == [
        "glibc==unknown"
    ]
    assert resolved.graph.get_dependents("glibc==unknown") == [
        "nginx-core==unknown",
        "openssl-libs==unknown",
        "curl==unknown",
    ]
    assert resolved.graph.get_vertex_metadata("glibc==unknown") == {"ecosystem": "rpm"}
