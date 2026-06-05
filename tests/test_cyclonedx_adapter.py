"""CycloneDX adapter tests for rebuilding CSR graphs from SBOMs."""

from pathlib import Path

from src.adapters.cyclonedx import CycloneDXAdapter


def test_cyclonedx_adapter_rebuilds_dependency_graph() -> None:
    resolved = CycloneDXAdapter().parse_graph(Path("tests/fixtures/sample-bom.json"))

    assert resolved.root_identifier == "demo-app==1.0.0"
    assert resolved.ecosystem == "npm"
    assert resolved.graph.get_dependencies("demo-app==1.0.0") == ["left-pad==1.3.0"]
    assert resolved.graph.get_vertex_metadata("left-pad==1.3.0") == {
        "purl": "pkg:npm/left-pad@1.3.0",
        "ecosystem": "npm",
        "component_type": "library",
        "license": "WTFPL",
    }
