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
    assert resolved.graph.get_vertex_metadata("serde==1.0.197") == {
        "ecosystem": "cargo",
        "source": "Cargo.lock",
        "cargo_checksum": "fixture-serde",
        "cargo_source": "registry+https://github.com/rust-lang/crates.io-index",
    }
