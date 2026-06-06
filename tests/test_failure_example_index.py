"""Failure example index tests for workbench and RAG ingestion metadata."""

import json
from pathlib import Path

from scripts.generate_failure_example_index import build_failure_example_index
from src.cli import main
from src.schema_validation import validate_target


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


def test_failure_example_index_matches_documented_schema() -> None:
    report = validate_target(INDEX_PATH)

    assert report["ok"] is True
    assert report["contract"] == "edgp.validation.failure.example.index.v1"


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


def test_cli_failure_examples_filters_by_validation_code(capsys) -> None:
    assert main(["failure-examples", "--code", "bundle.manifestInvalid"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["exampleCount"] == 1
    assert payload["examples"][0]["id"] == "manifest-invalid"


def test_cli_failure_examples_filters_by_id(capsys) -> None:
    assert main(["failure-examples", "--id", "manifest-invalid"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["exampleCount"] == 1
    assert payload["examples"][0]["id"] == "manifest-invalid"


def test_cli_failure_examples_filters_by_verification_code(capsys) -> None:
    assert (
        main(["failure-examples", "--code", "manifestInvalid", "--format", "text"])
        == 0
    )

    text = capsys.readouterr().out
    assert text.startswith(
        "OK examples=1 schema=edgp.validation.failure.example.index.v1"
    )
    assert "manifest-invalid targetType=report-bundle" in text


def test_cli_failure_examples_filters_by_target_type(capsys) -> None:
    assert main(["failure-examples", "--target-type", "json-file"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["exampleCount"] == 1
    assert payload["examples"][0]["id"] == "graph-missing-edge-count"


def test_cli_failure_examples_combines_filters(capsys) -> None:
    assert (
        main(
            [
                "failure-examples",
                "--id",
                "manifest-invalid",
                "--target-type",
                "report-bundle",
                "--code",
                "manifestInvalid",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["exampleCount"] == 1
    assert payload["examples"][0]["id"] == "manifest-invalid"


def test_cli_failure_examples_lists_available_filter_values(capsys) -> None:
    assert main(["failure-examples", "--list-codes"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.validation.failure.example.filters.v1"
    assert payload["sourceSchema"] == "edgp.validation.failure.example.index.v1"
    assert payload["exampleCount"] == 26
    assert "manifest-invalid" in payload["ids"]
    assert "json-file" in payload["targetTypes"]
    assert "report-bundle" in payload["targetTypes"]
    assert "bundle.manifestInvalid" in payload["validationFailureCodes"]
    assert "requiredMissing" in payload["validationFailureCodes"]
    assert "manifestInvalid" in payload["verificationFailureCodes"]


def test_cli_failure_examples_lists_filtered_filter_values_as_text(capsys) -> None:
    assert (
        main(
            [
                "failure-examples",
                "--target-type",
                "json-file",
                "--list-codes",
                "--format",
                "text",
            ]
        )
        == 0
    )

    text = capsys.readouterr().out
    assert text.startswith(
        "OK examples=1 schema=edgp.validation.failure.example.filters.v1"
    )
    assert "ids=graph-missing-edge-count" in text
    assert "targetTypes=json-file" in text
    assert "validationFailureCodes=requiredMissing" in text
