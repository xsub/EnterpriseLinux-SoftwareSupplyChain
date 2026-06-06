"""Failure example index tests for workbench and RAG ingestion metadata."""

import json
from pathlib import Path

from scripts.generate_failure_example_index import build_failure_example_index
from src.cli import main


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


def test_cli_failure_examples_emits_generated_index(capsys) -> None:
    assert main(["failure-examples"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == build_failure_example_index()


def test_cli_failure_examples_emits_text_summary(capsys) -> None:
    assert main(["failure-examples", "--format", "text"]) == 0

    text = capsys.readouterr().out
    assert text.startswith(
        "OK examples=26 schema=edgp.validation.failure.example.index.v1"
    )
    assert (
        "manifest-invalid targetType=report-bundle "
        "contract=edgp.report.bundle.v1 failureCodes=bundle.manifestInvalid"
    ) in text
