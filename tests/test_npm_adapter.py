"""npm adapter tests for building CSR graphs from package-lock fixtures."""

from pathlib import Path

from src.adapters.npm import NpmAdapter


def test_npm_package_lock_v3_builds_csr_graph() -> None:
    resolved = NpmAdapter().parse_lockfile_graph(Path("tests/fixtures/package-lock.json"))

    assert resolved.root_identifier == "demo-app==1.0.0"
    assert resolved.graph.get_dependencies("demo-app==1.0.0") == [
        "@scope/tool==2.1.0",
        "left-pad==1.3.0",
    ]
    assert resolved.graph.get_dependencies("@scope/tool==2.1.0") == [
        "nested==1.0.1",
        "left-pad==1.3.0",
    ]
    assert resolved.graph.get_dependencies("left-pad==1.3.0") == []
