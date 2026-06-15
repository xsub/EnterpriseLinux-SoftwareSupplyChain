"""Failure example index tests for workbench and RAG ingestion metadata."""

import json
from pathlib import Path

from scripts.generate_failure_example_index import (
    build_failure_example_filter_listing,
    build_failure_example_index,
)
from src.cli import build_parser, main
from src.schema_validation import validate_target


INDEX_PATH = Path("docs/validation-failure-example-index.json")
FILTERS_PATH = Path("docs/validation-failure-example-filters.json")


def test_cli_failure_examples_help_mentions_contract_filters(capsys) -> None:
    try:
        build_parser().parse_args(["failure-examples", "--help"])
    except SystemExit as error:
        assert error.code == 0

    help_text = capsys.readouterr().out
    assert "--contract CONTRACT" in help_text
    assert "--list-codes" in help_text
    assert "contracts, target types" in help_text


def test_failure_example_index_matches_committed_fixtures() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    assert index == build_failure_example_index()
    assert index["schema"] == "edgp.validation.failure.example.index.v1"
    assert index["exampleCount"] == len(index["examples"])
    assert {entry["targetType"] for entry in index["examples"]} == {
        "json-file",
        "report-bundle",
        "report-bundle-archive",
    }
    validation_codes = {
        code
        for entry in index["examples"]
        for code in entry["validationFailureCodes"]
    }
    assert "requiredMissing" in validation_codes
    assert "bundle.manifestInvalid" in validation_codes
    assert "bundle.sourceDigestMismatch" in validation_codes
    assert "bundleArchive.archiveMissing" in validation_codes


def test_failure_example_index_matches_documented_schema() -> None:
    report = validate_target(INDEX_PATH)

    assert report["ok"] is True
    assert report["contract"] == "edgp.validation.failure.example.index.v1"


def test_failure_example_filter_listing_matches_committed_fixture() -> None:
    listing = json.loads(FILTERS_PATH.read_text(encoding="utf-8"))

    assert listing == build_failure_example_filter_listing()
    assert listing["schema"] == "edgp.validation.failure.example.filters.v1"
    assert listing["sourceSchema"] == "edgp.validation.failure.example.index.v1"
    assert listing["exampleCount"] == 27
    assert "edgp.graph.snapshot.v1" in listing["contracts"]
    assert "edgp.report.bundle.v1" in listing["contracts"]
    assert "edgp.report.bundle.archive.v1" in listing["contracts"]
    assert "manifest-invalid" in listing["ids"]


def test_failure_example_filter_listing_matches_documented_schema() -> None:
    report = validate_target(FILTERS_PATH)

    assert report["ok"] is True
    assert report["contract"] == "edgp.validation.failure.example.filters.v1"


def test_cli_failure_examples_emits_generated_index(capsys) -> None:
    assert main(["failure-examples"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == build_failure_example_index()


def test_cli_failure_examples_emits_text_summary(capsys) -> None:
    assert main(["failure-examples", "--format", "text"]) == 0

    text = capsys.readouterr().out
    assert text.startswith(
        "OK examples=27 schema=edgp.validation.failure.example.index.v1"
    )
    assert (
        "manifest-invalid targetType=report-bundle "
        "contract=edgp.report.bundle.v1 failureCodes=bundle.manifestInvalid"
    ) in text
    assert "verifierCodes=manifestInvalid" in text
    assert (
        "archive-missing targetType=report-bundle-archive "
        "contract=edgp.report.bundle.archive.v1 "
        "failureCodes=bundleArchive.archiveMissing"
    ) in text
    assert "verifierCodes=archiveMissing" in text


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
    assert "verifierCodes=manifestInvalid" in text


def test_cli_failure_examples_filters_by_target_type(capsys) -> None:
    assert main(["failure-examples", "--target-type", "json-file"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["exampleCount"] == 1
    assert payload["examples"][0]["id"] == "graph-missing-edge-count"

    assert main(["failure-examples", "--target-type", "report-bundle-archive"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["exampleCount"] == 1
    assert payload["examples"][0]["id"] == "archive-missing"


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


def test_cli_failure_examples_combines_contract_target_and_code(capsys) -> None:
    assert (
        main(
            [
                "failure-examples",
                "--target-type",
                "report-bundle",
                "--contract",
                "edgp.report.bundle.v1",
                "--code",
                "manifestInvalid",
                "--format",
                "text",
            ]
        )
        == 0
    )

    text = capsys.readouterr().out
    assert text.startswith(
        "OK examples=1 schema=edgp.validation.failure.example.index.v1"
    )
    assert "manifest-invalid targetType=report-bundle" in text
    assert "verifierCodes=manifestInvalid" in text


def test_cli_failure_examples_lists_combined_filter_values(capsys) -> None:
    assert (
        main(
            [
                "failure-examples",
                "--target-type",
                "report-bundle",
                "--contract",
                "edgp.report.bundle.v1",
                "--list-codes",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["exampleCount"] == 25
    assert payload["contracts"] == ["edgp.report.bundle.v1"]
    assert payload["targetTypes"] == ["report-bundle"]


def test_cli_failure_examples_lists_available_filter_values(capsys) -> None:
    assert main(["failure-examples", "--list-codes"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == build_failure_example_filter_listing()
    assert payload["schema"] == "edgp.validation.failure.example.filters.v1"
    assert payload["sourceSchema"] == "edgp.validation.failure.example.index.v1"
    assert payload["exampleCount"] == 27
    assert "manifest-invalid" in payload["ids"]
    assert "archive-missing" in payload["ids"]
    assert "json-file" in payload["targetTypes"]
    assert "report-bundle" in payload["targetTypes"]
    assert "report-bundle-archive" in payload["targetTypes"]
    assert "edgp.report.bundle.v1" in payload["contracts"]
    assert "edgp.report.bundle.archive.v1" in payload["contracts"]
    assert "bundle.manifestInvalid" in payload["validationFailureCodes"]
    assert "bundleArchive.archiveMissing" in payload["validationFailureCodes"]
    assert "requiredMissing" in payload["validationFailureCodes"]
    assert "manifestInvalid" in payload["verificationFailureCodes"]
    assert "archiveMissing" in payload["verificationFailureCodes"]


def test_cli_failure_example_filter_listing_matches_documented_schema(
    capsys, tmp_path: Path
) -> None:
    assert main(["failure-examples", "--list-codes"]) == 0

    output_path = tmp_path / "failure-example-filters.json"
    output_path.write_text(capsys.readouterr().out, encoding="utf-8")
    report = validate_target(output_path)

    assert report["ok"] is True
    assert report["contract"] == "edgp.validation.failure.example.filters.v1"


def test_cli_failure_examples_filters_by_contract(capsys) -> None:
    assert main(["failure-examples", "--contract", "edgp.graph.snapshot.v1"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["exampleCount"] == 1
    assert payload["examples"][0]["id"] == "graph-missing-edge-count"


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
    assert "contracts=edgp.graph.snapshot.v1" in text
    assert "targetTypes=json-file" in text
    assert "validationFailureCodes=requiredMissing" in text
