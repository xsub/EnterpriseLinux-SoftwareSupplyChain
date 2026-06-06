"""Failure example index tests for workbench and RAG ingestion metadata."""

import json
from pathlib import Path

from scripts.generate_failure_example_index import build_failure_example_index


INDEX_PATH = Path("docs/validation-failure-example-index.json")


def test_failure_example_index_matches_committed_fixtures() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    assert index == build_failure_example_index()
    assert index["schema"] == "edgp.validation.failure.example.index.v1"
    assert index["exampleCount"] == len(index["examples"])
    assert {entry["targetType"] for entry in index["examples"]} == {
        "json-file",
        "report-bundle",
    }
    validation_codes = {
        code
        for entry in index["examples"]
        for code in entry["validationFailureCodes"]
    }
    assert "requiredMissing" in validation_codes
    assert "bundle.manifestInvalid" in validation_codes
    assert "bundle.sourceDigestMismatch" in validation_codes
