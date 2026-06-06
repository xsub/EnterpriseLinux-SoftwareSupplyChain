"""Schema index tests for documented EDGP JSON Schema contracts."""

import json
from pathlib import Path

from scripts.generate_schema_index import build_schema_index


INDEX_PATH = Path("docs/schemas/index.json")


def test_schema_index_matches_generated_schema_contracts() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    assert index == build_schema_index()
    assert index["schema"] == "edgp.schema.index.v1"
    assert index["schemaCount"] == len(index["schemas"])
    assert {
        entry["contract"]
        for entry in index["schemas"]
        if "contract" in entry
    } == {
        "edgp.advisory.report.v1",
        "edgp.graph.snapshot.v1",
        "edgp.impact.report.v1",
        "edgp.npm.diagnostics.v1",
        "edgp.report.bundle.v1",
        "edgp.report.bundle.verification.v1",
        "edgp.validation.failure.example.filters.v1",
        "edgp.validation.failure.example.index.v1",
    }
