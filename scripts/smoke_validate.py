"""Run dependency graph smoke checks without external test dependencies."""

from __future__ import annotations

import argparse
import compileall
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
REPORT_BUNDLE_SCHEMA_PATH = (
    REPO_ROOT / "docs" / "schemas" / "edgp.report.bundle.v1.schema.json"
)
REPORT_BUNDLE_VERIFICATION_SCHEMA_PATH = (
    REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.report.bundle.verification.v1.schema.json"
)
SCHEMA_INDEX_PATH = REPO_ROOT / "docs" / "schemas" / "index.json"
FAILURE_EXAMPLE_INDEX_PATH = REPO_ROOT / "docs" / "validation-failure-example-index.json"
FAILURE_EXAMPLE_FILTERS_PATH = (
    REPO_ROOT / "docs" / "validation-failure-example-filters.json"
)
VALIDATION_FAILURE_EXAMPLES_DOC_PATH = (
    REPO_ROOT / "docs" / "Validation Failure Examples.md"
)
REPORT_JSON_SCHEMA_CONTRACTS = {
    "edgp.graph.snapshot.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.graph.snapshot.v1.schema.json",
    "edgp.impact.report.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.impact.report.v1.schema.json",
    "edgp.advisory.report.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.advisory.report.v1.schema.json",
    "edgp.npm.diagnostics.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.npm.diagnostics.v1.schema.json",
}
REPORT_JSON_SCHEMA_FIXTURES = {
    "edgp.graph.snapshot.v1": REPO_ROOT / "tests" / "fixtures" / "snapshot-right.json",
    "edgp.impact.report.v1": REPO_ROOT / "tests" / "fixtures" / "impact-report.json",
    "edgp.advisory.report.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "advisory-report.json",
    "edgp.npm.diagnostics.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "npm-diagnostics-report.json",
}


def _run_cli(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "src.cli", *args],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _run_cli_allow_failure(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "src.cli", *args],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    return json.loads(completed.stdout)


def _normalize_validation_report(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    bundle_verification = normalized.get("bundleVerification")
    bundle_dir = ""
    if isinstance(bundle_verification, dict):
        bundle = dict(bundle_verification)
        bundle_dir = str(bundle.get("bundleDir", ""))
        bundle["bundleDir"] = "<bundle-dir>"
        if bundle.get("bundleSha256") is not None:
            bundle["bundleSha256"] = "<bundleSha256>"
        bundle["failures"] = _normalize_failure_paths(
            bundle.get("failures", []),
            bundle_dir,
        )
        normalized["bundleVerification"] = bundle
    normalized["target"] = "<target>"
    normalized["failures"] = _normalize_failure_paths(
        normalized.get("failures", []),
        bundle_dir,
    )
    return normalized


def _assert_compile() -> None:
    ok = compileall.compile_dir(REPO_ROOT / "src", quiet=1)
    ok = compileall.compile_dir(REPO_ROOT / "tests", quiet=1) and ok
    if not ok:
        raise AssertionError("compileall failed")


def _assert_lockfile_snapshot() -> None:
    payload = _run_cli(
        ["lockfile", "--path", "tests/fixtures/package-lock.json", "--format", "json"]
    )
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "npm"
    assert payload["stats"] == {"edges": 4, "nodes": 4}
    assert payload["rankings"]["mostDependedUpon"][0] == {
        "package": "left-pad==1.3.0",
        "dependents": 2,
    }


def _assert_npm_diagnostics() -> None:
    payload = _run_cli(
        [
            "npm-diagnostics",
            "--path",
            "tests/fixtures/package-lock-conflict.json",
        ]
    )
    assert payload["schema"] == "edgp.npm.diagnostics.v1"
    assert payload["summary"] == {
        "packages": 4,
        "duplicatePackageNames": 1,
        "nestedResolutionConflicts": 1,
        "unresolvedDependencies": 1,
    }


def _assert_validate_command() -> None:
    payload = _run_cli(["validate", "--path", "tests/fixtures/snapshot-right.json"])
    assert payload["schema"] == "edgp.validation.report.v1"
    assert payload["ok"] is True
    assert payload["targetType"] == "json-file"
    assert payload["contract"] == "edgp.graph.snapshot.v1"
    assert payload["summary"] == {"failures": 0}

    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "validate",
            "--path",
            "tests/fixtures/snapshot-right.json",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == (
        "OK targetType=json-file failures=0 contract=edgp.graph.snapshot.v1"
    )

    failure_payload = _run_cli_allow_failure(
        [
            "validate",
            "--path",
            "tests/fixtures/invalid-snapshot-missing-edge-count.json",
        ]
    )
    fixture = json.loads(
        (
            REPO_ROOT
            / "tests"
            / "fixtures"
            / "validation-failure-missing-edge-count.json"
        ).read_text(encoding="utf-8")
    )
    assert _normalize_validation_report(failure_payload) == fixture


def _load_report_bundle_manifest_schema() -> dict[str, Any]:
    return json.loads(REPORT_BUNDLE_SCHEMA_PATH.read_text(encoding="utf-8"))


def _load_report_bundle_verification_schema() -> dict[str, Any]:
    return json.loads(
        REPORT_BUNDLE_VERIFICATION_SCHEMA_PATH.read_text(encoding="utf-8")
    )


def _assert_report_bundle_manifest_schema_document() -> None:
    schema = _load_report_bundle_manifest_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema"]["const"] == "edgp.report.bundle.v1"
    assert set(schema["required"]) == {
        "schema",
        "bundleSha256",
        "index",
        "reportCount",
        "reports",
    }
    assert {
        "htmlSha256",
        "sourceSha256",
    } <= set(schema["properties"]["reports"]["items"]["required"])
    assert set(schema["properties"]["bundle"]["properties"]["sourceKind"]["enum"]) == {
        "cyclonedx-sbom",
        "dot",
        "edgp-json",
        "maven-dependency-tree",
        "npm-lockfile",
        "rpm-installed",
    }


def _assert_report_bundle_verification_schema_document() -> None:
    schema = _load_report_bundle_verification_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert (
        schema["properties"]["schema"]["const"]
        == "edgp.report.bundle.verification.v1"
    )
    assert set(schema["required"]) == {
        "schema",
        "bundleDir",
        "manifest",
        "ok",
        "bundleSha256",
        "summary",
        "failures",
    }
    assert set(schema["properties"]["summary"]["required"]) == {
        "reports",
        "failures",
    }
    assert set(schema["properties"]["failures"]["items"]["required"]) == {
        "code",
        "message",
        "path",
    }


def _assert_report_json_schemas_document() -> None:
    for contract, schema_path in REPORT_JSON_SCHEMA_CONTRACTS.items():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        payload = json.loads(
            REPORT_JSON_SCHEMA_FIXTURES[contract].read_text(encoding="utf-8")
        )
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["properties"]["schema"]["const"] == contract
        assert schema["title"]
        assert schema["description"]
        assert payload["schema"] == contract
        assert set(schema["required"]) <= set(payload)
        assert set(payload) <= set(schema["properties"])

    graph_schema = json.loads(
        REPORT_JSON_SCHEMA_CONTRACTS["edgp.graph.snapshot.v1"].read_text(
            encoding="utf-8"
        )
    )
    assert set(graph_schema["properties"]["nodes"]["items"]["required"]) == {
        "id",
        "name",
        "dependencies",
        "dependents",
        "metadata",
    }
    assert set(graph_schema["properties"]["edges"]["items"]["required"]) == {
        "source",
        "target",
        "relationshipType",
    }

    impact_schema = json.loads(
        REPORT_JSON_SCHEMA_CONTRACTS["edgp.impact.report.v1"].read_text(
            encoding="utf-8"
        )
    )
    advisory_schema = json.loads(
        REPORT_JSON_SCHEMA_CONTRACTS["edgp.advisory.report.v1"].read_text(
            encoding="utf-8"
        )
    )
    assert set(impact_schema["properties"]["summary"]["required"]) == set(
        advisory_schema["$defs"]["impactReport"]["properties"]["summary"]["required"]
    )


def _assert_schema_index_document() -> None:
    subprocess.run(
        [sys.executable, "-B", "scripts/generate_schema_index.py", "--check"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    index = json.loads(SCHEMA_INDEX_PATH.read_text(encoding="utf-8"))
    assert index["schema"] == "edgp.schema.index.v1"
    assert index["generatedBy"] == "scripts/generate_schema_index.py"
    assert index["schemaCount"] == len(index["schemas"])
    contracts = {
        schema["contract"]
        for schema in index["schemas"]
        if isinstance(schema, dict) and "contract" in schema
    }
    assert {
        "edgp.advisory.report.v1",
        "edgp.graph.snapshot.v1",
        "edgp.impact.report.v1",
        "edgp.npm.diagnostics.v1",
        "edgp.report.bundle.v1",
        "edgp.report.bundle.verification.v1",
        "edgp.validation.failure.example.filters.v1",
        "edgp.validation.failure.example.index.v1",
    } <= contracts
    for schema in index["schemas"]:
        assert schema["file"].endswith(".schema.json")
        assert schema["id"].startswith("urn:edgp:schema:")
        assert schema["jsonSchema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["title"]
        assert schema["description"]


def _assert_failure_example_index_document() -> None:
    subprocess.run(
        [sys.executable, "-B", "scripts/generate_failure_example_index.py", "--check"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    index = json.loads(FAILURE_EXAMPLE_INDEX_PATH.read_text(encoding="utf-8"))
    cli_index = _run_cli(["failure-examples"])
    assert cli_index == index
    filter_fixture = json.loads(FAILURE_EXAMPLE_FILTERS_PATH.read_text(encoding="utf-8"))
    filtered_index = _run_cli(["failure-examples", "--code", "manifestInvalid"])
    assert filtered_index["exampleCount"] == 1
    assert filtered_index["examples"][0]["id"] == "manifest-invalid"
    filtered_index = _run_cli(["failure-examples", "--id", "manifest-invalid"])
    assert filtered_index["exampleCount"] == 1
    assert filtered_index["examples"][0]["id"] == "manifest-invalid"
    filtered_index = _run_cli(["failure-examples", "--target-type", "json-file"])
    assert filtered_index["exampleCount"] == 1
    assert filtered_index["examples"][0]["id"] == "graph-missing-edge-count"
    filtered_index = _run_cli(
        ["failure-examples", "--contract", "edgp.graph.snapshot.v1"]
    )
    assert filtered_index["exampleCount"] == 1
    assert filtered_index["examples"][0]["id"] == "graph-missing-edge-count"
    filtered_index = _run_cli(
        [
            "failure-examples",
            "--target-type",
            "report-bundle",
            "--code",
            "manifestInvalid",
        ]
    )
    assert filtered_index["exampleCount"] == 1
    assert filtered_index["examples"][0]["id"] == "manifest-invalid"
    filtered_summary = _run_cli(
        [
            "failure-examples",
            "--target-type",
            "report-bundle",
            "--contract",
            "edgp.report.bundle.v1",
            "--list-codes",
        ]
    )
    assert filtered_summary["exampleCount"] == 25
    assert filtered_summary["contracts"] == ["edgp.report.bundle.v1"]
    assert filtered_summary["targetTypes"] == ["report-bundle"]
    filter_summary = _run_cli(["failure-examples", "--list-codes"])
    assert filter_summary == filter_fixture
    assert filter_summary["schema"] == "edgp.validation.failure.example.filters.v1"
    assert filter_summary["sourceSchema"] == "edgp.validation.failure.example.index.v1"
    assert filter_summary["exampleCount"] == 26
    assert "manifest-invalid" in filter_summary["ids"]
    assert "edgp.report.bundle.v1" in filter_summary["contracts"]
    assert "bundle.manifestInvalid" in filter_summary["validationFailureCodes"]
    assert "manifestInvalid" in filter_summary["verificationFailureCodes"]
    validation = _run_cli(
        ["validate", "--path", "docs/validation-failure-example-filters.json"]
    )
    assert validation["ok"] is True
    assert validation["contract"] == "edgp.validation.failure.example.filters.v1"
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "failure-examples",
            "--help",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert "--contract CONTRACT" in completed.stdout
    assert "--list-codes" in completed.stdout
    assert "contracts, target types" in completed.stdout
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "failure-examples",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.startswith(
        "OK examples=26 schema=edgp.validation.failure.example.index.v1"
    )
    assert "manifest-invalid targetType=report-bundle" in completed.stdout
    assert "verifierCodes=manifestInvalid" in completed.stdout
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "failure-examples",
            "--id",
            "manifest-invalid",
            "--code",
            "bundle.manifestInvalid",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.startswith(
        "OK examples=1 schema=edgp.validation.failure.example.index.v1"
    )
    assert "manifest-invalid targetType=report-bundle" in completed.stdout
    assert "verifierCodes=manifestInvalid" in completed.stdout
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "failure-examples",
            "--target-type",
            "report-bundle",
            "--contract",
            "edgp.report.bundle.v1",
            "--code",
            "manifestInvalid",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.startswith(
        "OK examples=1 schema=edgp.validation.failure.example.index.v1"
    )
    assert "manifest-invalid targetType=report-bundle" in completed.stdout
    assert "verifierCodes=manifestInvalid" in completed.stdout
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "failure-examples",
            "--target-type",
            "json-file",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.startswith(
        "OK examples=1 schema=edgp.validation.failure.example.index.v1"
    )
    assert "graph-missing-edge-count targetType=json-file" in completed.stdout
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "failure-examples",
            "--target-type",
            "json-file",
            "--list-codes",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.startswith(
        "OK examples=1 schema=edgp.validation.failure.example.filters.v1"
    )
    assert "ids=graph-missing-edge-count" in completed.stdout
    assert "contracts=edgp.graph.snapshot.v1" in completed.stdout
    assert "validationFailureCodes=requiredMissing" in completed.stdout
    assert index["schema"] == "edgp.validation.failure.example.index.v1"
    assert index["generatedBy"] == "scripts/generate_failure_example_index.py"
    assert index["exampleCount"] == len(index["examples"])
    assert index["exampleCount"] >= 25
    validation = _run_cli(["validate", "--path", "docs/validation-failure-example-index.json"])
    assert validation["ok"] is True
    assert validation["contract"] == "edgp.validation.failure.example.index.v1"
    validation_codes = {
        code
        for entry in index["examples"]
        for code in entry["validationFailureCodes"]
    }
    assert {"requiredMissing", "bundle.manifestInvalid"} <= validation_codes


def _assert_validation_failure_examples_quick_links() -> None:
    lines = VALIDATION_FAILURE_EXAMPLES_DOC_PATH.read_text(encoding="utf-8").splitlines()
    heading_anchors = _validation_failure_example_heading_anchors()
    linked_anchors = _markdown_link_anchors(lines)

    assert linked_anchors
    for anchor in linked_anchors:
        assert anchor in heading_anchors


def _assert_readme_validation_guide_anchors() -> None:
    heading_anchors = _validation_failure_example_heading_anchors()
    linked_anchors = _markdown_links_to_anchor(
        README_PATH.read_text(encoding="utf-8").splitlines(),
        "docs/Validation%20Failure%20Examples.md#",
    )

    assert {"cli-index-workflows", "quick-links"} <= set(linked_anchors)
    for anchor in linked_anchors:
        assert anchor in heading_anchors


def _assert_readme_validation_failure_fixture_links() -> None:
    readme_paths = set(
        _markdown_path_links(README_PATH.read_text(encoding="utf-8").splitlines())
    )
    linked_paths = {
        "docs/validation-failure-example-index.json",
        "docs/validation-failure-example-filters.json",
    }

    assert linked_paths <= readme_paths
    for path in linked_paths:
        assert (REPO_ROOT / path).exists()


def _validation_failure_example_heading_anchors() -> set[str]:
    lines = VALIDATION_FAILURE_EXAMPLES_DOC_PATH.read_text(encoding="utf-8").splitlines()
    return _markdown_heading_anchors(lines)


def _markdown_anchor(heading: str) -> str:
    anchor_chars = []
    previous_was_dash = False
    for character in heading.strip().lower():
        if character.isalnum():
            anchor_chars.append(character)
            previous_was_dash = False
        elif character in {" ", "-"} and not previous_was_dash:
            anchor_chars.append("-")
            previous_was_dash = True
    return "".join(anchor_chars).strip("-")


def _markdown_heading_anchors(lines: list[str], *, level: str = "## ") -> set[str]:
    return {
        _markdown_anchor(line.removeprefix(level))
        for line in lines
        if line.startswith(level)
    }


def _markdown_link_anchors(lines: list[str]) -> list[str]:
    return _markdown_links_to_anchor(lines, "#")


def _markdown_links_to_anchor(lines: list[str], marker: str) -> list[str]:
    anchors = []
    for target in _markdown_link_targets(lines):
        if marker in target:
            anchors.append(target.split(marker, 1)[1])
    return anchors


def _markdown_path_links(lines: list[str]) -> list[str]:
    paths = []
    for target in _markdown_link_targets(lines):
        if target.startswith("#") or "://" in target or target.startswith("mailto:"):
            continue
        paths.append(target.split("#", 1)[0])
    return paths


def _markdown_link_targets(lines: list[str]) -> list[str]:
    targets = []
    for line in lines:
        search_start = 0
        while True:
            link_start = line.find("](", search_start)
            if link_start == -1:
                break
            target_start = link_start + 2
            target_end = line.find(")", target_start)
            if target_end == -1:
                break
            label_start = line.rfind("[", 0, link_start)
            if label_start == 0 or line[label_start - 1] != "!":
                targets.append(line[target_start:target_end])
            search_start = target_end + 1
    return targets


def _assert_report_bundle_manifest_contract(
    manifest: dict[str, Any],
    bundle_dir: Path | None = None,
) -> None:
    schema = _load_report_bundle_manifest_schema()
    report_schema = schema["properties"]["reports"]["items"]
    required_report_keys = set(report_schema["required"])
    allowed_report_keys = set(report_schema["properties"])

    assert manifest["schema"] == schema["properties"]["schema"]["const"]
    assert isinstance(manifest["index"], str) and manifest["index"]
    assert _is_sha256(manifest["bundleSha256"])
    assert manifest["bundleSha256"] == _manifest_sha256(manifest)
    assert isinstance(manifest["reportCount"], int)
    assert isinstance(manifest["reports"], list) and manifest["reports"]
    assert manifest["reportCount"] == len(manifest["reports"])
    for report in manifest["reports"]:
        assert required_report_keys <= set(report)
        assert set(report) <= allowed_report_keys
        assert isinstance(report["href"], str) and report["href"]
        assert _is_sha256(report["htmlSha256"])
        assert isinstance(report["schema"], str) and report["schema"]
        assert isinstance(report["source"], str) and report["source"]
        assert _is_sha256(report["sourceSha256"])
        assert isinstance(report["summary"], dict)
        assert isinstance(report["title"], str) and report["title"]
        if bundle_dir is not None:
            html_path = bundle_dir / report["href"]
            source_path = _resolve_manifest_source(bundle_dir, report["source"])
            assert report["htmlSha256"] == _sha256_path(html_path)
            assert report["sourceSha256"] == _sha256_path(source_path)

    bundle = manifest.get("bundle")
    if bundle is not None:
        allowed_source_kinds = set(
            schema["properties"]["bundle"]["properties"]["sourceKind"]["enum"]
        )
        assert isinstance(bundle, dict)
        assert all(isinstance(value, str) for value in bundle.values())
        if "sourceKind" in bundle:
            assert bundle["sourceKind"] in allowed_source_kinds
        if "command" in bundle:
            assert bundle["command"]


def _assert_report_bundle_verification_contract(payload: dict[str, Any]) -> None:
    schema = _load_report_bundle_verification_schema()
    required_keys = set(schema["required"])
    allowed_keys = set(schema["properties"])
    summary_schema = schema["properties"]["summary"]
    failure_schema = schema["properties"]["failures"]["items"]

    assert required_keys <= set(payload)
    assert set(payload) <= allowed_keys
    assert payload["schema"] == schema["properties"]["schema"]["const"]
    assert isinstance(payload["bundleDir"], str) and payload["bundleDir"]
    assert isinstance(payload["manifest"], str) and payload["manifest"]
    assert isinstance(payload["ok"], bool)
    assert payload["bundleSha256"] is None or _is_sha256(payload["bundleSha256"])

    summary = payload["summary"]
    assert isinstance(summary, dict)
    assert set(summary) == set(summary_schema["required"])
    assert set(summary) <= set(summary_schema["properties"])
    assert isinstance(summary["reports"], int) and summary["reports"] >= 0
    assert isinstance(summary["failures"], int) and summary["failures"] >= 0

    failures = payload["failures"]
    assert isinstance(failures, list)
    assert summary["failures"] == len(failures)
    for failure in failures:
        assert isinstance(failure, dict)
        assert set(failure_schema["required"]) <= set(failure)
        assert set(failure) <= set(failure_schema["properties"])
        assert isinstance(failure["code"], str) and failure["code"]
        assert isinstance(failure["message"], str) and failure["message"]
        assert isinstance(failure["path"], str) and failure["path"]


def _assert_verify_bundle_command(output_dir: Path) -> None:
    payload = _run_cli(["verify-bundle", "--path", str(output_dir)])
    _assert_report_bundle_verification_contract(payload)
    assert payload["schema"] == "edgp.report.bundle.verification.v1"
    assert payload["ok"] is True
    assert payload["summary"] == {
        "reports": len(
            json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))[
                "reports"
            ]
        ),
        "failures": 0,
    }
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "verify-bundle",
            "--path",
            str(output_dir),
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.startswith("OK reports=")
    assert " failures=0 " in completed.stdout


def _assert_verify_bundle_fixture(output_dir: Path) -> None:
    payload = _run_cli(["verify-bundle", "--path", str(output_dir)])
    _assert_report_bundle_verification_contract(payload)
    fixture = json.loads(
        (REPO_ROOT / "tests/fixtures/report-bundle-verification.json").read_text(
            encoding="utf-8"
        )
    )
    assert _normalize_verification_report(payload) == fixture


def _normalize_verification_report(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    bundle_dir = str(normalized.get("bundleDir", ""))
    normalized["bundleDir"] = "<bundle-dir>"
    if normalized.get("bundleSha256") is not None:
        normalized["bundleSha256"] = "<bundleSha256>"
    normalized["failures"] = _normalize_failure_paths(
        normalized.get("failures", []),
        bundle_dir,
    )
    return normalized


def _normalize_failure_paths(
    failures: object,
    bundle_dir: str,
) -> list[dict[str, Any]]:
    normalized = []
    if not isinstance(failures, list):
        return normalized
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        item = dict(failure)
        if bundle_dir and isinstance(item.get("path"), str):
            item["path"] = item["path"].replace(bundle_dir, "<bundle-dir>", 1)
        normalized.append(item)
    return normalized


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_sha256(manifest: dict[str, Any]) -> str:
    digest_payload = {
        key: value for key, value in manifest.items() if key != "bundleSha256"
    }
    canonical = json.dumps(
        digest_payload,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_manifest_source(bundle_dir: Path, source_label: str) -> Path:
    source_path = Path(source_label)
    if source_path.is_absolute():
        candidates = [source_path]
    else:
        candidates = [
            bundle_dir / source_path,
            REPO_ROOT / source_path,
        ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise AssertionError(f"Manifest source path not found: {source_label}")


def _assert_poetry_lockfile_snapshot() -> None:
    payload = _run_cli(
        [
            "lockfile",
            "--ecosystem",
            "poetry",
            "--path",
            "tests/fixtures/poetry.lock",
            "--format",
            "json",
        ]
    )
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "pypi"
    assert payload["stats"] == {"edges": 4, "nodes": 5}


def _assert_poetry_query() -> None:
    payload = _run_cli(
        [
            "query",
            "--ecosystem",
            "poetry",
            "--path",
            "tests/fixtures/poetry.lock",
            "--operation",
            "path",
            "--node",
            "demo-lib",
            "--target",
            "urllib3",
        ]
    )
    assert payload["result"] == [
        "demo-lib==1.0.0",
        "requests==2.31.0",
        "urllib3==2.2.1",
    ]


def _assert_cargo_lockfile_snapshot() -> None:
    payload = _run_cli(
        [
            "lockfile",
            "--ecosystem",
            "cargo",
            "--path",
            "tests/fixtures/Cargo.lock",
            "--format",
            "json",
        ]
    )
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "cargo"
    assert payload["stats"] == {"edges": 4, "nodes": 5}


def _assert_cargo_query() -> None:
    payload = _run_cli(
        [
            "query",
            "--ecosystem",
            "cargo",
            "--path",
            "tests/fixtures/Cargo.lock",
            "--operation",
            "path",
            "--node",
            "demo-crate",
            "--target",
            "pin-project-lite",
        ]
    )
    assert payload["result"] == [
        "demo-crate==0.1.0",
        "tokio==1.36.0",
        "pin-project-lite==0.2.13",
    ]


def _assert_maven_tree_snapshot() -> None:
    payload = _run_cli(
        [
            "maven-tree",
            "--path",
            "tests/fixtures/maven-tree.txt",
            "--format",
            "json",
        ]
    )
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "maven"
    assert payload["stats"] == {"edges": 5, "nodes": 6}


def _assert_maven_tree_query() -> None:
    payload = _run_cli(
        [
            "query",
            "--source",
            "maven-tree",
            "--path",
            "tests/fixtures/maven-tree.txt",
            "--operation",
            "path",
            "--node",
            "com.example:demo-app",
            "--target",
            "org.hamcrest:hamcrest-core",
        ]
    )
    assert payload["result"] == [
        "com.example:demo-app==1.0.0",
        "junit:junit==4.13.2",
        "org.hamcrest:hamcrest-core==1.3",
    ]


def _assert_maven_tree_classifier_snapshot() -> None:
    payload = _run_cli(
        [
            "maven-tree",
            "--path",
            "tests/fixtures/maven-tree-classifier.txt",
            "--format",
            "json",
        ]
    )
    node_ids = {node["id"] for node in payload["nodes"]}
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["stats"] == {"edges": 3, "nodes": 4}
    assert "com.example:native-lib==1.0.0" in node_ids
    assert "com.example:native-lib:linux-x86_64==1.0.0" in node_ids


def _assert_maven_tree_packaging_snapshot() -> None:
    payload = _run_cli(
        [
            "maven-tree",
            "--path",
            "tests/fixtures/maven-tree-packaging.txt",
            "--format",
            "json",
        ]
    )
    node_ids = {node["id"] for node in payload["nodes"]}
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["stats"] == {"edges": 2, "nodes": 3}
    assert "com.example:platform==1.0.0" in node_ids
    assert "com.example:platform:pom==1.0.0" in node_ids


def _assert_maven_tree_marker_snapshot() -> None:
    payload = _run_cli(
        [
            "maven-tree",
            "--path",
            "tests/fixtures/maven-tree-markers.txt",
            "--format",
            "json",
        ]
    )
    nodes = {node["id"]: node for node in payload["nodes"]}
    edge_types = {edge["target"]: edge["relationshipType"] for edge in payload["edges"]}
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["stats"] == {"edges": 3, "nodes": 4}
    assert nodes["org.example:optional-lib==1.2.3"]["metadata"]["optional"] == "true"
    assert nodes["org.example:conflict-lib==1.0.0"]["metadata"]["omitted"] == "true"
    assert (
        nodes["org.example:conflict-lib==1.0.0"]["metadata"]["omittedReason"]
        == "conflict with 2.0.0"
    )
    assert edge_types["org.example:optional-lib==1.2.3"] == 2
    assert edge_types["org.example:conflict-lib==1.0.0"] == 3


def _assert_maven_tree_marker_html_report() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        snapshot_path = Path(temp_dir) / "maven-marker-graph.json"
        output_path = Path(temp_dir) / "maven-marker-report.html"
        payload = _run_cli(
            [
                "maven-tree",
                "--path",
                "tests/fixtures/maven-tree-markers.txt",
                "--format",
                "json",
            ]
        )
        snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--snapshot",
                str(snapshot_path),
                "--output",
                str(output_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_path)
        html = output_path.read_text(encoding="utf-8")
        assert 'data-testid="edge-relationship-panel"' in html
        assert "2 - Maven Optional" in html
        assert "3 - Maven Omitted" in html


def _assert_maven_bundle() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "maven-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "maven-bundle",
                "--path",
                "tests/fixtures/maven-tree-classifier.txt",
                "--impact-node",
                "com.example:native-lib:linux-x86_64",
                "--output-dir",
                str(output_dir),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_dir / "index.html")
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "maven-dependency-tree"
        assert manifest["bundle"]["command"].startswith("edgp maven-bundle ")
        assert manifest["reports"][0]["href"] == "001-maven-graph.html"
        assert (
            manifest["reports"][1]["href"]
            == "002-impact-com.example-native-lib-linux-x86_64-1.0.0.html"
        )
        graph_html = (output_dir / "001-maven-graph.html").read_text(encoding="utf-8")
        assert "com.example:native-lib:linux-x86_64==1.0.0" in graph_html


def _assert_dot_snapshot() -> None:
    payload = _run_cli(["dot", "--path", "tests/fixtures/repograph.dot", "--format", "json"])
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "rpm"
    assert payload["stats"] == {"edges": 5, "nodes": 4}
    assert payload["rankings"]["mostDependedUpon"][0] == {
        "package": "glibc==unknown",
        "dependents": 3,
    }


def _assert_dot_bundle() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "dot-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "dot-bundle",
                "--path",
                "tests/fixtures/repograph.dot",
                "--ecosystem",
                "rpm",
                "--impact-node",
                "glibc",
                "--output-dir",
                str(output_dir),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_dir / "index.html")
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "dot"
        assert manifest["bundle"]["command"].startswith("edgp dot-bundle ")
        assert manifest["reports"][0]["href"] == "001-dot-graph.html"
        assert manifest["reports"][1]["href"] == "002-impact-glibc-unknown.html"
        impact = json.loads(
            (output_dir / "impact-glibc-unknown.json").read_text(encoding="utf-8")
        )
        assert impact["node"] == "glibc==unknown"


def _assert_sbom_query() -> None:
    payload = _run_cli(
        [
            "query",
            "--source",
            "sbom",
            "--path",
            "tests/fixtures/sample-bom.json",
            "--operation",
            "reachable",
            "--node",
            "demo-app",
        ]
    )
    assert payload["node"] == "demo-app==1.0.0"
    assert payload["result"] == ["left-pad==1.3.0"]


def _assert_sbom_bundle() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "sbom-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "sbom-bundle",
                "--path",
                "tests/fixtures/sample-bom.json",
                "--impact-node",
                "left-pad",
                "--output-dir",
                str(output_dir),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_dir / "index.html")
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "cyclonedx-sbom"
        assert manifest["bundle"]["command"].startswith("edgp sbom-bundle ")
        assert manifest["reports"][0]["href"] == "001-sbom-graph.html"
        assert manifest["reports"][1]["href"] == "002-impact-left-pad-1.3.0.html"
        impact = json.loads(
            (output_dir / "impact-left-pad-1.3.0.json").read_text(encoding="utf-8")
        )
        assert impact["node"] == "left-pad==1.3.0"


def _assert_snapshot_diff() -> None:
    payload = _run_cli(
        [
            "diff",
            "--left",
            "tests/fixtures/snapshot-left.json",
            "--right",
            "tests/fixtures/snapshot-right.json",
        ]
    )
    assert payload["schema"] == "edgp.graph.diff.v1"
    assert payload["summary"] == {
        "addedNodes": 2,
        "removedNodes": 1,
        "addedEdges": 2,
        "removedEdges": 1,
        "metadataChangedNodes": 0,
    }


def _assert_impact_report() -> None:
    payload = _run_cli(
        [
            "impact",
            "--path",
            "tests/fixtures/package-lock.json",
            "--node",
            "left-pad",
        ]
    )
    assert payload["schema"] == "edgp.impact.report.v1"
    assert payload["node"] == "left-pad==1.3.0"
    assert payload["summary"]["directDependents"] == 2
    assert payload["summary"]["affectedDependents"] == 2


def _assert_advisory_overlay() -> None:
    payload = _run_cli(
        [
            "advisory",
            "--path",
            "tests/fixtures/package-lock.json",
            "--advisories",
            "tests/fixtures/advisories.json",
        ]
    )
    assert payload["schema"] == "edgp.advisory.report.v1"
    assert payload["summary"]["advisories"] == 2
    assert payload["summary"]["findings"] == 1
    assert payload["findings"][0]["package"] == "left-pad==1.3.0"


def _assert_rpm_advisory_overlay() -> None:
    payload = _run_cli(
        [
            "advisory",
            "--source",
            "dot",
            "--path",
            "tests/fixtures/repograph.dot",
            "--ecosystem",
            "rpm",
            "--advisories",
            "tests/fixtures/rpm-advisories.json",
        ]
    )
    assert payload["schema"] == "edgp.advisory.report.v1"
    assert payload["ecosystem"] == "rpm"
    assert payload["summary"]["findings"] == 1
    assert payload["findings"][0]["package"] == "glibc==unknown"


def _assert_html_report() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "snapshot-report.html"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output",
                str(output_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_path)
        html = output_path.read_text(encoding="utf-8")
        assert 'data-testid="report-hero"' in html
        assert 'data-testid="edge-filter-panel"' in html
        assert 'data-edge-filter-search' in html
        assert 'data-edge-filter-count' in html
        assert 'data-edge-filter-more' in html
        assert 'data-edge-page-size="250"' in html
        assert "data-sortable-table" in html
        assert 'data-sort-type="number"' in html
        assert "EDGP Snapshot Report - app==1.0.0" in html


def _assert_browser_smoke_report_sorting() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "report-sorting-smoke.html"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "scripts/browser_smoke_report_sorting.py",
                "--output",
                str(output_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_path)
        html = output_path.read_text(encoding="utf-8")
        assert 'data-testid="browser-smoke-panel"' in html
        assert 'data-testid="browser-smoke-result"' in html
        assert "edge target descending" in html
        assert "node package ascending" in html
        assert "dataset.browserSmokeStatus = 'pass'" in html


def _assert_browser_smoke_report_bundle_navigation() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "report-bundle-navigation-smoke"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "scripts/browser_smoke_report_bundle_navigation.py",
                "--output-dir",
                str(output_dir),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        index_path = output_dir / "index.html"
        assert completed.stdout.strip() == str(index_path)
        html = index_path.read_text(encoding="utf-8")
        assert 'data-testid="browser-smoke-panel"' in html
        assert 'data-testid="browser-smoke-frame"' in html
        assert "bundle link order" in html
        assert "003-impact-report.html" in html
        assert "dataset.browserSmokeStatus = 'pass'" in html
        assert (output_dir / "001-snapshot-right.html").exists()
        assert (output_dir / "002-npm-diagnostics-report.html").exists()
        assert (output_dir / "003-impact-report.html").exists()


def _assert_impact_html_report() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "impact-report.html"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                "tests/fixtures/impact-report.json",
                "--output",
                str(output_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_path)
        html = output_path.read_text(encoding="utf-8")
        assert 'data-testid="impact-chains-panel"' in html
        assert "EDGP Impact Report - left-pad==1.3.0" in html


def _assert_advisory_html_report() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "advisory-report.html"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                "tests/fixtures/advisory-report.json",
                "--output",
                str(output_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_path)
        html = output_path.read_text(encoding="utf-8")
        assert 'data-testid="advisory-findings-panel"' in html
        assert "ADV-LOCAL-0001" in html


def _assert_npm_diagnostics_html_report() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "npm-diagnostics-report.html"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--output",
                str(output_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_path)
        html = output_path.read_text(encoding="utf-8")
        assert 'data-testid="npm-conflicts-panel"' in html
        assert "EDGP npm Diagnostics - conflict-app==1.0.0" in html


def _assert_report_bundle() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report-bundle",
                "--input",
                "tests/fixtures/snapshot-right.json",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--output-dir",
                str(output_dir),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        index_path = output_dir / "index.html"
        assert completed.stdout.strip() == str(index_path)
        index_html = index_path.read_text(encoding="utf-8")
        assert 'data-testid="report-bundle-index"' in index_html
        assert 'data-testid="report-bundle-verification"' in index_html
        assert "002-npm-diagnostics-report.html" in index_html
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        _assert_verify_bundle_fixture(output_dir)
        validation = _run_cli(["validate", "--path", str(output_dir)])
        assert validation["schema"] == "edgp.validation.report.v1"
        assert validation["ok"] is True
        assert validation["targetType"] == "report-bundle"
        assert validation["bundleVerification"]["ok"] is True
        assert manifest["schema"] == "edgp.report.bundle.v1"
        assert manifest["bundle"]["sourceKind"] == "edgp-json"
        assert manifest["bundle"]["command"].startswith("edgp report-bundle ")
        assert manifest["bundleSha256"][:12] in index_html
        assert manifest["reports"][1]["href"] == "002-npm-diagnostics-report.html"
        npm_html = (output_dir / "002-npm-diagnostics-report.html").read_text(
            encoding="utf-8"
        )
        assert 'data-testid="npm-unresolved-panel"' in npm_html


def _assert_verify_bundle_detects_tampering() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "bundle"
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report-bundle",
                "--input",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(output_dir),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        (output_dir / "001-snapshot-right.html").write_text(
            "<!doctype html><title>tampered</title>",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "verify-bundle",
                "--path",
                str(output_dir),
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        payload = json.loads(completed.stdout)
        assert completed.returncode == 1
        _assert_report_bundle_verification_contract(payload)
        assert payload["ok"] is False
        assert payload["failures"][0]["code"] == "htmlDigestMismatch"


def _assert_bundle_validation_failure_fixtures() -> None:
    cases = [
        (
            "tampered-report-bundle-manifest",
            "report-bundle-verification-tampered-manifest.json",
            "validation-failure-tampered-bundle-manifest.json",
            "bundleDigestMismatch",
            "bundle.bundleDigestMismatch",
            1,
        ),
        (
            "tampered-report-bundle-member",
            "report-bundle-verification-tampered-member.json",
            "validation-failure-tampered-bundle-member.json",
            "htmlDigestMismatch",
            "bundle.htmlDigestMismatch",
            1,
        ),
        (
            "missing-html-report-bundle",
            "report-bundle-verification-missing-html.json",
            "validation-failure-missing-bundle-html.json",
            "htmlMissing",
            "bundle.htmlMissing",
            1,
        ),
        (
            "missing-source-report-bundle",
            "report-bundle-verification-missing-source.json",
            "validation-failure-missing-bundle-source.json",
            "sourceMissing",
            "bundle.sourceMissing",
            1,
        ),
        (
            "invalid-manifest-missing-report-count-bundle",
            "report-bundle-verification-invalid-manifest-missing-report-count.json",
            "validation-failure-invalid-manifest-missing-report-count.json",
            "manifestMissingField",
            "bundle.manifestMissingField",
            2,
        ),
        (
            "invalid-report-missing-title-bundle",
            "report-bundle-verification-invalid-report-missing-title.json",
            "validation-failure-invalid-report-missing-title.json",
            "reportMissingField",
            "bundle.reportMissingField",
            2,
        ),
        (
            "invalid-manifest-unknown-field-bundle",
            "report-bundle-verification-invalid-manifest-unknown-field.json",
            "validation-failure-invalid-manifest-unknown-field.json",
            "manifestUnknownField",
            "bundle.manifestUnknownField",
            1,
        ),
        (
            "invalid-report-unknown-field-bundle",
            "report-bundle-verification-invalid-report-unknown-field.json",
            "validation-failure-invalid-report-unknown-field.json",
            "reportUnknownField",
            "bundle.reportUnknownField",
            1,
        ),
        (
            "invalid-bundle-source-kind-bundle",
            "report-bundle-verification-invalid-bundle-source-kind.json",
            "validation-failure-invalid-bundle-source-kind.json",
            "bundleSourceKindInvalid",
            "bundle.bundleSourceKindInvalid",
            1,
        ),
        (
            "invalid-report-digest-bundle",
            "report-bundle-verification-invalid-report-digest.json",
            "validation-failure-invalid-report-digest.json",
            "reportDigestInvalid",
            "bundle.reportDigestInvalid",
            1,
        ),
        (
            "invalid-bundle-metadata-bundle",
            "report-bundle-verification-invalid-bundle-metadata.json",
            "validation-failure-invalid-bundle-metadata.json",
            "bundleInvalid",
            "bundle.bundleInvalid",
            1,
        ),
        (
            "invalid-index-path-bundle",
            "report-bundle-verification-invalid-index-path.json",
            "validation-failure-invalid-index-path.json",
            "indexInvalid",
            "bundle.indexInvalid",
            1,
        ),
        (
            "invalid-manifest-schema-bundle",
            "report-bundle-verification-invalid-manifest-schema.json",
            "validation-failure-invalid-manifest-schema.json",
            "manifestSchemaMismatch",
            "bundle.manifestSchemaMismatch",
            1,
        ),
        (
            "invalid-bundle-digest-bundle",
            "report-bundle-verification-invalid-bundle-digest.json",
            "validation-failure-invalid-bundle-digest.json",
            "bundleDigestInvalid",
            "bundle.bundleDigestInvalid",
            1,
        ),
        (
            "invalid-reports-list-bundle",
            "report-bundle-verification-invalid-reports-list.json",
            "validation-failure-invalid-reports-list.json",
            "reportsInvalid",
            "bundle.reportsInvalid",
            1,
        ),
        (
            "invalid-report-entry-bundle",
            "report-bundle-verification-invalid-report-entry.json",
            "validation-failure-invalid-report-entry.json",
            "reportInvalid",
            "bundle.reportInvalid",
            1,
        ),
        (
            "invalid-report-field-bundle",
            "report-bundle-verification-invalid-report-field.json",
            "validation-failure-invalid-report-field.json",
            "reportFieldInvalid",
            "bundle.reportFieldInvalid",
            1,
        ),
        (
            "invalid-report-summary-bundle",
            "report-bundle-verification-invalid-report-summary.json",
            "validation-failure-invalid-report-summary.json",
            "reportSummaryInvalid",
            "bundle.reportSummaryInvalid",
            1,
        ),
        (
            "invalid-report-count-bundle",
            "report-bundle-verification-invalid-report-count.json",
            "validation-failure-invalid-report-count.json",
            "reportCountMismatch",
            "bundle.reportCountMismatch",
            1,
        ),
        (
            "invalid-report-href-bundle",
            "report-bundle-verification-invalid-report-href.json",
            "validation-failure-invalid-report-href.json",
            "reportHrefInvalid",
            "bundle.reportHrefInvalid",
            1,
        ),
        (
            "missing-index-report-bundle",
            "report-bundle-verification-missing-index.json",
            "validation-failure-missing-index.json",
            "indexMissing",
            "bundle.indexMissing",
            1,
        ),
        (
            "source-digest-mismatch-bundle",
            "report-bundle-verification-source-digest-mismatch.json",
            "validation-failure-source-digest-mismatch.json",
            "sourceDigestMismatch",
            "bundle.sourceDigestMismatch",
            1,
        ),
        (
            "missing-manifest-report-bundle",
            "report-bundle-verification-missing-manifest.json",
            "validation-failure-missing-manifest.json",
            "manifestMissing",
            "bundle.manifestMissing",
            1,
        ),
        (
            "invalid-json-manifest-bundle",
            "report-bundle-verification-invalid-json-manifest.json",
            "validation-failure-invalid-json-manifest.json",
            "manifestInvalidJson",
            "bundle.manifestInvalidJson",
            1,
        ),
        (
            "invalid-manifest-type-bundle",
            "report-bundle-verification-invalid-manifest-type.json",
            "validation-failure-invalid-manifest-type.json",
            "manifestInvalid",
            "bundle.manifestInvalid",
            1,
        ),
    ]
    expected_failure_codes = {
        "bundleDigestInvalid",
        "bundleDigestMismatch",
        "bundleInvalid",
        "bundleSourceKindInvalid",
        "htmlDigestMismatch",
        "htmlMissing",
        "indexInvalid",
        "indexMissing",
        "manifestInvalid",
        "manifestInvalidJson",
        "manifestMissing",
        "manifestMissingField",
        "manifestSchemaMismatch",
        "manifestUnknownField",
        "reportCountMismatch",
        "reportDigestInvalid",
        "reportFieldInvalid",
        "reportHrefInvalid",
        "reportInvalid",
        "reportMissingField",
        "reportSummaryInvalid",
        "reportUnknownField",
        "reportsInvalid",
        "sourceDigestMismatch",
        "sourceMissing",
    }
    assert {case[3] for case in cases} == expected_failure_codes

    for (
        bundle_name,
        verification_fixture_name,
        validation_fixture_name,
        verify_code,
        validate_code,
        failure_count,
    ) in cases:
        bundle_path = Path("tests/fixtures") / bundle_name
        verification_payload = _run_cli_allow_failure(
            ["verify-bundle", "--path", str(bundle_path)]
        )
        _assert_report_bundle_verification_contract(verification_payload)
        verification_fixture = json.loads(
            (REPO_ROOT / "tests" / "fixtures" / verification_fixture_name).read_text(
                encoding="utf-8"
            )
        )
        assert _normalize_verification_report(verification_payload) == verification_fixture

        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "verify-bundle",
                "--path",
                str(bundle_path),
                "--format",
                "text",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 1
        no_report_codes = {
            "manifestInvalid",
            "manifestInvalidJson",
            "manifestMissing",
            "reportsInvalid",
        }
        no_bundle_sha_codes = {
            "bundleDigestInvalid",
            "manifestInvalid",
            "manifestInvalidJson",
            "manifestMissing",
        }
        report_count = 0 if verify_code in no_report_codes else 1
        if verify_code in no_bundle_sha_codes:
            assert completed.stdout.startswith(
                f"FAIL reports={report_count} failures={failure_count} "
            )
            assert "bundleSha256=" not in completed.stdout
        else:
            assert completed.stdout.startswith(
                f"FAIL reports={report_count} failures={failure_count} "
                "bundleSha256="
            )
        assert f"firstFailure={verify_code}" in completed.stdout

        validation_payload = _run_cli_allow_failure(
            ["validate", "--path", str(bundle_path)]
        )
        validation_fixture = json.loads(
            (REPO_ROOT / "tests" / "fixtures" / validation_fixture_name).read_text(
                encoding="utf-8"
            )
        )
        assert _normalize_validation_report(validation_payload) == validation_fixture

        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "validate",
                "--path",
                str(bundle_path),
                "--format",
                "text",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 1
        assert completed.stdout.strip() == (
            f"FAIL targetType=report-bundle failures={failure_count} "
            f"contract=edgp.report.bundle.v1 firstFailure={validate_code}"
        )


def _assert_npm_bundle() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "npm-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "npm-bundle",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
                "--output-dir",
                str(output_dir),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_dir / "index.html")
        graph = json.loads((output_dir / "npm-graph.json").read_text(encoding="utf-8"))
        diagnostics = json.loads(
            (output_dir / "npm-diagnostics.json").read_text(encoding="utf-8")
        )
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        assert graph["schema"] == "edgp.graph.snapshot.v1"
        assert diagnostics["schema"] == "edgp.npm.diagnostics.v1"
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "npm-lockfile"
        assert manifest["bundle"]["command"].startswith("edgp npm-bundle ")
        assert manifest["reports"][1]["href"] == "002-npm-diagnostics.html"


def _assert_npm_bundle_with_impact_and_advisory() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "npm-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "npm-bundle",
                "--path",
                "tests/fixtures/package-lock.json",
                "--impact-node",
                "left-pad",
                "--advisories",
                "tests/fixtures/advisories.json",
                "--output-dir",
                str(output_dir),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_dir / "index.html")
        impact = json.loads(
            (output_dir / "impact-left-pad-1.3.0.json").read_text(encoding="utf-8")
        )
        advisory = json.loads(
            (output_dir / "advisory-report.json").read_text(encoding="utf-8")
        )
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        assert impact["schema"] == "edgp.impact.report.v1"
        assert advisory["schema"] == "edgp.advisory.report.v1"
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "npm-lockfile"
        assert manifest["bundle"]["command"].startswith("edgp npm-bundle ")
        assert manifest["reports"][2]["href"] == "003-impact-left-pad-1.3.0.html"
        assert manifest["reports"][3]["href"] == "004-advisory-report.html"


def _assert_benchmark() -> None:
    payload = _run_cli(["benchmark", "--nodes", "64", "--fanout", "3"])
    assert payload["schema"] == "edgp.benchmark.v1"
    assert payload["stats"]["nodes"] == 64
    assert payload["stats"]["edges"] == 186
    assert payload["stats"]["reachableFromRoot"] == 63


def _assert_rpm_installed() -> None:
    payload = _run_cli(
        ["rpm-installed", "--limit", "5", "--max-requirements", "10", "--format", "json"]
    )
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "rpm"
    assert payload["root"] == "rpm-installed==local"
    assert payload["stats"]["nodes"] >= 1


def _assert_rpm_installed_bundle() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "rpm-installed-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "rpm-installed-bundle",
                "--limit",
                "5",
                "--max-requirements",
                "10",
                "--impact-node",
                "rpm-installed==local",
                "--output-dir",
                str(output_dir),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_dir / "index.html")
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "rpm-installed"
        assert manifest["bundle"]["command"].startswith("edgp rpm-installed-bundle ")
        assert manifest["reports"][0]["href"] == "001-rpm-installed-graph.html"
        assert manifest["reports"][1]["href"] == "002-impact-rpm-installed-local.html"
        graph = json.loads(
            (output_dir / "rpm-installed-graph.json").read_text(encoding="utf-8")
        )
        assert graph["schema"] == "edgp.graph.snapshot.v1"
        assert graph["root"] == "rpm-installed==local"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-rpm-installed",
        action="store_true",
        help="also validate live rpmdb ingestion on an RPM-based host",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checks = [
        ("compile", _assert_compile),
        ("lockfile snapshot", _assert_lockfile_snapshot),
        ("npm diagnostics", _assert_npm_diagnostics),
        ("validate command", _assert_validate_command),
        ("report bundle manifest schema", _assert_report_bundle_manifest_schema_document),
        (
            "report bundle verification schema",
            _assert_report_bundle_verification_schema_document,
        ),
        ("report json schemas", _assert_report_json_schemas_document),
        ("schema index", _assert_schema_index_document),
        ("failure example index", _assert_failure_example_index_document),
        (
            "validation failure example quick links",
            _assert_validation_failure_examples_quick_links,
        ),
        (
            "readme validation guide anchors",
            _assert_readme_validation_guide_anchors,
        ),
        (
            "readme validation failure fixture links",
            _assert_readme_validation_failure_fixture_links,
        ),
        ("poetry lockfile snapshot", _assert_poetry_lockfile_snapshot),
        ("poetry query", _assert_poetry_query),
        ("cargo lockfile snapshot", _assert_cargo_lockfile_snapshot),
        ("cargo query", _assert_cargo_query),
        ("maven tree snapshot", _assert_maven_tree_snapshot),
        ("maven tree query", _assert_maven_tree_query),
        ("maven classifier snapshot", _assert_maven_tree_classifier_snapshot),
        ("maven packaging snapshot", _assert_maven_tree_packaging_snapshot),
        ("maven marker snapshot", _assert_maven_tree_marker_snapshot),
        ("maven marker html report", _assert_maven_tree_marker_html_report),
        ("maven bundle", _assert_maven_bundle),
        ("dot snapshot", _assert_dot_snapshot),
        ("dot bundle", _assert_dot_bundle),
        ("sbom query", _assert_sbom_query),
        ("sbom bundle", _assert_sbom_bundle),
        ("snapshot diff", _assert_snapshot_diff),
        ("impact report", _assert_impact_report),
        ("advisory overlay", _assert_advisory_overlay),
        ("rpm advisory overlay", _assert_rpm_advisory_overlay),
        ("html report", _assert_html_report),
        ("browser smoke report sorting", _assert_browser_smoke_report_sorting),
        (
            "browser smoke report bundle navigation",
            _assert_browser_smoke_report_bundle_navigation,
        ),
        ("impact html report", _assert_impact_html_report),
        ("advisory html report", _assert_advisory_html_report),
        ("npm diagnostics html report", _assert_npm_diagnostics_html_report),
        ("report bundle", _assert_report_bundle),
        ("verify bundle tamper detection", _assert_verify_bundle_detects_tampering),
        (
            "bundle validation failure fixtures",
            _assert_bundle_validation_failure_fixtures,
        ),
        ("npm bundle", _assert_npm_bundle),
        ("npm bundle impact advisory", _assert_npm_bundle_with_impact_and_advisory),
        ("synthetic benchmark", _assert_benchmark),
    ]
    if args.include_rpm_installed:
        checks.append(("installed rpm graph", _assert_rpm_installed))
        checks.append(("installed rpm bundle", _assert_rpm_installed_bundle))

    for label, check in checks:
        check()
        print(f"ok - {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
