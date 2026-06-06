"""Generate a deterministic index for committed EDGP validation failures."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = REPO_ROOT / "docs" / "validation-failure-example-index.json"
INDEX_SCHEMA = "edgp.validation.failure.example.index.v1"


@dataclass(frozen=True)
class FailureExample:
    id: str
    target: str
    validation_fixture: str
    verification_fixture: str = ""


EXAMPLES = [
    FailureExample(
        "graph-missing-edge-count",
        "tests/fixtures/invalid-snapshot-missing-edge-count.json",
        "tests/fixtures/validation-failure-missing-edge-count.json",
    ),
    FailureExample(
        "bundle-digest-mismatch",
        "tests/fixtures/tampered-report-bundle-manifest",
        "tests/fixtures/validation-failure-tampered-bundle-manifest.json",
        "tests/fixtures/report-bundle-verification-tampered-manifest.json",
    ),
    FailureExample(
        "html-digest-mismatch",
        "tests/fixtures/tampered-report-bundle-member",
        "tests/fixtures/validation-failure-tampered-bundle-member.json",
        "tests/fixtures/report-bundle-verification-tampered-member.json",
    ),
    FailureExample(
        "html-missing",
        "tests/fixtures/missing-html-report-bundle",
        "tests/fixtures/validation-failure-missing-bundle-html.json",
        "tests/fixtures/report-bundle-verification-missing-html.json",
    ),
    FailureExample(
        "source-missing",
        "tests/fixtures/missing-source-report-bundle",
        "tests/fixtures/validation-failure-missing-bundle-source.json",
        "tests/fixtures/report-bundle-verification-missing-source.json",
    ),
    FailureExample(
        "manifest-missing-field",
        "tests/fixtures/invalid-manifest-missing-report-count-bundle",
        "tests/fixtures/validation-failure-invalid-manifest-missing-report-count.json",
        "tests/fixtures/report-bundle-verification-invalid-manifest-missing-report-count.json",
    ),
    FailureExample(
        "report-missing-field",
        "tests/fixtures/invalid-report-missing-title-bundle",
        "tests/fixtures/validation-failure-invalid-report-missing-title.json",
        "tests/fixtures/report-bundle-verification-invalid-report-missing-title.json",
    ),
    FailureExample(
        "manifest-unknown-field",
        "tests/fixtures/invalid-manifest-unknown-field-bundle",
        "tests/fixtures/validation-failure-invalid-manifest-unknown-field.json",
        "tests/fixtures/report-bundle-verification-invalid-manifest-unknown-field.json",
    ),
    FailureExample(
        "report-unknown-field",
        "tests/fixtures/invalid-report-unknown-field-bundle",
        "tests/fixtures/validation-failure-invalid-report-unknown-field.json",
        "tests/fixtures/report-bundle-verification-invalid-report-unknown-field.json",
    ),
    FailureExample(
        "bundle-source-kind-invalid",
        "tests/fixtures/invalid-bundle-source-kind-bundle",
        "tests/fixtures/validation-failure-invalid-bundle-source-kind.json",
        "tests/fixtures/report-bundle-verification-invalid-bundle-source-kind.json",
    ),
    FailureExample(
        "report-digest-invalid",
        "tests/fixtures/invalid-report-digest-bundle",
        "tests/fixtures/validation-failure-invalid-report-digest.json",
        "tests/fixtures/report-bundle-verification-invalid-report-digest.json",
    ),
    FailureExample(
        "bundle-invalid",
        "tests/fixtures/invalid-bundle-metadata-bundle",
        "tests/fixtures/validation-failure-invalid-bundle-metadata.json",
        "tests/fixtures/report-bundle-verification-invalid-bundle-metadata.json",
    ),
    FailureExample(
        "index-invalid",
        "tests/fixtures/invalid-index-path-bundle",
        "tests/fixtures/validation-failure-invalid-index-path.json",
        "tests/fixtures/report-bundle-verification-invalid-index-path.json",
    ),
    FailureExample(
        "manifest-schema-mismatch",
        "tests/fixtures/invalid-manifest-schema-bundle",
        "tests/fixtures/validation-failure-invalid-manifest-schema.json",
        "tests/fixtures/report-bundle-verification-invalid-manifest-schema.json",
    ),
    FailureExample(
        "bundle-digest-invalid",
        "tests/fixtures/invalid-bundle-digest-bundle",
        "tests/fixtures/validation-failure-invalid-bundle-digest.json",
        "tests/fixtures/report-bundle-verification-invalid-bundle-digest.json",
    ),
    FailureExample(
        "reports-invalid",
        "tests/fixtures/invalid-reports-list-bundle",
        "tests/fixtures/validation-failure-invalid-reports-list.json",
        "tests/fixtures/report-bundle-verification-invalid-reports-list.json",
    ),
    FailureExample(
        "report-invalid",
        "tests/fixtures/invalid-report-entry-bundle",
        "tests/fixtures/validation-failure-invalid-report-entry.json",
        "tests/fixtures/report-bundle-verification-invalid-report-entry.json",
    ),
    FailureExample(
        "report-field-invalid",
        "tests/fixtures/invalid-report-field-bundle",
        "tests/fixtures/validation-failure-invalid-report-field.json",
        "tests/fixtures/report-bundle-verification-invalid-report-field.json",
    ),
    FailureExample(
        "report-summary-invalid",
        "tests/fixtures/invalid-report-summary-bundle",
        "tests/fixtures/validation-failure-invalid-report-summary.json",
        "tests/fixtures/report-bundle-verification-invalid-report-summary.json",
    ),
    FailureExample(
        "report-count-mismatch",
        "tests/fixtures/invalid-report-count-bundle",
        "tests/fixtures/validation-failure-invalid-report-count.json",
        "tests/fixtures/report-bundle-verification-invalid-report-count.json",
    ),
    FailureExample(
        "report-href-invalid",
        "tests/fixtures/invalid-report-href-bundle",
        "tests/fixtures/validation-failure-invalid-report-href.json",
        "tests/fixtures/report-bundle-verification-invalid-report-href.json",
    ),
    FailureExample(
        "index-missing",
        "tests/fixtures/missing-index-report-bundle",
        "tests/fixtures/validation-failure-missing-index.json",
        "tests/fixtures/report-bundle-verification-missing-index.json",
    ),
    FailureExample(
        "source-digest-mismatch",
        "tests/fixtures/source-digest-mismatch-bundle",
        "tests/fixtures/validation-failure-source-digest-mismatch.json",
        "tests/fixtures/report-bundle-verification-source-digest-mismatch.json",
    ),
    FailureExample(
        "manifest-missing",
        "tests/fixtures/missing-manifest-report-bundle",
        "tests/fixtures/validation-failure-missing-manifest.json",
        "tests/fixtures/report-bundle-verification-missing-manifest.json",
    ),
    FailureExample(
        "manifest-invalid-json",
        "tests/fixtures/invalid-json-manifest-bundle",
        "tests/fixtures/validation-failure-invalid-json-manifest.json",
        "tests/fixtures/report-bundle-verification-invalid-json-manifest.json",
    ),
    FailureExample(
        "manifest-invalid",
        "tests/fixtures/invalid-manifest-type-bundle",
        "tests/fixtures/validation-failure-invalid-manifest-type.json",
        "tests/fixtures/report-bundle-verification-invalid-manifest-type.json",
    ),
]


def build_failure_example_index() -> dict[str, Any]:
    examples = [_example_entry(example) for example in EXAMPLES]
    return {
        "schema": INDEX_SCHEMA,
        "generatedBy": "scripts/generate_failure_example_index.py",
        "exampleCount": len(examples),
        "examples": examples,
    }


def _example_entry(example: FailureExample) -> dict[str, Any]:
    validation = _load_fixture(example.validation_fixture)
    failures = _failure_records(validation)
    entry: dict[str, Any] = {
        "id": example.id,
        "target": example.target,
        "targetType": str(validation.get("targetType", "")),
        "contract": str(validation.get("contract", "")),
        "validationFixture": example.validation_fixture,
        "validationFailureCodes": _failure_codes(failures),
        "firstFailure": _first_failure(failures),
        "commands": {
            "validateText": (
                f"python -B -m src.cli validate --path {example.target} --format text"
            ),
        },
    }

    bundle_verification = validation.get("bundleVerification")
    if isinstance(bundle_verification, dict):
        verifier_failures = _failure_records(bundle_verification)
        entry["verificationFixture"] = example.verification_fixture
        entry["verificationFailureCodes"] = _failure_codes(verifier_failures)
        entry["verificationSummary"] = bundle_verification.get("summary", {})
        entry["commands"]["verifyText"] = (
            f"python -B -m src.cli verify-bundle --path {example.target} --format text"
        )

    return entry


def _load_fixture(path: str) -> dict[str, Any]:
    payload = json.loads((REPO_ROOT / path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _failure_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    failures = payload.get("failures", [])
    if not isinstance(failures, list):
        return []
    return [failure for failure in failures if isinstance(failure, dict)]


def _failure_codes(failures: list[dict[str, Any]]) -> list[str]:
    return [
        str(failure.get("code", ""))
        for failure in failures
        if isinstance(failure.get("code"), str)
    ]


def _first_failure(failures: list[dict[str, Any]]) -> dict[str, str]:
    if not failures:
        return {"code": "", "message": "", "path": ""}
    first = failures[0]
    return {
        "code": str(first.get("code", "")),
        "message": str(first.get("message", "")),
        "path": str(first.get("path", "")),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=INDEX_PATH)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the existing index does not match generated content",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    expected = build_failure_example_index()
    if args.check:
        actual = json.loads(args.output.read_text(encoding="utf-8"))
        if actual != expected:
            print(f"{args.output} is out of date")
            return 1
        return 0

    args.output.write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
