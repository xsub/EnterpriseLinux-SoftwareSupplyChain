"""Cargo.lock adapter tests for Rust dependency graph ingestion."""

from pathlib import Path

from src.adapters.cargo import CargoAdapter


def test_cargo_lockfile_builds_resolved_graph() -> None:
    resolved = CargoAdapter().parse_lockfile_graph(Path("tests/fixtures/Cargo.lock"))

    assert resolved.root_identifier == "cargo-lock==resolved"
    assert resolved.ecosystem == "cargo"
    assert resolved.graph.get_dependencies("cargo-lock==resolved") == [
        "demo-crate==0.1.0"
    ]
    assert resolved.graph.get_dependencies("demo-crate==0.1.0") == [
        "serde==1.0.197",
        "tokio==1.36.0",
    ]
    assert resolved.graph.get_dependencies("tokio==1.36.0") == [
        "pin-project-lite==0.2.13"
    ]
    metadata = resolved.graph.get_vertex_metadata("serde==1.0.197")
    assert metadata["ecosystem"] == "cargo"
    assert metadata["source"] == "Cargo.lock"
    assert metadata["package_manager"] == "cargo"
    assert metadata["purl"] == "pkg:cargo/serde@1.0.197"
    assert metadata["checksum"] == "fixture-serde"
    assert metadata["cargo_checksum"] == "fixture-serde"
    assert metadata["cargo_source"] == "registry+https://github.com/rust-lang/crates.io-index"
    assert metadata["source_url"] == "https://github.com/rust-lang/crates.io-index"
    assert metadata["classification"] == "transitive"
    assert resolved.graph.get_edge_metadata("demo-crate==0.1.0", "tokio==1.36.0")[
        "constraint"
    ] == "1.36.0"
    assert resolved.graph.get_edge_metadata("cargo-lock==resolved", "demo-crate==0.1.0")[
        "direct"
    ] == "True"
