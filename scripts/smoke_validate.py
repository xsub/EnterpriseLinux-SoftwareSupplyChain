"""Run dependency graph smoke checks without extra test-only dependencies."""

from __future__ import annotations

import argparse
import ast
import compileall
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
ARCHITECTURE_DOC_PATH = (
    REPO_ROOT / "docs" / "Architecture and Traversal of Massive-Scale Dependency Graphs.md"
)
REPORT_SCHEMA_DOC_PATHS = (
    REPO_ROOT / "docs" / "Report JSON Schemas.md",
    REPO_ROOT / "docs" / "Report Bundle Manifest Schema.md",
    REPO_ROOT / "docs" / "Report Bundle Verification Schema.md",
)
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
PYTHON_TRANSLATION_UNIT_DIRS = ("src", "scripts", "tests")
REPORT_JSON_SCHEMA_CONTRACTS = {
    "edgp.albs.build_diff.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.albs.build_diff.v1.schema.json",
    "edgp.albs.log_intelligence.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.albs.log_intelligence.v1.schema.json",
    "edgp.albs.release_completeness.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.albs.release_completeness.v1.schema.json",
    "edgp.albs.artifact_inventory.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.albs.artifact_inventory.v1.schema.json",
    "edgp.albs.build_timing.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.albs.build_timing.v1.schema.json",
    "edgp.graph.diff.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.graph.diff.v1.schema.json",
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
    "edgp.bundle.catalog.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.bundle.catalog.v1.schema.json",
    "edgp.csr.artifact.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.csr.artifact.v1.schema.json",
    "edgp.export.batch.archive.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.export.batch.archive.v1.schema.json",
    "edgp.export.batch.submission_plan.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.export.batch.submission_plan.v1.schema.json",
    "edgp.export.batch.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.export.batch.v1.schema.json",
    "edgp.export.batch.verification.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.export.batch.verification.v1.schema.json",
    "edgp.fixture.provenance.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.fixture.provenance.v1.schema.json",
    "edgp.report.bundle.archive.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.report.bundle.archive.v1.schema.json",
    "edgp.report.bundle.submission_plan.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.report.bundle.submission_plan.v1.schema.json",
    "edgp.submission.plan.index.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.submission.plan.index.v1.schema.json",
    "edgp.npm.diagnostics.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.npm.diagnostics.v1.schema.json",
    "edgp.libsolv.bridge.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.libsolv.bridge.v1.schema.json",
    "edgp.license.report.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.license.report.v1.schema.json",
    "edgp.performance.report.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.performance.report.v1.schema.json",
    "edgp.parallel.query.report.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.parallel.query.report.v1.schema.json",
    "edgp.public.advisory_feed.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.public.advisory_feed.v1.schema.json",
    "edgp.real_data.coverage.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.real_data.coverage.v1.schema.json",
    "edgp.real_data.coverage_diff.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.real_data.coverage_diff.v1.schema.json",
    "edgp.real_data.replacement_plan.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.real_data.replacement_plan.v1.schema.json",
    "edgp.real_data.replacement_plan_diff.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.real_data.replacement_plan_diff.v1.schema.json",
    "edgp.query.report.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.query.report.v1.schema.json",
    "edgp.rpm.albs_provenance.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.rpm.albs_provenance.v1.schema.json",
    "edgp.rpm.repository_diff.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.rpm.repository_diff.v1.schema.json",
    "edgp.rpm.repository_summary.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.rpm.repository_summary.v1.schema.json",
    "edgp.schema.index.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.schema.index.v1.schema.json",
    "edgp.triage.summary.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.triage.summary.v1.schema.json",
    "edgp.validation.report.v1": REPO_ROOT
    / "docs"
    / "schemas"
    / "edgp.validation.report.v1.schema.json",
}
REPORT_JSON_SCHEMA_FIXTURES = {
    "edgp.albs.build_diff.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "albs-build-diff.json",
    "edgp.albs.log_intelligence.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "albs-log-intelligence.json",
    "edgp.albs.release_completeness.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "albs-release-completeness.json",
    "edgp.albs.artifact_inventory.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "albs-artifact-inventory.json",
    "edgp.albs.build_timing.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "albs-build-timing.json",
    "edgp.graph.diff.v1": REPO_ROOT / "tests" / "fixtures" / "graph-diff.json",
    "edgp.graph.snapshot.v1": REPO_ROOT / "tests" / "fixtures" / "snapshot-right.json",
    "edgp.impact.report.v1": REPO_ROOT / "tests" / "fixtures" / "impact-report.json",
    "edgp.advisory.report.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "advisory-report.json",
    "edgp.bundle.catalog.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "bundle-catalog.json",
    "edgp.csr.artifact.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "csr-artifact-manifest.json",
    "edgp.export.batch.archive.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "export-batch-archive.json",
    "edgp.export.batch.submission_plan.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "export-batch-submission-plan.json",
    "edgp.export.batch.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "export-batch.json",
    "edgp.export.batch.verification.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "export-batch-verification.json",
    "edgp.fixture.provenance.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "fixture-provenance.json",
    "edgp.report.bundle.archive.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "report-bundle-archive.json",
    "edgp.report.bundle.submission_plan.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "report-bundle-submission-plan.json",
    "edgp.npm.diagnostics.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "npm-diagnostics-report.json",
    "edgp.libsolv.bridge.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "libsolv-bridge.json",
    "edgp.license.report.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "license-report.json",
    "edgp.performance.report.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "performance-report.json",
    "edgp.parallel.query.report.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "parallel-query-report.json",
    "edgp.public.advisory_feed.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "public-advisory-feed.json",
    "edgp.real_data.coverage.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "real-data-coverage.json",
    "edgp.real_data.coverage_diff.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "real-data-coverage-diff.json",
    "edgp.real_data.replacement_plan.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "real-data-replacement-plan.json",
    "edgp.real_data.replacement_plan_diff.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "real-data-replacement-plan-diff.json",
    "edgp.query.report.v1": REPO_ROOT / "tests" / "fixtures" / "query-report.json",
    "edgp.rpm.albs_provenance.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "rpm-albs-provenance.json",
    "edgp.rpm.repository_diff.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "rpm-repository-diff.json",
    "edgp.rpm.repository_summary.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "rpm-repository-summary.json",
    "edgp.schema.index.v1": SCHEMA_INDEX_PATH,
    "edgp.triage.summary.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "triage-summary.json",
    "edgp.validation.report.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "validation-failure-missing-edge-count.json",
    "edgp.submission.plan.index.v1": REPO_ROOT
    / "tests"
    / "fixtures"
    / "submission-plan-index.json",
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
    archive_path = ""
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
    bundle_archive_verification = normalized.get("bundleArchiveVerification")
    if isinstance(bundle_archive_verification, dict):
        archive = _normalize_archive_verification_report(bundle_archive_verification)
        archive_path = str(bundle_archive_verification.get("archive", ""))
        bundle_dir = str(bundle_archive_verification.get("bundleDir", ""))
        normalized["bundleArchiveVerification"] = archive
    normalized["target"] = "<target>"
    normalized["failures"] = _normalize_failure_paths(
        normalized.get("failures", []),
        bundle_dir,
        archive_path=archive_path,
    )
    return normalized


def _normalize_archive_verification_report(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    archive_path = str(normalized.get("archive", ""))
    bundle_dir = str(normalized.get("bundleDir", ""))
    normalized["archive"] = "<archive>"
    normalized["bundleDir"] = "<bundle-dir>"
    if normalized.get("archiveSha256") is not None:
        normalized["archiveSha256"] = "<archiveSha256>"
    if normalized.get("bundleSha256") is not None:
        normalized["bundleSha256"] = "<bundleSha256>"
    verification = normalized.get("verification")
    if isinstance(verification, dict):
        nested = dict(verification)
        nested_bundle_dir = str(nested.get("bundleDir", bundle_dir))
        nested["bundleDir"] = "<bundle-dir>"
        if nested.get("bundleSha256") is not None:
            nested["bundleSha256"] = "<bundleSha256>"
        nested["failures"] = _normalize_failure_paths(
            nested.get("failures", []),
            nested_bundle_dir,
            archive_path=archive_path,
        )
        normalized["verification"] = nested
    return normalized


def _assert_compile() -> None:
    ok = compileall.compile_dir(REPO_ROOT / "src", quiet=1)
    ok = compileall.compile_dir(REPO_ROOT / "scripts", quiet=1) and ok
    ok = compileall.compile_dir(REPO_ROOT / "tests", quiet=1) and ok
    if not ok:
        raise AssertionError("compileall failed")


def _python_translation_unit_paths() -> list[Path]:
    paths: list[Path] = []
    for directory in PYTHON_TRANSLATION_UNIT_DIRS:
        paths.extend((REPO_ROOT / directory).rglob("*.py"))
    return sorted(paths, key=lambda path: path.relative_to(REPO_ROOT).as_posix())


def _assert_python_translation_unit_docstrings() -> None:
    missing: list[str] = []
    for path in _python_translation_unit_paths():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstring = ast.get_docstring(tree, clean=False)
        if not docstring or not docstring.strip():
            missing.append(path.relative_to(REPO_ROOT).as_posix())

    if missing:
        raise AssertionError(
            "Python translation units missing top-level descriptions: "
            + ", ".join(missing)
        )


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

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "npm-diagnostics-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "npm-diagnostics-bundle",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "npm-diagnostics"
        assert manifest["reports"][0]["href"] == "001-npm-diagnostics.html"
        assert manifest["reports"][0]["schema"] == "edgp.npm.diagnostics.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        report = json.loads(
            (output_dir / "npm-diagnostics.json").read_text(encoding="utf-8")
        )
        assert report["schema"] == "edgp.npm.diagnostics.v1"
        assert report["summary"]["nestedResolutionConflicts"] == 1
        assert report["summary"]["unresolvedDependencies"] == 1
        assert 'data-testid="npm-conflicts-panel"' in (
            output_dir / "001-npm-diagnostics.html"
        ).read_text(encoding="utf-8")


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

    with tempfile.TemporaryDirectory() as temp_dir:
        validation_path = Path(temp_dir) / "validation-report.json"
        validation_path.write_text(json.dumps(payload), encoding="utf-8")
        html_path = Path(temp_dir) / "validation-report.html"
        completed_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                str(validation_path),
                "--output",
                str(html_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert Path(completed_report.stdout.strip()) == html_path
        html = html_path.read_text(encoding="utf-8")
        assert 'data-testid="validation-target-panel"' in html
        assert "edgp.graph.snapshot.v1" in html

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
    with tempfile.TemporaryDirectory() as temp_dir:
        html_path = Path(temp_dir) / "validation-failure.html"
        completed_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                "tests/fixtures/validation-failure-missing-edge-count.json",
                "--output",
                str(html_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert Path(completed_report.stdout.strip()) == html_path
        html = html_path.read_text(encoding="utf-8")
        assert 'data-testid="validation-failures-panel"' in html
        assert "requiredMissing" in html

    archive_failure_payload = _run_cli_allow_failure(
        [
            "validate",
            "--path",
            "tests/fixtures/missing-report-bundle.tar.gz",
        ]
    )
    archive_fixture = json.loads(
        (
            REPO_ROOT
            / "tests"
            / "fixtures"
            / "validation-failure-missing-bundle-archive.json"
        ).read_text(encoding="utf-8")
    )
    assert _normalize_validation_report(archive_failure_payload) == archive_fixture

    catalog_payload = _run_cli(["validate", "--path", "tests/fixtures/bundle-catalog.json"])
    assert catalog_payload["ok"] is True
    assert catalog_payload["contract"] == "edgp.bundle.catalog.v1"
    with tempfile.TemporaryDirectory() as temp_dir:
        invalid_catalog_path = Path(temp_dir) / "invalid-bundle-catalog.json"
        invalid_catalog = json.loads(
            (REPO_ROOT / "tests" / "fixtures" / "bundle-catalog.json").read_text(
                encoding="utf-8"
            )
        )
        invalid_catalog["bundles"][0]["bundleSha256"] = 42
        invalid_catalog_path.write_text(
            json.dumps(invalid_catalog, sort_keys=True),
            encoding="utf-8",
        )
        invalid_catalog_report = _run_cli_allow_failure(
            ["validate", "--path", str(invalid_catalog_path)]
        )
        assert {
            "code": "anyOfMismatch",
            "message": "Value must match at least one schema",
            "path": "$.bundles[0].bundleSha256",
        } in invalid_catalog_report["failures"]

    with tempfile.TemporaryDirectory() as temp_dir:
        impact_path = Path(temp_dir) / "impact-report-null-root.json"
        impact_payload = json.loads(
            (REPO_ROOT / "tests" / "fixtures" / "impact-report.json").read_text(
                encoding="utf-8"
            )
        )
        impact_payload["root"] = None
        impact_path.write_text(
            json.dumps(impact_payload, sort_keys=True),
            encoding="utf-8",
        )
        impact_report = _run_cli(["validate", "--path", str(impact_path)])
        assert impact_report["ok"] is True
        assert impact_report["contract"] == "edgp.impact.report.v1"

        impact_payload["root"] = 42
        invalid_impact_path = Path(temp_dir) / "impact-report-invalid-root.json"
        invalid_impact_path.write_text(
            json.dumps(impact_payload, sort_keys=True),
            encoding="utf-8",
        )
        invalid_impact_report = _run_cli_allow_failure(
            ["validate", "--path", str(invalid_impact_path)]
        )
        assert {
            "code": "oneOfMismatch",
            "message": "Value must match exactly one schema",
            "path": "$.root",
        } in invalid_impact_report["failures"]

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
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        manifest["bundle"]["ciRun"] = "local"
        manifest_path = Path(temp_dir) / "manifest-with-extra-metadata.json"
        manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
        manifest_report = _run_cli(["validate", "--path", str(manifest_path)])
        assert manifest_report["ok"] is True
        assert manifest_report["contract"] == "edgp.report.bundle.v1"

        manifest["bundle"]["ciRun"] = {"not": "string"}
        invalid_manifest_path = (
            Path(temp_dir) / "manifest-with-invalid-extra-metadata.json"
        )
        invalid_manifest_path.write_text(
            json.dumps(manifest, sort_keys=True),
            encoding="utf-8",
        )
        invalid_manifest_report = _run_cli_allow_failure(
            ["validate", "--path", str(invalid_manifest_path)]
        )
        assert {
            "code": "typeMismatch",
            "message": "Expected type string",
            "path": "$.bundle.ciRun",
        } in invalid_manifest_report["failures"]


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
        "advisory-report",
        "albs-build",
        "albs-build-diff",
        "albs-artifact-inventory",
        "albs-build-timing",
        "albs-log-intelligence",
        "albs-release-completeness",
        "bundle-catalog",
        "cyclonedx-sbom",
        "dot",
        "edgp-json",
        "fixture-provenance",
        "graph-diff",
        "impact-report",
        "license-report",
        "libsolv-transaction",
        "maven-dependency-tree",
        "npm-diagnostics",
        "npm-lockfile",
        "performance-report",
        "public-advisory-feed",
        "query-report",
        "real-data-coverage",
        "real-data-coverage-diff",
        "real-data-replacement-plan",
        "real-data-replacement-plan-diff",
        "rpm-albs-provenance",
        "rpm-installed",
        "rpm-repository",
        "rpm-repository-diff",
        "rpm-repository-summary",
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
        "edgp.albs.build_diff.v1",
        "edgp.albs.log_intelligence.v1",
        "edgp.albs.release_completeness.v1",
        "edgp.albs.artifact_inventory.v1",
        "edgp.albs.build_timing.v1",
        "edgp.advisory.report.v1",
        "edgp.bundle.catalog.v1",
        "edgp.export.batch.archive.v1",
        "edgp.export.batch.submission_plan.v1",
        "edgp.export.batch.v1",
        "edgp.export.batch.verification.v1",
        "edgp.graph.diff.v1",
        "edgp.graph.snapshot.v1",
        "edgp.impact.report.v1",
        "edgp.libsolv.bridge.v1",
        "edgp.license.report.v1",
        "edgp.npm.diagnostics.v1",
        "edgp.performance.report.v1",
        "edgp.public.advisory_feed.v1",
        "edgp.query.report.v1",
        "edgp.report.bundle.submission_plan.v1",
        "edgp.report.bundle.v1",
        "edgp.report.bundle.verification.v1",
        "edgp.rpm.albs_provenance.v1",
        "edgp.rpm.repository_diff.v1",
        "edgp.rpm.repository_summary.v1",
        "edgp.schema.index.v1",
        "edgp.submission.plan.index.v1",
        "edgp.triage.summary.v1",
        "edgp.validation.report.v1",
        "edgp.validation.failure.example.filters.v1",
        "edgp.validation.failure.example.index.v1",
    } <= contracts
    for schema in index["schemas"]:
        assert schema["file"].endswith(".schema.json")
        assert schema["id"].startswith("urn:edgp:schema:")
        assert schema["jsonSchema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["title"]
        assert schema["description"]
    validation = _run_cli(["validate", "--path", str(SCHEMA_INDEX_PATH)])
    assert validation["ok"] is True
    assert validation["contract"] == "edgp.schema.index.v1"
    assert validation["schemaFile"] == "edgp.schema.index.v1.schema.json"
    validation_report = _run_cli(
        [
            "validate",
            "--path",
            "tests/fixtures/validation-failure-missing-edge-count.json",
        ]
    )
    assert validation_report["ok"] is True
    assert validation_report["contract"] == "edgp.validation.report.v1"
    assert validation_report["schemaFile"] == "edgp.validation.report.v1.schema.json"
    with tempfile.TemporaryDirectory() as temp_dir:
        html_path = Path(temp_dir) / "schema-index.html"
        completed_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                str(SCHEMA_INDEX_PATH),
                "--output",
                str(html_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert Path(completed_report.stdout.strip()) == html_path
        html = html_path.read_text(encoding="utf-8")
        assert 'data-testid="schema-index-groups-panel"' in html
        assert 'data-testid="schema-index-schemas-panel"' in html
        assert "edgp.graph.snapshot.v1" in html
        assert "edgp.report.bundle.v1" in html


def _assert_submission_plan_index() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "submission-plan-index.json"
        index = _run_cli(
            [
                "submission-plan-index",
                "--input",
                "tests/fixtures/export-batch-submission-plan.json",
                "--input",
                "tests/fixtures/report-bundle-submission-plan.json",
                "--output",
                str(output_path),
            ]
        )
        assert index["schema"] == "edgp.submission.plan.index.v1"
        assert index["ok"] is True
        assert index["summary"]["plans"] == 2
        assert index["summary"]["artifacts"] == 4
        assert index["summary"]["targets"] == ["dependency-track", "workbench"]
        assert json.loads(output_path.read_text(encoding="utf-8")) == index
        validation = _run_cli(["validate", "--path", str(output_path)])
        assert validation["ok"] is True
        assert validation["contract"] == "edgp.submission.plan.index.v1"
        html_path = Path(temp_dir) / "submission-plan-index.html"
        completed_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                str(output_path),
                "--output",
                str(html_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert Path(completed_report.stdout.strip()) == html_path
        html = html_path.read_text(encoding="utf-8")
        assert 'data-testid="submission-plan-index-panel"' in html
        assert "dependency-track" in html
        assert "workbench" in html

        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "submission-plan-index",
                "--input",
                "tests/fixtures/export-batch-submission-plan.json",
                "--input",
                "tests/fixtures/report-bundle-submission-plan.json",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.startswith(
            "OK plans=2 failedPlans=0 artifacts=4 bytes=7517 failures=0 "
        )


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
    assert filtered_index["exampleCount"] == 2
    assert {example["id"] for example in filtered_index["examples"]} == {
        "graph-missing-edge-count",
        "json-schema-unsupported",
    }
    filtered_index = _run_cli(
        ["failure-examples", "--contract", "edgp.graph.snapshot.v1"]
    )
    assert filtered_index["exampleCount"] == 1
    assert filtered_index["examples"][0]["id"] == "graph-missing-edge-count"
    filtered_index = _run_cli(
        ["failure-examples", "--contract", "edgp.unknown.report.v1"]
    )
    assert filtered_index["exampleCount"] == 1
    assert filtered_index["examples"][0]["id"] == "json-schema-unsupported"
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
    assert filter_summary["exampleCount"] == 28
    assert "manifest-invalid" in filter_summary["ids"]
    assert "json-schema-unsupported" in filter_summary["ids"]
    assert "archive-missing" in filter_summary["ids"]
    assert "edgp.unknown.report.v1" in filter_summary["contracts"]
    assert "edgp.report.bundle.v1" in filter_summary["contracts"]
    assert "edgp.report.bundle.archive.v1" in filter_summary["contracts"]
    assert "report-bundle-archive" in filter_summary["targetTypes"]
    assert "bundle.manifestInvalid" in filter_summary["validationFailureCodes"]
    assert "bundleArchive.archiveMissing" in filter_summary["validationFailureCodes"]
    assert "schemaUnsupported" in filter_summary["validationFailureCodes"]
    assert "manifestInvalid" in filter_summary["verificationFailureCodes"]
    assert "archiveMissing" in filter_summary["verificationFailureCodes"]
    validation = _run_cli(
        ["validate", "--path", "docs/validation-failure-example-filters.json"]
    )
    assert validation["ok"] is True
    assert validation["contract"] == "edgp.validation.failure.example.filters.v1"
    with tempfile.TemporaryDirectory() as temp_dir:
        index_html_path = Path(temp_dir) / "failure-examples.html"
        completed_index_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                "docs/validation-failure-example-index.json",
                "--output",
                str(index_html_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert Path(completed_index_report.stdout.strip()) == index_html_path
        index_html = index_html_path.read_text(encoding="utf-8")
        assert 'data-testid="failure-example-index-panel"' in index_html
        assert "graph-missing-edge-count" in index_html

        filters_html_path = Path(temp_dir) / "failure-example-filters.html"
        completed_filters_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                "docs/validation-failure-example-filters.json",
                "--output",
                str(filters_html_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert Path(completed_filters_report.stdout.strip()) == filters_html_path
        filters_html = filters_html_path.read_text(encoding="utf-8")
        assert 'data-testid="failure-example-filters-panel"' in filters_html
        assert "bundleArchive.archiveMissing" in filters_html
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
        "OK examples=28 schema=edgp.validation.failure.example.index.v1"
    )
    assert "json-schema-unsupported targetType=json-file" in completed.stdout
    assert "failureCodes=schemaUnsupported" in completed.stdout
    assert "manifest-invalid targetType=report-bundle" in completed.stdout
    assert "verifierCodes=manifestInvalid" in completed.stdout
    assert "archive-missing targetType=report-bundle-archive" in completed.stdout
    assert "verifierCodes=archiveMissing" in completed.stdout
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
        "OK examples=2 schema=edgp.validation.failure.example.index.v1"
    )
    assert "graph-missing-edge-count targetType=json-file" in completed.stdout
    assert "json-schema-unsupported targetType=json-file" in completed.stdout
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "failure-examples",
            "--target-type",
            "report-bundle-archive",
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
    assert "archive-missing targetType=report-bundle-archive" in completed.stdout
    assert "verifierCodes=archiveMissing" in completed.stdout
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
        "OK examples=2 schema=edgp.validation.failure.example.filters.v1"
    )
    assert "ids=graph-missing-edge-count,json-schema-unsupported" in completed.stdout
    assert "contracts=edgp.graph.snapshot.v1,edgp.unknown.report.v1" in completed.stdout
    assert "validationFailureCodes=requiredMissing,schemaUnsupported" in completed.stdout
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


def _assert_report_schema_docs_local_links() -> None:
    for document_path in REPORT_SCHEMA_DOC_PATHS:
        _assert_markdown_local_path_links(document_path, document_path.parent)


def _assert_architecture_doc_local_links() -> None:
    _assert_markdown_local_path_links(
        ARCHITECTURE_DOC_PATH,
        ARCHITECTURE_DOC_PATH.parent,
        require_links=False,
    )


def _assert_architecture_doc_headings() -> None:
    lines = ARCHITECTURE_DOC_PATH.read_text(encoding="utf-8").splitlines()
    title_anchors = _markdown_heading_anchors(lines, level="# ")
    section_anchors = _markdown_heading_anchors(lines, level="## ")
    subsection_anchors = _markdown_heading_anchors(lines, level="### ")

    assert title_anchors == {
        "architecture-and-traversal-of-massive-scale-dependency-graphs"
    }
    assert {
        "the-imperative-of-massive-scale-graph-architectures",
        "memory-optimization-and-sparse-matrix-representations",
        "algorithmic-resolution-of-software-dependency-graphs",
        "conclusion",
    } <= section_anchors
    assert {
        "compressed-sparse-row-and-compressed-sparse-column-formats",
        "pubgrub-and-conflict-driven-clause-learning",
    } <= subsection_anchors


def _assert_architecture_doc_quick_links() -> None:
    lines = ARCHITECTURE_DOC_PATH.read_text(encoding="utf-8").splitlines()
    linked_anchors = _markdown_link_anchors(lines)
    heading_anchors = _architecture_doc_heading_anchors()

    assert {
        "memory-optimization-and-sparse-matrix-representations",
        "algorithmic-resolution-of-software-dependency-graphs",
        "securing-the-open-source-supply-chain-at-scale",
    } <= set(linked_anchors)
    for anchor in linked_anchors:
        assert anchor in heading_anchors


def _assert_architecture_doc_extraction_artifacts() -> None:
    text = ARCHITECTURE_DOC_PATH.read_text(encoding="utf-8")
    for marker in ("span_", "start_span", "end_span", "\ufffc"):
        assert marker not in text


def _assert_architecture_doc_markdown_lists() -> None:
    text = ARCHITECTURE_DOC_PATH.read_text(encoding="utf-8")

    assert "\n•" not in text
    assert "- Answer Set Programming (ASP):" in text
    assert "- Minimal Version Selection (MVS):" in text
    assert "- Backtracking & Deduplication:" in text


def _assert_validation_failure_examples_quick_links() -> None:
    lines = VALIDATION_FAILURE_EXAMPLES_DOC_PATH.read_text(encoding="utf-8").splitlines()
    heading_anchors = _validation_failure_example_heading_anchors()
    linked_anchors = _markdown_link_anchors(lines)

    assert linked_anchors
    for anchor in linked_anchors:
        assert anchor in heading_anchors


def _assert_validation_failure_examples_local_links() -> None:
    _assert_markdown_local_path_links(
        VALIDATION_FAILURE_EXAMPLES_DOC_PATH,
        VALIDATION_FAILURE_EXAMPLES_DOC_PATH.parent,
    )


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


def _assert_readme_architecture_research_link() -> None:
    readme_paths = set(
        _markdown_path_links(README_PATH.read_text(encoding="utf-8").splitlines())
    )
    architecture_path = (
        "docs/Architecture%20and%20Traversal%20of%20Massive-Scale%20"
        "Dependency%20Graphs.md"
    )

    assert architecture_path in readme_paths
    assert (REPO_ROOT / unquote(architecture_path)).exists()


def _assert_readme_architecture_research_anchors() -> None:
    linked_anchors = _markdown_links_to_anchor(
        README_PATH.read_text(encoding="utf-8").splitlines(),
        "docs/Architecture%20and%20Traversal%20of%20Massive-Scale%20"
        "Dependency%20Graphs.md#",
    )
    heading_anchors = _architecture_doc_heading_anchors()

    assert {
        "memory-optimization-and-sparse-matrix-representations",
        "algorithmic-resolution-of-software-dependency-graphs",
    } <= set(linked_anchors)
    for anchor in linked_anchors:
        assert anchor in heading_anchors


def _assert_readme_local_documentation_links() -> None:
    _assert_markdown_local_path_links(README_PATH, REPO_ROOT)


def _assert_markdown_local_path_links(
    document_path: Path,
    base_path: Path,
    *,
    require_links: bool = True,
) -> None:
    linked_paths = set(
        _markdown_path_links(document_path.read_text(encoding="utf-8").splitlines())
    )

    if require_links:
        assert linked_paths
    for path in linked_paths:
        assert (base_path / unquote(path)).exists()


def _validation_failure_example_heading_anchors() -> set[str]:
    lines = VALIDATION_FAILURE_EXAMPLES_DOC_PATH.read_text(encoding="utf-8").splitlines()
    return _markdown_heading_anchors(lines)


def _architecture_doc_heading_anchors() -> set[str]:
    lines = ARCHITECTURE_DOC_PATH.read_text(encoding="utf-8").splitlines()
    return (
        _markdown_heading_anchors(lines, level="# ")
        | _markdown_heading_anchors(lines, level="## ")
        | _markdown_heading_anchors(lines, level="### ")
    )


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
    triage_schema = schema["properties"]["triageSummary"]
    required_triage_keys = set(triage_schema["required"])
    allowed_triage_keys = set(triage_schema["properties"])

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

    triage_summary = manifest.get("triageSummary")
    if triage_summary is not None:
        assert isinstance(triage_summary, dict)
        assert required_triage_keys <= set(triage_summary)
        assert set(triage_summary) <= allowed_triage_keys
        assert isinstance(triage_summary["href"], str) and triage_summary["href"]
        assert _is_sha256(triage_summary["htmlSha256"])
        assert triage_summary["schema"] == "edgp.triage.summary.v1"
        assert isinstance(triage_summary["source"], str) and triage_summary["source"]
        assert _is_sha256(triage_summary["sourceSha256"])
        assert isinstance(triage_summary["summary"], dict)
        assert isinstance(triage_summary["title"], str) and triage_summary["title"]
        if bundle_dir is not None:
            html_path = bundle_dir / triage_summary["href"]
            source_path = _resolve_manifest_source(bundle_dir, triage_summary["source"])
            assert triage_summary["htmlSha256"] == _sha256_path(html_path)
            assert triage_summary["sourceSha256"] == _sha256_path(source_path)

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
    *,
    archive_path: str = "",
) -> list[dict[str, Any]]:
    normalized = []
    if not isinstance(failures, list):
        return normalized
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        item = dict(failure)
        path = item.get("path")
        if isinstance(path, str):
            if archive_path:
                path = path.replace(archive_path, "<archive>", 1)
            if bundle_dir:
                path = path.replace(bundle_dir, "<bundle-dir>", 1)
            item["path"] = path
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

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "query-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "query-bundle",
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
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "query-report"
        assert manifest["reports"][0]["href"] == "001-query-report.html"
        assert manifest["reports"][0]["schema"] == "edgp.query.report.v1"
        report = json.loads(
            (output_dir / "query-report.json").read_text(encoding="utf-8")
        )
        assert report["summary"] == {
            "pathFound": True,
            "resultCount": 3,
            "resultKind": "path",
        }
        assert 'data-testid="query-result-panel"' in (
            output_dir / "001-query-report.html"
        ).read_text(encoding="utf-8")


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
                "--triage-summary",
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


def _assert_export_batch() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "export-batch"
        manifest = _run_cli(
            [
                "export-batch",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(output_dir),
                "--format",
                "cypher",
                "--format",
                "cyclonedx",
            ]
        )
        assert manifest["schema"] == "edgp.export.batch.v1"
        assert manifest["source"]["root"] == "app==1.0.0"
        assert manifest["source"]["ecosystem"] == "npm"
        assert manifest["summary"]["formats"] == ["cypher", "cyclonedx"]
        assert json.loads((output_dir / "manifest.json").read_text()) == manifest
        exports = {entry["format"]: entry for entry in manifest["exports"]}
        assert set(exports) == {"cypher", "cyclonedx"}
        assert "DEPENDS_ON" in (output_dir / exports["cypher"]["path"]).read_text(
            encoding="utf-8"
        )
        cyclonedx = json.loads(
            (output_dir / exports["cyclonedx"]["path"]).read_text(encoding="utf-8")
        )
        assert cyclonedx["bomFormat"] == "CycloneDX"
        for entry in manifest["exports"]:
            data = (output_dir / entry["path"]).read_bytes()
            assert entry["bytes"] == len(data)
            assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        validation = _run_cli(["validate", "--path", str(output_dir / "manifest.json")])
        assert validation["ok"] is True
        assert validation["contract"] == "edgp.export.batch.v1"
        manifest_html_path = Path(temp_dir) / "export-batch.html"
        completed_manifest_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                str(output_dir / "manifest.json"),
                "--output",
                str(manifest_html_path),
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert Path(completed_manifest_report.stdout.strip()) == manifest_html_path
        manifest_html = manifest_html_path.read_text(encoding="utf-8")
        assert 'data-testid="export-batch-artifacts-panel"' in manifest_html
        assert "graph.cypher" in manifest_html
        verification = _run_cli(["verify-export-batch", "--path", str(output_dir)])
        assert verification["schema"] == "edgp.export.batch.verification.v1"
        assert verification["ok"] is True
        assert verification["summary"]["exports"] == 2
        verification_path = Path(temp_dir) / "export-batch-verification.json"
        verification_path.write_text(json.dumps(verification), encoding="utf-8")
        verification_html_path = Path(temp_dir) / "export-batch-verification.html"
        completed_verification_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                str(verification_path),
                "--output",
                str(verification_html_path),
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert (
            Path(completed_verification_report.stdout.strip())
            == verification_html_path
        )
        verification_html = verification_html_path.read_text(encoding="utf-8")
        assert 'data-testid="export-batch-verification-panel"' in verification_html
        assert "manifest.json" in verification_html
        directory_validation = _run_cli(["validate", "--path", str(output_dir)])
        assert directory_validation["ok"] is True
        assert directory_validation["targetType"] == "export-batch"
        assert directory_validation["exportBatchVerification"]["ok"] is True
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "verify-export-batch",
                "--path",
                str(output_dir),
                "--format",
                "text",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.startswith("OK exports=2")
        submission_plan_path = Path(temp_dir) / "submission-plan.json"
        submission_plan = _run_cli(
            [
                "plan-export-batch-submission",
                "--path",
                str(output_dir),
                "--target",
                "neo4j",
                "--endpoint",
                "https://neo4j.example/import",
                "--output",
                str(submission_plan_path),
            ]
        )
        assert submission_plan["schema"] == "edgp.export.batch.submission_plan.v1"
        assert submission_plan["ok"] is True
        assert submission_plan["summary"]["artifacts"] == 1
        assert submission_plan["artifacts"][0]["format"] == "cypher"
        submission_plan_validation = _run_cli(
            ["validate", "--path", str(submission_plan_path)]
        )
        assert submission_plan_validation["ok"] is True
        assert (
            submission_plan_validation["contract"]
            == "edgp.export.batch.submission_plan.v1"
        )
        text_plan = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "plan-export-batch-submission",
                "--path",
                str(output_dir),
                "--target",
                "generic",
                "--endpoint",
                "https://collector.example/upload",
                "--format",
                "text",
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert text_plan.stdout.startswith("OK target=generic artifacts=2")
        archive_path = Path(temp_dir) / "export-batch.tar.gz"
        archive_report = _run_cli(
            [
                "archive-export-batch",
                "--path",
                str(output_dir),
                "--output",
                str(archive_path),
            ]
        )
        assert archive_report["schema"] == "edgp.export.batch.archive.v1"
        assert archive_report["ok"] is True
        assert archive_report["summary"]["files"] == 3
        archive_report_path = Path(temp_dir) / "export-batch-archive.json"
        archive_report_path.write_text(json.dumps(archive_report), encoding="utf-8")
        archive_html_path = Path(temp_dir) / "export-batch-archive.html"
        completed_archive_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                str(archive_report_path),
                "--output",
                str(archive_html_path),
            ],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert Path(completed_archive_report.stdout.strip()) == archive_html_path
        archive_html = archive_html_path.read_text(encoding="utf-8")
        assert 'data-testid="export-batch-archive-panel"' in archive_html
        assert str(archive_path) in archive_html
        archive_verification = _run_cli(
            ["verify-export-batch-archive", "--path", str(archive_path)]
        )
        assert archive_verification["schema"] == "edgp.export.batch.archive.v1"
        assert archive_verification["ok"] is True
        archive_validation = _run_cli(["validate", "--path", str(archive_path)])
        assert archive_validation["targetType"] == "export-batch-archive"
        assert archive_validation["ok"] is True
        archive_submission_plan = _run_cli(
            [
                "plan-export-batch-submission",
                "--path",
                str(archive_path),
                "--target",
                "dependency-track",
                "--endpoint",
                "https://dependency-track.example/api/v1/bom",
            ]
        )
        assert archive_submission_plan["ok"] is True
        assert archive_submission_plan["source"]["inputType"] == "archive"
        assert archive_submission_plan["artifacts"][0]["format"] == "cyclonedx"
        (output_dir / exports["cypher"]["path"]).write_text("tampered\n", encoding="utf-8")
        failed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "verify-export-batch",
                "--path",
                str(output_dir),
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert failed.returncode == 1
        tampered = json.loads(failed.stdout)
        assert tampered["ok"] is False
        assert {
            failure["code"] for failure in tampered["failures"]
        } == {"exportBytesMismatch", "exportDigestMismatch"}


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
                "--triage-summary",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_dir / "index.html")
        manifest = json.loads(
            (output_dir / "manifest.json").read_text(encoding="utf-8")
        )
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


def _assert_albs_build_snapshot() -> None:
    payload = _run_cli(
        [
            "albs-build",
            "--path",
            "tests/fixtures/albs-build.json",
            "--format",
            "json",
        ]
    )
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "albs"
    assert payload["root"] == "albs-build:17812"
    assert payload["stats"] == {"edges": 20, "nodes": 15}
    assert {
        "source": "albs-task:188080:ppc64le",
        "target": "rpm:3237086:nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm",
        "relationshipType": 25,
    } in payload["edges"]


def _assert_albs_build_bundle() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "albs-build-bundle"
        impact_node = "rpm:3237086:nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "albs-build-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
                "--impact-node",
                impact_node,
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "albs-build"
        assert manifest["bundle"]["command"].startswith("edgp albs-build-bundle ")
        assert manifest["reports"][0]["href"] == "001-albs-build-graph.html"
        assert manifest["reports"][1]["href"] == "002-albs-artifact-inventory.html"
        assert manifest["reports"][2]["href"] == "003-albs-build-timing.html"
        assert (
            manifest["reports"][3]["href"]
            == "004-impact-rpm-3237086-nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm.html"
        )
        graph_html = (output_dir / "001-albs-build-graph.html").read_text(
            encoding="utf-8"
        )
        inventory = json.loads(
            (output_dir / "albs-artifact-inventory.json").read_text(encoding="utf-8")
        )
        timing = json.loads(
            (output_dir / "albs-build-timing.json").read_text(encoding="utf-8")
        )
        inventory_html = (output_dir / "002-albs-artifact-inventory.html").read_text(
            encoding="utf-8"
        )
        timing_html = (output_dir / "003-albs-build-timing.html").read_text(
            encoding="utf-8"
        )
        assert "25 - ALBS Produces Artifact" in graph_html
        assert inventory["schema"] == "edgp.albs.artifact_inventory.v1"
        assert inventory["summary"]["artifacts"] == 4
        assert "nginx-core-1.20.1-16.el9_4.1.ppc64le.rpm" in inventory_html
        assert timing["schema"] == "edgp.albs.build_timing.v1"
        assert timing["summary"]["criticalBuildTaskWallSeconds"] == 371.070048
        assert "EDGP ALBS Build Timing" in timing_html


def _assert_public_vertical_reports() -> None:
    inventory_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "albs-artifact-inventory",
            "--path",
            "tests/fixtures/albs-build.json",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert inventory_text.startswith("OK schema=edgp.albs.artifact_inventory.v1")
    assert "artifacts=4" in inventory_text
    assert "buildTasks=2" in inventory_text
    timing_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "albs-build-timing",
            "--path",
            "tests/fixtures/albs-build.json",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert timing_text.startswith("OK schema=edgp.albs.build_timing.v1")
    assert "buildTasks=2" in timing_text
    assert "criticalBuildTaskWallSeconds=371.070" in timing_text

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "albs-artifact-inventory-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "albs-artifact-inventory-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "albs-artifact-inventory"
        assert manifest["reports"][0]["href"] == "001-albs-artifact-inventory.html"
        assert manifest["reports"][0]["schema"] == "edgp.albs.artifact_inventory.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        inventory = json.loads(
            (output_dir / "albs-artifact-inventory.json").read_text(encoding="utf-8")
        )
        assert inventory["summary"]["artifacts"] == 4
        inventory_html = (output_dir / "001-albs-artifact-inventory.html").read_text(
            encoding="utf-8"
        )
        assert 'data-testid="albs-artifact-table-panel"' in inventory_html

        text_output_dir = Path(temp_dir) / "albs-artifact-inventory-bundle-text"
        completed_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "albs-artifact-inventory-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
                "--output-dir",
                str(text_output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        inventory_bundle_text = completed_text.stdout.strip()
        assert inventory_bundle_text.startswith("BUNDLE ")
        assert "sourceKind=albs-artifact-inventory" in inventory_bundle_text
        assert "reports=1" in inventory_bundle_text
        assert "triageStatus=pass" in inventory_bundle_text

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "albs-build-timing-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "albs-build-timing-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "albs-build-timing"
        assert manifest["reports"][0]["href"] == "001-albs-build-timing.html"
        assert manifest["reports"][0]["schema"] == "edgp.albs.build_timing.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        timing = json.loads(
            (output_dir / "albs-build-timing.json").read_text(encoding="utf-8")
        )
        assert timing["summary"]["criticalBuildTaskWallSeconds"] == 371.070048
        timing_html = (output_dir / "001-albs-build-timing.html").read_text(
            encoding="utf-8"
        )
        assert 'data-testid="albs-artifact-timing-panel"' in timing_html

        text_output_dir = Path(temp_dir) / "albs-build-timing-bundle-text"
        completed_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "albs-build-timing-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
                "--output-dir",
                str(text_output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        timing_bundle_text = completed_text.stdout.strip()
        assert timing_bundle_text.startswith("BUNDLE ")
        assert "sourceKind=albs-build-timing" in timing_bundle_text
        assert "reports=1" in timing_bundle_text
        assert "triageStatus=pass" in timing_bundle_text

    albs_build_url = (REPO_ROOT / "tests" / "fixtures" / "albs-build.json").as_uri()
    albs_updated_url = (
        REPO_ROOT / "tests" / "fixtures" / "albs-build-updated.json"
    ).as_uri()
    url_inventory = _run_cli(["albs-artifact-inventory", "--url", albs_build_url])
    assert url_inventory["schema"] == "edgp.albs.artifact_inventory.v1"
    assert url_inventory["summary"]["artifacts"] == 4
    url_query = _run_cli(
        [
            "query",
            "--source",
            "albs-build",
            "--albs-url",
            albs_build_url,
            "--operation",
            "most-depended-upon",
        ]
    )
    assert url_query["operation"] == "most-depended-upon"
    assert url_query["result"][0] == {
        "package": "albs-release:7396",
        "dependents": 6,
    }
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "albs-query-url-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "query-bundle",
                "--source",
                "albs-build",
                "--albs-url",
                albs_build_url,
                "--operation",
                "most-depended-upon",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "query-report"
        assert manifest["reports"][0]["schema"] == "edgp.query.report.v1"
    url_release = _run_cli(
        [
            "albs-release-completeness",
            "--url",
            albs_build_url,
            "--url",
            albs_updated_url,
        ]
    )
    assert url_release["schema"] == "edgp.albs.release_completeness.v1"
    assert url_release["summary"]["builds"] == 2

    diff = _run_cli(
        [
            "albs-build-diff",
            "--left-path",
            "tests/fixtures/albs-build.json",
            "--right-path",
            "tests/fixtures/albs-build-updated.json",
        ]
    )
    assert diff["schema"] == "edgp.albs.build_diff.v1"
    assert diff["summary"]["changedArtifacts"] == 3
    diff_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "albs-build-diff",
            "--left-path",
            "tests/fixtures/albs-build.json",
            "--right-path",
            "tests/fixtures/albs-build-updated.json",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert diff_text.startswith("ALBS_BUILD_DIFF ")
    assert "changedArtifacts=3" in diff_text
    assert "wallSecondsDelta=70.000" in diff_text

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "albs-build-diff-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "albs-build-diff-bundle",
                "--left-path",
                "tests/fixtures/albs-build.json",
                "--right-path",
                "tests/fixtures/albs-build-updated.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "albs-build-diff"
        assert manifest["reports"][0]["href"] == "001-albs-build-diff.html"
        assert manifest["reports"][0]["schema"] == "edgp.albs.build_diff.v1"
        assert manifest["triageSummary"]["href"] == "triage-summary.html"
        diff_report = json.loads(
            (output_dir / "albs-build-diff.json").read_text(encoding="utf-8")
        )
        assert diff_report["summary"]["changedArtifacts"] == 3
        diff_html = (output_dir / "001-albs-build-diff.html").read_text(
            encoding="utf-8"
        )
        assert "EDGP ALBS Build Diff" in diff_html

        text_output_dir = Path(temp_dir) / "albs-build-diff-bundle-text"
        completed_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "albs-build-diff-bundle",
                "--left-path",
                "tests/fixtures/albs-build.json",
                "--right-path",
                "tests/fixtures/albs-build-updated.json",
                "--output-dir",
                str(text_output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        diff_bundle_text = completed_text.stdout.strip()
        assert diff_bundle_text.startswith("BUNDLE ")
        assert "sourceKind=albs-build-diff" in diff_bundle_text
        assert "reports=1" in diff_bundle_text
        assert "triageStatus=pass" in diff_bundle_text

    log = _run_cli(
        ["albs-log-intelligence", "--path", "tests/fixtures/albs-build-updated.json"]
    )
    assert log["schema"] == "edgp.albs.log_intelligence.v1"
    assert log["signalCounts"]["missing"] == 1
    completed_log_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "albs-log-intelligence",
            "--path",
            "tests/fixtures/albs-build-updated.json",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    log_text = completed_log_text.stdout.strip()
    assert log_text.startswith(
        "ALBS_LOG_INTELLIGENCE schema=edgp.albs.log_intelligence.v1"
    )
    assert "logArtifacts=1" in log_text
    assert "signals=4" in log_text
    assert "signalCounts=error:1,failed:1,missing:1,warning:1" in log_text
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "albs-log-intelligence-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "albs-log-intelligence-bundle",
                "--path",
                "tests/fixtures/albs-build-updated.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "albs-log-intelligence"
        assert manifest["reports"][0]["href"] == "001-albs-log-intelligence.html"
        assert manifest["reports"][0]["schema"] == "edgp.albs.log_intelligence.v1"
        assert manifest["triageSummary"]["href"] == "triage-summary.html"
        log_report = json.loads(
            (output_dir / "albs-log-intelligence.json").read_text(encoding="utf-8")
        )
        assert log_report["signalCounts"]["missing"] == 1
        log_html = (output_dir / "001-albs-log-intelligence.html").read_text(
            encoding="utf-8"
        )
        assert 'data-testid="albs-log-intelligence-panel"' in log_html
        text_output_dir = Path(temp_dir) / "albs-log-intelligence-bundle-text"
        completed_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "albs-log-intelligence-bundle",
                "--path",
                "tests/fixtures/albs-build-updated.json",
                "--output-dir",
                str(text_output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        log_bundle_text = completed_text.stdout.strip()
        assert log_bundle_text.startswith("BUNDLE ")
        assert "sourceKind=albs-log-intelligence" in log_bundle_text
        assert "reports=1" in log_bundle_text
        assert "triageStatus=pass" in log_bundle_text

    completeness = _run_cli(
        [
            "albs-release-completeness",
            "--path",
            "tests/fixtures/albs-build.json",
            "--path",
            "tests/fixtures/albs-build-updated.json",
        ]
    )
    assert completeness["schema"] == "edgp.albs.release_completeness.v1"
    assert completeness["summary"]["builds"] == 2
    completed_completeness_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "albs-release-completeness",
            "--path",
            "tests/fixtures/albs-build.json",
            "--path",
            "tests/fixtures/albs-build-updated.json",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    completeness_text = completed_completeness_text.stdout.strip()
    assert completeness_text.startswith(
        "ALBS_RELEASE_COMPLETENESS schema=edgp.albs.release_completeness.v1"
    )
    assert "builds=2" in completeness_text
    assert "missingBuildArchitectures=6" in completeness_text
    assert "firstMissingArchitectures=aarch64,s390x,i686" in completeness_text
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "albs-release-completeness-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "albs-release-completeness-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
                "--path",
                "tests/fixtures/albs-build-updated.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "albs-release-completeness"
        assert manifest["reports"][0]["href"] == "001-albs-release-completeness.html"
        assert manifest["reports"][0]["schema"] == "edgp.albs.release_completeness.v1"
        assert manifest["triageSummary"]["href"] == "triage-summary.html"
        completeness_report = json.loads(
            (output_dir / "albs-release-completeness.json").read_text(encoding="utf-8")
        )
        assert completeness_report["summary"]["builds"] == 2
        completeness_html = (
            output_dir / "001-albs-release-completeness.html"
        ).read_text(encoding="utf-8")
        assert 'data-testid="albs-release-completeness-panel"' in completeness_html
        text_output_dir = Path(temp_dir) / "albs-release-completeness-bundle-text"
        completed_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "albs-release-completeness-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
                "--path",
                "tests/fixtures/albs-build-updated.json",
                "--output-dir",
                str(text_output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        completeness_bundle_text = completed_text.stdout.strip()
        assert completeness_bundle_text.startswith("BUNDLE ")
        assert "sourceKind=albs-release-completeness" in completeness_bundle_text
        assert "reports=1" in completeness_bundle_text
        assert "triageStatus=pass" in completeness_bundle_text

    rpm_repo = _run_cli(
        [
            "rpm-repo",
            "--source",
            "tests/fixtures/repodata/repomd.xml",
            "--format",
            "json",
        ]
    )
    assert rpm_repo["schema"] == "edgp.graph.snapshot.v1"
    assert rpm_repo["stats"] == {"edges": 21, "nodes": 20}

    rpm_repo_summary = _run_cli(
        ["rpm-repo-summary", "--source", "tests/fixtures/repodata/repomd.xml"]
    )
    assert rpm_repo_summary["schema"] == "edgp.rpm.repository_summary.v1"
    assert rpm_repo_summary["summary"]["packages"] == 2
    rpm_repo_summary_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "rpm-repo-summary",
            "--source",
            "tests/fixtures/repodata/repomd.xml",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert rpm_repo_summary_text.startswith("OK schema=edgp.rpm.repository_summary.v1")
    assert "packages=2" in rpm_repo_summary_text
    assert "unresolvedRequirements=18" in rpm_repo_summary_text

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "rpm-repo-summary-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "rpm-repo-summary-bundle",
                "--source",
                "tests/fixtures/repodata/repomd.xml",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "rpm-repository-summary"
        assert manifest["reports"][0]["href"] == "001-rpm-repository-summary.html"
        assert manifest["reports"][0]["schema"] == "edgp.rpm.repository_summary.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        summary = json.loads(
            (output_dir / "rpm-repository-summary.json").read_text(encoding="utf-8")
        )
        assert summary["schema"] == "edgp.rpm.repository_summary.v1"
        assert summary["summary"]["packages"] == 2
        assert 'data-testid="rpm-repository-architectures-panel"' in (
            output_dir / "001-rpm-repository-summary.html"
        ).read_text(encoding="utf-8")

        text_output_dir = Path(temp_dir) / "rpm-repo-summary-bundle-text"
        completed_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "rpm-repo-summary-bundle",
                "--source",
                "tests/fixtures/repodata/repomd.xml",
                "--output-dir",
                str(text_output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        rpm_repo_summary_bundle_text = completed_text.stdout.strip()
        assert rpm_repo_summary_bundle_text.startswith("BUNDLE ")
        assert "sourceKind=rpm-repository-summary" in rpm_repo_summary_bundle_text
        assert "reports=1" in rpm_repo_summary_bundle_text
        assert "triageStatus=pass" in rpm_repo_summary_bundle_text

    rpm_repo_diff = _run_cli(
        [
            "rpm-repo-diff",
            "--left-primary",
            "tests/fixtures/rpm-primary.xml",
            "--right-primary",
            "tests/fixtures/rpm-primary-updated.xml",
        ]
    )
    assert rpm_repo_diff["schema"] == "edgp.rpm.repository_diff.v1"
    assert rpm_repo_diff["summary"]["changedPackages"] == 1
    rpm_repo_diff_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "rpm-repo-diff",
            "--left-primary",
            "tests/fixtures/rpm-primary.xml",
            "--right-primary",
            "tests/fixtures/rpm-primary-updated.xml",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert rpm_repo_diff_text.startswith("RPM_REPO_DIFF ")
    assert "changedPackages=1" in rpm_repo_diff_text
    assert "firstChanged=nginx" in rpm_repo_diff_text

    rpm_repo_nginx_node = "nginx==1.20.1-28.el9_8.2.alma.1.x86_64"
    rpm_repo_nginx_core_node = "nginx-core==1.20.1-28.el9_8.2.alma.1.x86_64"
    rpm_repo_query = _run_cli(
        [
            "query",
            "--source",
            "rpm-repo",
            "--path",
            "tests/fixtures/repodata/repomd.xml",
            "--operation",
            "dependencies",
            "--node",
            "nginx",
        ]
    )
    assert rpm_repo_query["node"] == rpm_repo_nginx_node
    assert rpm_repo_query["result"][0] == rpm_repo_nginx_core_node
    assert "rpm-capability:nginx-filesystem" in rpm_repo_query["result"]
    assert "rpm-capability:systemd" in rpm_repo_query["result"]
    assert len(rpm_repo_query["result"]) == 7

    rpm_repo_impact = _run_cli(
        [
            "impact",
            "--source",
            "rpm-repo",
            "--path",
            "tests/fixtures/repodata/repomd.xml",
            "--node",
            "nginx-core",
        ]
    )
    assert rpm_repo_impact["schema"] == "edgp.impact.report.v1"
    assert rpm_repo_impact["node"] == rpm_repo_nginx_core_node
    rpm_repo_impact_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "impact",
            "--source",
            "rpm-repo",
            "--path",
            "tests/fixtures/repodata/repomd.xml",
            "--node",
            "nginx-core",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert rpm_repo_impact_text.startswith("IMPACT_REPORT ")
    assert "schema=edgp.impact.report.v1" in rpm_repo_impact_text
    assert f"node={rpm_repo_nginx_core_node}" in rpm_repo_impact_text
    assert "directDependents=2" in rpm_repo_impact_text
    assert f"firstDependent={rpm_repo_nginx_node}" in rpm_repo_impact_text

    rpm_repo_advisory = _run_cli(
        [
            "advisory",
            "--source",
            "rpm-repo",
            "--path",
            "tests/fixtures/repodata/repomd.xml",
            "--advisories",
            "tests/fixtures/rpm-repo-advisories.json",
            "--ecosystem",
            "rpm",
        ]
    )
    assert rpm_repo_advisory["schema"] == "edgp.advisory.report.v1"
    assert rpm_repo_advisory["summary"]["findings"] == 1
    rpm_repo_public_advisory = _run_cli(
        [
            "advisory",
            "--source",
            "rpm-repo",
            "--path",
            "tests/fixtures/repodata/repomd.xml",
            "--public-advisory-feed-url",
            (
                REPO_ROOT / "tests" / "fixtures" / "public-osv-ranges.json"
            ).as_uri(),
            "--ecosystem",
            "rpm",
        ]
    )
    assert rpm_repo_public_advisory["schema"] == "edgp.advisory.report.v1"
    assert rpm_repo_public_advisory["summary"]["findings"] == 1
    assert rpm_repo_public_advisory["findings"][0]["advisory"]["ranges"][0][
        "fixed"
    ] == "1.20.1-28.el9_8.2.alma.2"
    completed_advisory_gate = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "advisory",
            "--source",
            "rpm-repo",
            "--path",
            "tests/fixtures/repodata/repomd.xml",
            "--public-advisory-feed",
            "tests/fixtures/public-osv-ranges.json",
            "--ecosystem",
            "rpm",
            "--fail-on-findings",
            "--fail-min-severity",
            "high",
        ],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed_advisory_gate.returncode == 2
    gated_advisory = json.loads(completed_advisory_gate.stdout)
    assert gated_advisory["schema"] == "edgp.advisory.report.v1"
    assert gated_advisory["summary"]["findings"] == 1
    completed_advisory_gate_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "advisory",
            "--source",
            "rpm-repo",
            "--path",
            "tests/fixtures/repodata/repomd.xml",
            "--public-advisory-feed",
            "tests/fixtures/public-osv-ranges.json",
            "--ecosystem",
            "rpm",
            "--format",
            "text",
            "--fail-on-findings",
            "--fail-min-severity",
            "high",
        ],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed_advisory_gate_text.returncode == 2
    advisory_gate_text = completed_advisory_gate_text.stdout.strip()
    assert advisory_gate_text.startswith("ADVISORY_REPORT ")
    assert "schema=edgp.advisory.report.v1" in advisory_gate_text
    assert "findings=1" in advisory_gate_text
    assert "firstPackage=nginx==1.20.1-28.el9_8.2.alma.1.x86_64" in advisory_gate_text
    assert "firstAdvisory=OSV-2026-0002" in advisory_gate_text
    assert "firstSeverity=HIGH" in advisory_gate_text
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "advisory-bundle"
        completed_advisory_bundle = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "advisory-bundle",
                "--source",
                "rpm-repo",
                "--path",
                "tests/fixtures/repodata/repomd.xml",
                "--public-advisory-feed",
                "tests/fixtures/public-osv-ranges.json",
                "--ecosystem",
                "rpm",
                "--fail-on-findings",
                "--fail-min-severity",
                "high",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed_advisory_bundle.returncode == 2
        assert completed_advisory_bundle.stdout.strip() == str(output_dir / "index.html")
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "advisory-report"
        assert manifest["reports"][0]["href"] == "001-advisory-report.html"
        assert manifest["reports"][0]["schema"] == "edgp.advisory.report.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        bundled_advisory = json.loads(
            (output_dir / "advisory-report.json").read_text(encoding="utf-8")
        )
        assert bundled_advisory["summary"]["findings"] == 1
        assert 'data-testid="advisory-findings-panel"' in (
            output_dir / "001-advisory-report.html"
        ).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "advisory-bundle-text"
        completed_advisory_bundle_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "advisory-bundle",
                "--source",
                "rpm-repo",
                "--path",
                "tests/fixtures/repodata/repomd.xml",
                "--public-advisory-feed",
                "tests/fixtures/public-osv-ranges.json",
                "--ecosystem",
                "rpm",
                "--fail-on-findings",
                "--fail-min-severity",
                "high",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed_advisory_bundle_text.returncode == 2
        advisory_bundle_text = completed_advisory_bundle_text.stdout.strip()
        assert advisory_bundle_text.startswith("BUNDLE ")
        assert f"index={output_dir / 'index.html'}" in advisory_bundle_text
        assert "sourceKind=advisory-report" in advisory_bundle_text
        assert "triageStatus=fail" in advisory_bundle_text
    completed_noncritical_gate = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "advisory",
            "--source",
            "rpm-repo",
            "--path",
            "tests/fixtures/repodata/repomd.xml",
            "--public-advisory-feed",
            "tests/fixtures/public-osv-ranges.json",
            "--ecosystem",
            "rpm",
            "--fail-on-findings",
            "--fail-min-severity",
            "critical",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    noncritical_advisory = json.loads(completed_noncritical_gate.stdout)
    assert noncritical_advisory["schema"] == "edgp.advisory.report.v1"
    assert noncritical_advisory["summary"]["findings"] == 1
    completed_cvss_gate = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "advisory",
            "--source",
            "rpm-repo",
            "--path",
            "tests/fixtures/repodata/repomd.xml",
            "--public-advisory-feed",
            "tests/fixtures/public-osv-cvss-score.json",
            "--ecosystem",
            "rpm",
            "--fail-on-findings",
            "--fail-min-severity",
            "critical",
        ],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed_cvss_gate.returncode == 2
    cvss_advisory = json.loads(completed_cvss_gate.stdout)
    assert cvss_advisory["schema"] == "edgp.advisory.report.v1"
    assert cvss_advisory["findings"][0]["advisory"]["severity"] == "9.8"
    purl_advisory = _run_cli(
        [
            "advisory",
            "--source",
            "sbom",
            "--path",
            "tests/fixtures/sample-bom.json",
            "--public-advisory-feed",
            "tests/fixtures/public-osv-purl.json",
            "--ecosystem",
            "npm",
        ]
    )
    assert purl_advisory["schema"] == "edgp.advisory.report.v1"
    assert purl_advisory["summary"]["findings"] == 1
    assert purl_advisory["findings"][0]["package"] == "left-pad==1.3.0"
    completed_license_gate = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "license-report",
            "--source",
            "sbom",
            "--path",
            "tests/fixtures/sample-bom.json",
            "--deny-license",
            "WTFPL",
            "--fail-on-denied",
        ],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed_license_gate.returncode == 2
    license_gate = json.loads(completed_license_gate.stdout)
    assert license_gate["schema"] == "edgp.license.report.v1"
    assert license_gate["summary"]["deniedFindings"] == 1
    assert license_gate["findings"][0]["package"] == "left-pad==1.3.0"
    completed_license_gate_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "license-report",
            "--source",
            "sbom",
            "--path",
            "tests/fixtures/sample-bom.json",
            "--deny-license",
            "WTFPL",
            "--format",
            "text",
            "--fail-on-denied",
        ],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed_license_gate_text.returncode == 2
    license_gate_text = completed_license_gate_text.stdout.strip()
    assert license_gate_text.startswith("LICENSE_REPORT ")
    assert "schema=edgp.license.report.v1" in license_gate_text
    assert "deniedFindings=1" in license_gate_text
    assert "firstDeniedPackage=left-pad==1.3.0" in license_gate_text
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "license-report-bundle"
        completed_license_bundle = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "license-report-bundle",
                "--source",
                "sbom",
                "--path",
                "tests/fixtures/sample-bom.json",
                "--deny-license",
                "WTFPL",
                "--fail-on-denied",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed_license_bundle.returncode == 2
        assert completed_license_bundle.stdout.strip() == str(output_dir / "index.html")
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "license-report"
        assert manifest["reports"][0]["href"] == "001-license-report.html"
        assert manifest["reports"][0]["schema"] == "edgp.license.report.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        bundle_license = json.loads(
            (output_dir / "license-report.json").read_text(encoding="utf-8")
        )
        assert bundle_license["summary"]["deniedFindings"] == 1
        assert 'data-testid="license-denied-panel"' in (
            output_dir / "001-license-report.html"
        ).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "license-report-bundle-text"
        completed_license_bundle_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "license-report-bundle",
                "--source",
                "sbom",
                "--path",
                "tests/fixtures/sample-bom.json",
                "--deny-license",
                "WTFPL",
                "--fail-on-denied",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed_license_bundle_text.returncode == 2
        license_bundle_text = completed_license_bundle_text.stdout.strip()
        assert license_bundle_text.startswith("BUNDLE ")
        assert f"index={output_dir / 'index.html'}" in license_bundle_text
        assert "sourceKind=license-report" in license_bundle_text
        assert "triageStatus=fail" in license_bundle_text
    triage = _run_cli(
        [
            "triage-summary",
            "--input",
            "tests/fixtures/snapshot-right.json",
            "--input",
            "tests/fixtures/advisory-report.json",
            "--input",
            "tests/fixtures/license-report.json",
            "--input",
            "tests/fixtures/npm-diagnostics-report.json",
        ]
    )
    assert triage["schema"] == "edgp.triage.summary.v1"
    assert triage["status"] == "fail"
    assert triage["summary"]["failedChecks"] == 2
    completed_triage_gate = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "triage-summary",
            "--input",
            "tests/fixtures/advisory-report.json",
            "--fail-on-status",
            "fail",
        ],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert completed_triage_gate.returncode == 2
    gated_triage = json.loads(completed_triage_gate.stdout)
    assert gated_triage["schema"] == "edgp.triage.summary.v1"
    assert gated_triage["status"] == "fail"

    libsolv = _run_cli(
        ["libsolv-bridge", "--transaction", "tests/fixtures/libsolv-transaction.txt"]
    )
    assert libsolv["schema"] == "edgp.libsolv.bridge.v1"
    assert libsolv["summary"]["transactionActions"] == 3
    assert libsolv["summary"]["parsedPackages"] == 4
    assert libsolv["transactionActions"][0]["nodeId"] == (
        "nginx==1.20.1-28.el9_8.2.alma.1.x86_64"
    )
    assert libsolv["transactionActions"][1]["oldNodeId"] == (
        "openssl==3.0.7-1.el9.x86_64"
    )
    assert libsolv["transactionActions"][1]["newNodeId"] == (
        "openssl==3.0.7-2.el9.x86_64"
    )
    completed_libsolv_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "libsolv-bridge",
            "--transaction",
            "tests/fixtures/libsolv-transaction.txt",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    libsolv_text = completed_libsolv_text.stdout.strip()
    assert libsolv_text.startswith("LIBSOLV_BRIDGE schema=edgp.libsolv.bridge.v1")
    assert "transactionActions=3" in libsolv_text
    assert "parsedPackages=4" in libsolv_text
    assert "installs=1" in libsolv_text
    assert "erases=1" in libsolv_text
    assert "upgrades=1" in libsolv_text
    rpm_repo_snapshot = _run_cli(
        ["rpm-repo", "--source", "tests/fixtures/repodata/repomd.xml", "--format", "json"]
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        graph_snapshot_path = Path(tmpdir) / "rpm-repo-snapshot.json"
        graph_snapshot_path.write_text(json.dumps(rpm_repo_snapshot), encoding="utf-8")
        libsolv_graph = _run_cli(
            [
                "libsolv-bridge",
                "--transaction",
                "tests/fixtures/libsolv-transaction.txt",
                "--graph-snapshot",
                str(graph_snapshot_path),
            ]
        )
    assert libsolv_graph["schema"] == "edgp.libsolv.bridge.v1"
    assert libsolv_graph["graphContext"]["schema"] == "edgp.graph.snapshot.v1"
    assert libsolv_graph["summary"]["graphExactActions"] == 1
    assert libsolv_graph["summary"]["graphImpactedActions"] == 1
    assert libsolv_graph["transactionImpact"][0]["matchStatus"] == "exact"
    assert libsolv_graph["transactionActions"][0]["graphMatchStatus"] == "exact"
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "libsolv-bundle"
        graph_snapshot_path = Path(tmpdir) / "rpm-repo-snapshot.json"
        graph_snapshot_path.write_text(json.dumps(rpm_repo_snapshot), encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "libsolv-bundle",
                "--transaction",
                "tests/fixtures/libsolv-transaction.txt",
                "--graph-snapshot",
                str(graph_snapshot_path),
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip().endswith("index.html")
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "libsolv-transaction"
        report = json.loads((output_dir / "libsolv-bridge.json").read_text(encoding="utf-8"))
        assert report["summary"]["graphExactActions"] == 1
        assert report["transactionImpact"][0]["affectedDependents"] == 1
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        text_output_dir = Path(tmpdir) / "libsolv-bundle-text"
        completed_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "libsolv-bundle",
                "--transaction",
                "tests/fixtures/libsolv-transaction.txt",
                "--graph-snapshot",
                str(graph_snapshot_path),
                "--output-dir",
                str(text_output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        libsolv_bundle_text = completed_text.stdout.strip()
        assert libsolv_bundle_text.startswith("BUNDLE ")
        assert "sourceKind=libsolv-transaction" in libsolv_bundle_text
        assert "reports=1" in libsolv_bundle_text
        assert "triageStatus=pass" in libsolv_bundle_text

    advisory = _run_cli(
        ["public-advisory-feed", "--path", "tests/fixtures/public-osv.json"]
    )
    assert advisory["schema"] == "edgp.public.advisory_feed.v1"
    assert advisory["overlay"]["schema"] == "edgp.advisory.overlay.v1"
    advisory_url = _run_cli(
        [
            "public-advisory-feed",
            "--url",
            (REPO_ROOT / "tests" / "fixtures" / "public-osv.json").as_uri(),
        ]
    )
    assert advisory_url["schema"] == "edgp.public.advisory_feed.v1"
    assert advisory_url["summary"]["advisories"] == 1
    advisory_range = _run_cli(
        ["public-advisory-feed", "--path", "tests/fixtures/public-osv-ranges.json"]
    )
    assert advisory_range["schema"] == "edgp.public.advisory_feed.v1"
    assert advisory_range["advisories"][0]["ranges"][0]["fixed"] == (
        "1.20.1-28.el9_8.2.alma.2"
    )
    advisory_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "public-advisory-feed",
            "--path",
            "tests/fixtures/public-osv.json",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert advisory_text.startswith("OK schema=edgp.public.advisory_feed.v1")
    assert "advisories=1" in advisory_text
    assert "firstAdvisory=OSV-2026-0001" in advisory_text

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "public-advisory-feed-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "public-advisory-feed-bundle",
                "--path",
                "tests/fixtures/public-osv.json",
                "--ecosystem",
                "rpm",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "public-advisory-feed"
        assert manifest["reports"][0]["href"] == "001-public-advisory-feed.html"
        assert manifest["reports"][0]["schema"] == "edgp.public.advisory_feed.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        report = json.loads(
            (output_dir / "public-advisory-feed.json").read_text(encoding="utf-8")
        )
        assert report["schema"] == "edgp.public.advisory_feed.v1"
        assert report["summary"]["advisories"] == 1
        assert 'data-testid="public-advisory-feed-panel"' in (
            output_dir / "001-public-advisory-feed.html"
        ).read_text(encoding="utf-8")

        text_output_dir = Path(temp_dir) / "public-advisory-feed-bundle-text"
        completed_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "public-advisory-feed-bundle",
                "--path",
                "tests/fixtures/public-osv.json",
                "--ecosystem",
                "rpm",
                "--output-dir",
                str(text_output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        advisory_bundle_text = completed_text.stdout.strip()
        assert advisory_bundle_text.startswith("BUNDLE ")
        assert "sourceKind=public-advisory-feed" in advisory_bundle_text
        assert "reports=1" in advisory_bundle_text
        assert "triageStatus=pass" in advisory_bundle_text

    fixture_provenance = _run_cli(
        ["fixture-provenance", "--fixture-dir", "tests/fixtures"]
    )
    assert fixture_provenance["schema"] == "edgp.fixture.provenance.v1"
    assert fixture_provenance["summary"]["publicDerivedSources"] == 3
    assert fixture_provenance["summary"]["generatedPublicReports"] == 14
    fixture_provenance_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "fixture-provenance",
            "--fixture-dir",
            "tests/fixtures",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert fixture_provenance_text.startswith("OK schema=edgp.fixture.provenance.v1")
    assert "publicDerivedSources=3" in fixture_provenance_text
    assert "generatedPublicReports=14" in fixture_provenance_text
    assert "sourceUrls=3" in fixture_provenance_text

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "fixture-provenance-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "fixture-provenance-bundle",
                "--fixture-dir",
                "tests/fixtures",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "fixture-provenance"
        assert manifest["reports"][0]["href"] == "001-fixture-provenance.html"
        assert manifest["reports"][0]["schema"] == "edgp.fixture.provenance.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        report = json.loads(
            (output_dir / "fixture-provenance.json").read_text(encoding="utf-8")
        )
        assert report["summary"]["catalogedFiles"] >= 70
        assert 'data-testid="fixture-provenance-entries-panel"' in (
            output_dir / "001-fixture-provenance.html"
        ).read_text(encoding="utf-8")

    real_data_coverage = _run_cli(
        ["real-data-coverage", "--fixture-dir", "tests/fixtures"]
    )
    assert real_data_coverage["schema"] == "edgp.real_data.coverage.v1"
    assert real_data_coverage["summary"]["directPublicSources"] == 3
    assert real_data_coverage["summary"]["generatedPublicReports"] == 14
    assert real_data_coverage["summary"]["replacementCandidateGroups"] >= 4
    real_data_coverage_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "real-data-coverage",
            "--fixture-dir",
            "tests/fixtures",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert real_data_coverage_text.startswith("WARN schema=edgp.real_data.coverage.v1")
    assert "directPublicSources=3" in real_data_coverage_text
    policy_completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "real-data-coverage",
            "--fixture-dir",
            "tests/fixtures",
            "--fail-on-priority",
            "high",
        ],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert policy_completed.returncode == 2
    policy_report = json.loads(policy_completed.stdout)
    assert policy_report["policy"]["status"] == "fail"
    assert policy_report["policy"]["matchedReplacementGroups"] == 1

    real_data_replacement_plan = _run_cli(
        ["real-data-replacement-plan", "--fixture-dir", "tests/fixtures"]
    )
    assert real_data_replacement_plan["schema"] == (
        "edgp.real_data.replacement_plan.v1"
    )
    assert real_data_replacement_plan["summary"]["replacementCandidates"] >= 1
    assert real_data_replacement_plan["replacementCandidates"][0]["priority"] == "high"
    real_data_replacement_plan_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "real-data-replacement-plan",
            "--fixture-dir",
            "tests/fixtures",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert real_data_replacement_plan_text.startswith(
        "WARN schema=edgp.real_data.replacement_plan.v1"
    )
    assert "replacementCandidates=" in real_data_replacement_plan_text
    coverage_plan = _run_cli(
        [
            "real-data-replacement-plan",
            "--coverage",
            "tests/fixtures/real-data-coverage.json",
        ]
    )
    assert coverage_plan == real_data_replacement_plan
    replacement_policy_completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "real-data-replacement-plan",
            "--fixture-dir",
            "tests/fixtures",
            "--fail-on-priority",
            "high",
        ],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert replacement_policy_completed.returncode == 2
    replacement_policy_report = json.loads(replacement_policy_completed.stdout)
    assert replacement_policy_report["policy"]["status"] == "fail"
    assert replacement_policy_report["policy"]["matchedReplacementGroups"] == 1

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "real-data-replacement-plan-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-replacement-plan-bundle",
                "--fixture-dir",
                "tests/fixtures",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "real-data-replacement-plan"
        assert manifest["reports"][0]["href"] == "001-real-data-replacement-plan.html"
        assert manifest["reports"][0]["schema"] == (
            "edgp.real_data.replacement_plan.v1"
        )
        report = json.loads(
            (output_dir / "real-data-replacement-plan.json").read_text(
                encoding="utf-8"
            )
        )
        assert report == real_data_replacement_plan
        assert 'data-testid="real-data-replacement-plan-candidates-panel"' in (
            output_dir / "001-real-data-replacement-plan.html"
        ).read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "real-data-replacement-plan-policy-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-replacement-plan-bundle",
                "--fixture-dir",
                "tests/fixtures",
                "--output-dir",
                str(output_dir),
                "--fail-on-priority",
                "high",
                "--fail-on-status",
                "fail",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        policy_bundle_report = json.loads(
            (output_dir / "real-data-replacement-plan.json").read_text(
                encoding="utf-8"
            )
        )
        triage = json.loads(
            (output_dir / "triage-summary.json").read_text(encoding="utf-8")
        )
        assert policy_bundle_report["policy"]["status"] == "fail"
        assert triage["status"] == "fail"
        assert triage["summary"]["realDataReplacementPlanPolicyFailures"] == 1
        catalog_dir = Path(temp_dir) / "real-data-replacement-plan-catalog"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "bundle-catalog",
                "--bundle",
                str(output_dir),
                "--output-dir",
                str(catalog_dir),
                "--format",
                "text",
                "--fail-on-status",
                "fail",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert "realDataReplacementPlanPolicyFailures=1" in completed.stdout
        catalog = json.loads(
            (catalog_dir / "bundle-catalog.json").read_text(encoding="utf-8")
        )
        assert catalog["status"] == "fail"
        assert catalog["summary"]["realDataReplacementPlanPolicyFailures"] == 1
        assert catalog["bundles"][0]["realDataReplacementPlanPolicyFailures"] == 1
        assert catalog["bundles"][0]["realDataReplacementPlanFailureCodes"] == [
            "replacementPlanPriorityMatched"
        ]
        assert catalog["sourceKinds"][0]["realDataReplacementPlanFailureCodes"] == [
            "replacementPlanPriorityMatched"
        ]

    real_data_replacement_plan_diff = _run_cli(
        [
            "real-data-replacement-plan-diff",
            "--left",
            "tests/fixtures/real-data-replacement-plan.json",
            "--right",
            "tests/fixtures/real-data-replacement-plan.json",
            "--left-label",
            "baseline",
            "--right-label",
            "current",
        ]
    )
    assert real_data_replacement_plan_diff["schema"] == (
        "edgp.real_data.replacement_plan_diff.v1"
    )
    assert real_data_replacement_plan_diff["summary"]["candidateFilesDelta"] == 0
    assert real_data_replacement_plan_diff["summary"]["regressions"] == 0
    replacement_plan_diff_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "real-data-replacement-plan-diff",
            "--left",
            "tests/fixtures/real-data-replacement-plan.json",
            "--right",
            "tests/fixtures/real-data-replacement-plan.json",
            "--left-label",
            "baseline",
            "--right-label",
            "current",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert replacement_plan_diff_text.startswith(
        "PASS schema=edgp.real_data.replacement_plan_diff.v1"
    )
    assert "replacementCandidatesDelta=0" in replacement_plan_diff_text
    fixture_dir_plan_diff = _run_cli(
        [
            "real-data-replacement-plan-diff",
            "--left-fixture-dir",
            "tests/fixtures",
            "--right-fixture-dir",
            "tests/fixtures",
            "--left-label",
            "baseline",
            "--right-label",
            "current",
        ]
    )
    assert fixture_dir_plan_diff == real_data_replacement_plan_diff

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "real-data-replacement-plan-diff-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-replacement-plan-diff-bundle",
                "--left",
                "tests/fixtures/real-data-replacement-plan.json",
                "--right",
                "tests/fixtures/real-data-replacement-plan.json",
                "--left-label",
                "baseline",
                "--right-label",
                "current",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == (
            "real-data-replacement-plan-diff"
        )
        assert manifest["reports"][0]["href"] == (
            "001-real-data-replacement-plan-diff.html"
        )
        assert manifest["reports"][0]["schema"] == (
            "edgp.real_data.replacement_plan_diff.v1"
        )
        report = json.loads(
            (output_dir / "real-data-replacement-plan-diff.json").read_text(
                encoding="utf-8"
            )
        )
        assert report == real_data_replacement_plan_diff
        assert 'data-testid="real-data-replacement-plan-diff-sides-panel"' in (
            output_dir / "001-real-data-replacement-plan-diff.html"
        ).read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as temp_dir:
        regressed_path = Path(temp_dir) / "real-data-replacement-plan-regressed.json"
        regressed_plan = json.loads(json.dumps(real_data_replacement_plan))
        candidate = {
            "rank": len(regressed_plan["replacementCandidates"]) + 1,
            "group": "New public-data gap",
            "kind": "synthetic-public-shape",
            "fileCount": 2,
            "decision": "replace-where-practical",
            "priority": "high",
            "nextStep": "Add a stable public source for this new fixture gap.",
            "files": ["tests/fixtures/new-public-gap.json"],
        }
        regressed_plan["replacementCandidates"].append(candidate)
        regressed_plan["summary"]["totalGroups"] += 1
        regressed_plan["summary"]["replacementCandidates"] += 1
        regressed_plan["summary"]["candidateFiles"] += candidate["fileCount"]
        regressed_plan["summary"]["highPriorityGroups"] += 1
        regressed_path.write_text(json.dumps(regressed_plan), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-replacement-plan-diff",
                "--left",
                "tests/fixtures/real-data-replacement-plan.json",
                "--right",
                str(regressed_path),
                "--fail-on-regression",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        diff_policy_report = json.loads(completed.stdout)
        assert diff_policy_report["policy"]["status"] == "fail"
        assert diff_policy_report["summary"]["addedCandidates"] == 1
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-replacement-plan-diff",
                "--left",
                "tests/fixtures/real-data-replacement-plan.json",
                "--right",
                str(regressed_path),
                "--fail-on-regression",
                "--format",
                "text",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert "policyStatus=fail" in completed.stdout
        assert "addedCandidates=1" in completed.stdout

        output_dir = Path(temp_dir) / "real-data-replacement-plan-diff-policy-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-replacement-plan-diff-bundle",
                "--left",
                "tests/fixtures/real-data-replacement-plan.json",
                "--right",
                str(regressed_path),
                "--output-dir",
                str(output_dir),
                "--fail-on-regression",
                "--fail-on-status",
                "fail",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        diff_bundle_report = json.loads(
            (output_dir / "real-data-replacement-plan-diff.json").read_text(
                encoding="utf-8"
            )
        )
        triage = json.loads(
            (output_dir / "triage-summary.json").read_text(encoding="utf-8")
        )
        assert diff_bundle_report["policy"]["status"] == "fail"
        assert triage["status"] == "fail"
        assert triage["summary"]["realDataReplacementPlanDiffPolicyFailures"] == 1
        catalog_dir = Path(temp_dir) / "real-data-replacement-plan-diff-catalog"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "bundle-catalog",
                "--bundle",
                str(output_dir),
                "--output-dir",
                str(catalog_dir),
                "--format",
                "text",
                "--fail-on-status",
                "fail",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert "realDataReplacementPlanDiffPolicyFailures=1" in completed.stdout
        catalog = json.loads(
            (catalog_dir / "bundle-catalog.json").read_text(encoding="utf-8")
        )
        assert catalog["status"] == "fail"
        assert catalog["summary"]["realDataReplacementPlanDiffPolicyFailures"] == 1
        assert catalog["bundles"][0][
            "realDataReplacementPlanDiffPolicyFailures"
        ] == 1
        assert catalog["bundles"][0]["realDataReplacementPlanDiffFailureCodes"] == [
            "replacementCandidatesIncreased",
            "candidateFilesIncreased",
            "highPriorityGroupsIncreased",
        ]
        assert catalog["sourceKinds"][0][
            "realDataReplacementPlanDiffFailureCodes"
        ] == [
            "replacementCandidatesIncreased",
            "candidateFilesIncreased",
            "highPriorityGroupsIncreased",
        ]

    real_data_coverage_diff = _run_cli(
        [
            "real-data-coverage-diff",
            "--left",
            "tests/fixtures/real-data-coverage.json",
            "--right",
            "tests/fixtures/real-data-coverage.json",
            "--left-label",
            "baseline",
            "--right-label",
            "current",
        ]
    )
    assert real_data_coverage_diff["schema"] == "edgp.real_data.coverage_diff.v1"
    assert real_data_coverage_diff["left"]["label"] == "baseline"
    assert real_data_coverage_diff["right"]["label"] == "current"
    assert real_data_coverage_diff["summary"]["publicEvidenceFilesDelta"] == 0
    assert real_data_coverage_diff["summary"]["regressions"] == 0
    coverage_diff_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "real-data-coverage-diff",
            "--left",
            "tests/fixtures/real-data-coverage.json",
            "--right",
            "tests/fixtures/real-data-coverage.json",
            "--left-label",
            "baseline",
            "--right-label",
            "current",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert coverage_diff_text.startswith("PASS schema=edgp.real_data.coverage_diff.v1")
    assert "publicEvidenceFilesDelta=0" in coverage_diff_text
    fixture_dir_diff = _run_cli(
        [
            "real-data-coverage-diff",
            "--left-fixture-dir",
            "tests/fixtures",
            "--right-fixture-dir",
            "tests/fixtures",
            "--left-label",
            "baseline",
            "--right-label",
            "current",
        ]
    )
    assert fixture_dir_diff == real_data_coverage_diff
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "real-data-coverage-diff-fixture-dir-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-coverage-diff-bundle",
                "--left-fixture-dir",
                "tests/fixtures",
                "--right-fixture-dir",
                "tests/fixtures",
                "--left-label",
                "baseline",
                "--right-label",
                "current",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        report = json.loads(
            (output_dir / "real-data-coverage-diff.json").read_text(encoding="utf-8")
        )
        assert report == real_data_coverage_diff

    with tempfile.TemporaryDirectory() as temp_dir:
        regressed_path = Path(temp_dir) / "real-data-coverage-regressed.json"
        regressed_report = json.loads(json.dumps(real_data_coverage))
        removed = regressed_report["publicEvidence"].pop()
        regressed_summary = regressed_report["summary"]
        regressed_summary["publicEvidenceFiles"] = len(
            regressed_report["publicEvidence"]
        )
        regressed_summary["publicEvidenceCoveragePercent"] = round(
            regressed_summary["publicEvidenceFiles"]
            / regressed_summary["catalogedFiles"]
            * 100,
            2,
        )
        if removed.get("kind") == "generated-public-report":
            regressed_summary["generatedPublicReports"] -= 1
        regressed_path.write_text(json.dumps(regressed_report), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-coverage-diff",
                "--left",
                "tests/fixtures/real-data-coverage.json",
                "--right",
                str(regressed_path),
                "--fail-on-regression",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        diff_policy_report = json.loads(completed.stdout)
        assert diff_policy_report["policy"]["status"] == "fail"
        assert diff_policy_report["summary"]["removedPublicEvidence"] == 1
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-coverage-diff",
                "--left",
                "tests/fixtures/real-data-coverage.json",
                "--right",
                str(regressed_path),
                "--fail-on-regression",
                "--format",
                "text",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert "policyStatus=fail" in completed.stdout
        assert "removedPublicEvidence=1" in completed.stdout

        output_dir = Path(temp_dir) / "real-data-coverage-diff-policy-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-coverage-diff-bundle",
                "--left",
                "tests/fixtures/real-data-coverage.json",
                "--right",
                str(regressed_path),
                "--output-dir",
                str(output_dir),
                "--fail-on-regression",
                "--fail-on-status",
                "fail",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert completed.stdout.strip() == str(output_dir / "index.html")
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "real-data-coverage-diff"
        assert manifest["reports"][0]["href"] == "001-real-data-coverage-diff.html"
        assert manifest["reports"][0]["schema"] == "edgp.real_data.coverage_diff.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        diff_bundle_report = json.loads(
            (output_dir / "real-data-coverage-diff.json").read_text(encoding="utf-8")
        )
        triage = json.loads(
            (output_dir / "triage-summary.json").read_text(encoding="utf-8")
        )
        assert diff_bundle_report["policy"]["status"] == "fail"
        assert triage["status"] == "fail"
        assert triage["summary"]["realDataCoverageDiffPolicyFailures"] == 1
        assert 'data-testid="real-data-coverage-diff-sides-panel"' in (
            output_dir / "001-real-data-coverage-diff.html"
        ).read_text(encoding="utf-8")
        catalog_dir = Path(temp_dir) / "real-data-coverage-diff-catalog"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "bundle-catalog",
                "--bundle",
                str(output_dir),
                "--output-dir",
                str(catalog_dir),
                "--format",
                "text",
                "--fail-on-status",
                "fail",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert "realDataCoverageDiffPolicyFailures=1" in completed.stdout
        catalog = json.loads(
            (catalog_dir / "bundle-catalog.json").read_text(encoding="utf-8")
        )
        assert catalog["status"] == "fail"
        assert catalog["summary"]["realDataCoverageDiffPolicyFailures"] == 1
        assert catalog["bundles"][0]["realDataCoverageDiffPolicyFailures"] == 1
        assert catalog["bundles"][0]["realDataCoverageDiffFailureCodes"] == [
            "publicEvidenceCoverageDecreased",
            "publicEvidenceFilesDecreased",
        ]
        assert catalog["sourceKinds"][0]["realDataCoverageDiffFailureCodes"] == [
            "publicEvidenceCoverageDecreased",
            "publicEvidenceFilesDecreased",
        ]

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "real-data-coverage-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-coverage-bundle",
                "--fixture-dir",
                "tests/fixtures",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "real-data-coverage"
        assert manifest["reports"][0]["href"] == "001-real-data-coverage.html"
        assert manifest["reports"][0]["schema"] == "edgp.real_data.coverage.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        report = json.loads(
            (output_dir / "real-data-coverage.json").read_text(encoding="utf-8")
        )
        assert report["summary"]["publicEvidenceFiles"] >= 10
        assert 'data-testid="real-data-coverage-plan-panel"' in (
            output_dir / "001-real-data-coverage.html"
        ).read_text(encoding="utf-8")

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "real-data-coverage-policy-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "real-data-coverage-bundle",
                "--fixture-dir",
                "tests/fixtures",
                "--output-dir",
                str(output_dir),
                "--fail-on-priority",
                "high",
                "--fail-on-status",
                "fail",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert completed.stdout.strip() == str(output_dir / "index.html")
        policy_bundle_report = json.loads(
            (output_dir / "real-data-coverage.json").read_text(encoding="utf-8")
        )
        triage = json.loads(
            (output_dir / "triage-summary.json").read_text(encoding="utf-8")
        )
        assert policy_bundle_report["policy"]["status"] == "fail"
        assert triage["status"] == "fail"
        assert triage["summary"]["realDataCoveragePolicyFailures"] == 1
        catalog_dir = Path(temp_dir) / "real-data-coverage-catalog"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "bundle-catalog",
                "--bundle",
                str(output_dir),
                "--output-dir",
                str(catalog_dir),
                "--format",
                "text",
                "--fail-on-status",
                "fail",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert "realDataCoveragePolicyFailures=1" in completed.stdout
        catalog = json.loads(
            (catalog_dir / "bundle-catalog.json").read_text(encoding="utf-8")
        )
        assert catalog["status"] == "fail"
        assert catalog["summary"]["realDataCoveragePolicyFailures"] == 1
        assert catalog["bundles"][0]["realDataCoveragePolicyFailures"] == 1
        assert catalog["bundles"][0]["realDataCoverageFailureCodes"] == [
            "replacementPriorityMatched"
        ]
        assert catalog["sourceKinds"][0]["realDataCoverageFailureCodes"] == [
            "replacementPriorityMatched"
        ]

    performance = _run_cli(
        ["performance-report", "--scenario", "16:2", "--scenario", "32:3"]
    )
    assert performance["schema"] == "edgp.performance.report.v1"
    assert performance["summary"]["allContiguous"] is True
    performance_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "performance-report",
            "--scenario",
            "16:2",
            "--scenario",
            "32:3",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert performance_text.startswith("OK schema=edgp.performance.report.v1")
    assert "scenarios=2" in performance_text
    assert "allContiguous=true" in performance_text

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "rpm-repo-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "rpm-repo-bundle",
                "--source",
                "tests/fixtures/repodata/repomd.xml",
                "--impact-node",
                "nginx-core",
                "--advisories",
                "tests/fixtures/rpm-repo-advisories.json",
                "--public-advisory-feed-url",
                (
                    REPO_ROOT / "tests" / "fixtures" / "public-osv-ranges.json"
                ).as_uri(),
                "--libsolv-transaction",
                "tests/fixtures/libsolv-transaction.txt",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "rpm-repository"
        assert manifest["reports"][1]["href"] == "002-rpm-repository-summary.html"
        assert manifest["reports"][3]["href"] == "004-advisory-report.html"
        assert manifest["reports"][4]["href"] == "005-public-advisory-feed.html"
        assert manifest["reports"][5]["href"] == "006-public-advisory-report.html"
        assert manifest["reports"][6]["href"] == "007-libsolv-bridge.html"
        assert manifest["triageSummary"]["href"] == "triage-summary.html"
        advisory = json.loads(
            (output_dir / "advisory-report.json").read_text(encoding="utf-8")
        )
        assert advisory["schema"] == "edgp.advisory.report.v1"
        assert advisory["summary"]["findings"] == 1
        public_feed = json.loads(
            (output_dir / "public-advisory-feed.json").read_text(encoding="utf-8")
        )
        assert public_feed["schema"] == "edgp.public.advisory_feed.v1"
        assert public_feed["summary"]["advisories"] == 1
        assert public_feed["advisories"][0]["versions"] == []
        assert public_feed["advisories"][0]["ranges"][0]["fixed"] == (
            "1.20.1-28.el9_8.2.alma.2"
        )
        triage = json.loads(
            (output_dir / "triage-summary.json").read_text(encoding="utf-8")
        )
        assert triage["schema"] == "edgp.triage.summary.v1"
        assert triage["status"] == "fail"
        assert triage["summary"]["reports"] == 7
        libsolv = json.loads(
            (output_dir / "libsolv-bridge.json").read_text(encoding="utf-8")
        )
        assert libsolv["schema"] == "edgp.libsolv.bridge.v1"
        assert libsolv["summary"]["graphExactActions"] == 1
        assert libsolv["transactionImpact"][0]["matchStatus"] == "exact"
        public_advisory = json.loads(
            (output_dir / "public-advisory-report.json").read_text(encoding="utf-8")
        )
        assert public_advisory["schema"] == "edgp.advisory.report.v1"
        assert public_advisory["summary"]["findings"] == 1

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "rpm-repo-diff-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "rpm-repo-diff-bundle",
                "--left-primary",
                "tests/fixtures/rpm-primary.xml",
                "--right-primary",
                "tests/fixtures/rpm-primary-updated.xml",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(output_dir / "index.html")
        manifest = json.loads(
            (output_dir / "manifest.json").read_text(encoding="utf-8")
        )
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "rpm-repository-diff"
        assert manifest["reports"][0]["href"] == "001-rpm-repository-diff.html"
        diff = json.loads(
            (output_dir / "rpm-repository-diff.json").read_text(encoding="utf-8")
        )
        assert diff["schema"] == "edgp.rpm.repository_diff.v1"
        assert diff["summary"]["changedPackages"] == 1

        text_output_dir = Path(temp_dir) / "rpm-repo-diff-bundle-text"
        completed_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "rpm-repo-diff-bundle",
                "--left-primary",
                "tests/fixtures/rpm-primary.xml",
                "--right-primary",
                "tests/fixtures/rpm-primary-updated.xml",
                "--output-dir",
                str(text_output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        rpm_repo_diff_bundle_text = completed_text.stdout.strip()
        assert rpm_repo_diff_bundle_text.startswith("BUNDLE ")
        assert "sourceKind=rpm-repository-diff" in rpm_repo_diff_bundle_text
        assert "reports=1" in rpm_repo_diff_bundle_text
        assert "triageStatus=pass" in rpm_repo_diff_bundle_text


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
                "--deny-license",
                "WTFPL",
                "--fail-on-denied",
                "--output-dir",
                str(output_dir),
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
        assert completed.stdout.strip() == str(output_dir / "index.html")
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        assert manifest["bundle"]["sourceKind"] == "cyclonedx-sbom"
        assert manifest["bundle"]["command"].startswith("edgp sbom-bundle ")
        assert manifest["reports"][0]["href"] == "001-sbom-graph.html"
        assert manifest["reports"][1]["href"] == "002-impact-left-pad-1.3.0.html"
        assert manifest["reports"][2]["href"] == "003-license-report.html"
        impact = json.loads(
            (output_dir / "impact-left-pad-1.3.0.json").read_text(encoding="utf-8")
        )
        assert impact["node"] == "left-pad==1.3.0"
        license_report = json.loads(
            (output_dir / "license-report.json").read_text(encoding="utf-8")
        )
        assert license_report["schema"] == "edgp.license.report.v1"
        assert license_report["summary"]["deniedFindings"] == 1
        triage = _run_cli(["triage-summary", "--bundle", str(output_dir)])
        assert triage["schema"] == "edgp.triage.summary.v1"
        assert triage["bundle"]["sourceKind"] == "cyclonedx-sbom"
        assert triage["summary"]["deniedLicenseFindings"] == 1


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
    assert payload["summary"]["addedNodes"] == 2
    assert payload["summary"]["removedNodes"] == 1
    assert payload["summary"]["addedEdges"] == 2
    assert payload["summary"]["removedEdges"] == 1
    assert payload["summary"]["metadataChangedNodes"] == 0
    assert payload["summary"]["classifiedChanges"] == 2
    assert payload["summary"]["upgradeChanges"] == 1
    assert payload["summary"]["downgradeChanges"] == 0

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "graph-diff-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "diff-bundle",
                "--left",
                "tests/fixtures/snapshot-left.json",
                "--right",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "graph-diff"
        assert manifest["reports"][0]["href"] == "001-graph-diff.html"
        assert manifest["reports"][0]["schema"] == "edgp.graph.diff.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        bundled_diff = json.loads(
            (output_dir / "graph-diff.json").read_text(encoding="utf-8")
        )
        assert bundled_diff["summary"]["addedNodes"] == 2
        graph_diff_html = (output_dir / "001-graph-diff.html").read_text(
            encoding="utf-8"
        )
        assert 'data-testid="graph-diff-filter-panel"' in graph_diff_html
        assert 'data-graph-diff-search' in graph_diff_html
        assert "graphDiffQuery" in graph_diff_html
        assert "graphDiffKind" in graph_diff_html
        assert 'data-testid="graph-diff-added-nodes-panel"' in graph_diff_html

        diff_tree_dir = Path(temp_dir) / "graph-diff-tree-bundle"
        completed_tree = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "diff-tree-bundle",
                "--left",
                "tests/fixtures/snapshot-left.json",
                "--right",
                "tests/fixtures/snapshot-right.json",
                "--node",
                "app",
                "--depth",
                "2",
                "--output-dir",
                str(diff_tree_dir),
                "--triage-summary",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed_tree.stdout.strip() == str(diff_tree_dir / "index.html")
        diff_tree = json.loads(
            (diff_tree_dir / "graph-diff-tree.json").read_text(encoding="utf-8")
        )
        assert diff_tree["schema"] == "edgp.graph.diff_tree.v1"
        assert diff_tree["summary"]["classifiedChanges"] == 2
        diff_tree_html = (diff_tree_dir / "001-graph-diff-tree.html").read_text(
            encoding="utf-8"
        )
        assert 'data-testid="graph-diff-tree-filter-panel"' in diff_tree_html
        assert 'data-graph-diff-tree-search' in diff_tree_html
        assert "graphDiffTreeQuery" in diff_tree_html
        assert "graphDiffTreeKind" in diff_tree_html


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
    text_payload = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "impact",
            "--path",
            "tests/fixtures/package-lock.json",
            "--node",
            "left-pad",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert text_payload.startswith("IMPACT_REPORT ")
    assert "schema=edgp.impact.report.v1" in text_payload
    assert "node=left-pad==1.3.0" in text_payload
    assert "affectedDependents=2" in text_payload

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "impact-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "impact-bundle",
                "--path",
                "tests/fixtures/package-lock.json",
                "--node",
                "left-pad",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "impact-report"
        assert manifest["reports"][0]["href"] == "001-impact-report.html"
        assert manifest["reports"][0]["schema"] == "edgp.impact.report.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        report = json.loads((output_dir / "impact-report.json").read_text(encoding="utf-8"))
        assert report["schema"] == "edgp.impact.report.v1"
        assert report["node"] == "left-pad==1.3.0"
        assert report["summary"]["affectedDependents"] == 2
        assert 'data-testid="impact-chains-panel"' in (
            output_dir / "001-impact-report.html"
        ).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "impact-bundle-text"
        completed_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "impact-bundle",
                "--path",
                "tests/fixtures/package-lock.json",
                "--node",
                "left-pad",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        impact_bundle_text = completed_text.stdout.strip()
        assert impact_bundle_text.startswith("BUNDLE ")
        assert f"index={output_dir / 'index.html'}" in impact_bundle_text
        assert "sourceKind=impact-report" in impact_bundle_text
        assert "triageStatus=pass" in impact_bundle_text


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
        assert "smokeBundleReady" in html
        assert "bundleQuery" in html
        assert "bundleSchema" in html
        assert "initial filtered count" in html
        assert "updated filtered count" in html
        assert "reset filtered count" in html
        assert "bundle link order" in html
        assert "003-impact-report.html" in html
        assert "dataset.browserSmokeStatus = 'pass'" in html
        assert (output_dir / "001-snapshot-right.html").exists()
        assert (output_dir / "002-npm-diagnostics-report.html").exists()
        assert (output_dir / "003-impact-report.html").exists()


def _assert_browser_smoke_bundle_catalog_filters() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "bundle-catalog-filters-smoke.html"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "scripts/browser_smoke_bundle_catalog_filters.py",
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
        assert 'data-testid="bundle-catalog-filter-panel"' in html
        assert 'data-testid="browser-smoke-panel"' in html
        assert 'data-testid="browser-smoke-result"' in html
        assert "initial filtered count" in html
        assert "updated URL query" in html
        assert "reset filtered count" in html
        assert "dataset.browserSmokeStatus = 'pass'" in html


def _assert_browser_smoke_graph_diff_filters() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "graph-diff-filters-smoke.html"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "scripts/browser_smoke_graph_diff_filters.py",
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
        assert 'data-testid="graph-diff-filter-panel"' in html
        assert 'data-testid="browser-smoke-panel"' in html
        assert 'data-testid="browser-smoke-result"' in html
        assert "initial filtered count" in html
        assert "updated URL query" in html
        assert "reset filtered count" in html
        assert "dataset.browserSmokeStatus = 'pass'" in html


def _assert_browser_smoke_graph_diff_tree_filters() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = Path(temp_dir) / "graph-diff-tree-filters-smoke.html"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "scripts/browser_smoke_graph_diff_tree_filters.py",
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
        assert 'data-testid="graph-diff-tree-filter-panel"' in html
        assert 'data-testid="browser-smoke-panel"' in html
        assert 'data-testid="browser-smoke-result"' in html
        assert "initial filtered count" in html
        assert "updated URL query" in html
        assert "reset filtered count" in html
        assert "dataset.browserSmokeStatus = 'pass'" in html


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
                "--triage-summary",
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
        assert 'data-testid="report-bundle-filter-panel"' in index_html
        assert 'data-report-bundle-search' in index_html
        assert 'data-report-bundle-schema' in index_html
        assert 'data-report-bundle-card="true"' in index_html
        assert "bundleQuery" in index_html
        assert "bundleSchema" in index_html
        assert 'data-testid="report-bundle-triage-summary"' in index_html
        assert "002-npm-diagnostics-report.html" in index_html
        assert "triage-summary.html" in index_html
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        manifest_html_path = Path(temp_dir) / "report-bundle-manifest.html"
        completed_manifest_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                str(output_dir / "manifest.json"),
                "--output",
                str(manifest_html_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert Path(completed_manifest_report.stdout.strip()) == manifest_html_path
        manifest_html = manifest_html_path.read_text(encoding="utf-8")
        assert 'data-testid="report-bundle-manifest-panel"' in manifest_html
        assert 'data-testid="report-bundle-manifest-reports-panel"' in manifest_html
        assert 'data-testid="report-bundle-manifest-triage-panel"' in manifest_html
        assert "002-npm-diagnostics-report.html" in manifest_html
        assert "triage-summary.html" in manifest_html
        _assert_verify_bundle_command(output_dir)
        _assert_verify_bundle_fixture(output_dir)
        validation = _run_cli(["validate", "--path", str(output_dir)])
        assert validation["schema"] == "edgp.validation.report.v1"
        assert validation["ok"] is True
        assert validation["targetType"] == "report-bundle"
        assert validation["bundleVerification"]["ok"] is True
        assert validation["triageSummary"]["status"] == "warn"
        verification_report_path = Path(temp_dir) / "report-bundle-verification.json"
        verification_report_path.write_text(
            json.dumps(validation["bundleVerification"]), encoding="utf-8"
        )
        verification_html_path = Path(temp_dir) / "report-bundle-verification.html"
        completed_verification_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                str(verification_report_path),
                "--output",
                str(verification_html_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert Path(completed_verification_report.stdout.strip()) == verification_html_path
        verification_html = verification_html_path.read_text(encoding="utf-8")
        assert 'data-testid="report-bundle-verification-report-panel"' in verification_html
        assert "manifest.json" in verification_html
        completed_validation_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "validate",
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
        assert completed_validation_text.stdout.strip() == (
            "OK targetType=report-bundle failures=0 "
            "contract=edgp.report.bundle.v1 triageStatus=warn"
        )
        submission_plan_path = Path(temp_dir) / "bundle-submission-plan.json"
        submission_plan = _run_cli(
            [
                "plan-bundle-submission",
                "--path",
                str(output_dir),
                "--target",
                "workbench",
                "--endpoint",
                "https://workbench.example/api/bundles",
                "--output",
                str(submission_plan_path),
            ]
        )
        assert submission_plan["schema"] == "edgp.report.bundle.submission_plan.v1"
        assert submission_plan["ok"] is True
        assert submission_plan["source"]["inputType"] == "directory"
        assert submission_plan["summary"]["reports"] == 2
        assert [artifact["role"] for artifact in submission_plan["artifacts"]] == [
            "manifest",
            "index",
            "report-html",
            "report-html",
            "triage-html",
            "triage-source",
        ]
        submission_plan_validation = _run_cli(
            ["validate", "--path", str(submission_plan_path)]
        )
        assert submission_plan_validation["ok"] is True
        assert (
            submission_plan_validation["contract"]
            == "edgp.report.bundle.submission_plan.v1"
        )
        completed_submission_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "plan-bundle-submission",
                "--path",
                str(output_dir),
                "--target",
                "generic",
                "--endpoint",
                "https://collector.example/upload",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed_submission_text.stdout.startswith(
            "OK target=generic reports=2 artifacts=6"
        )
        archive_path = Path(temp_dir) / "bundle.tar.gz"
        archive_report = _run_cli(
            [
                "archive-bundle",
                "--path",
                str(output_dir),
                "--output",
                str(archive_path),
            ]
        )
        assert archive_report["schema"] == "edgp.report.bundle.archive.v1"
        assert archive_report["ok"] is True
        assert archive_report["bundleSha256"] == manifest["bundleSha256"]
        assert archive_report["archiveSha256"] == hashlib.sha256(
            archive_path.read_bytes()
        ).hexdigest()
        assert archive_report["summary"]["files"] == 6
        assert archive_report["summary"]["verificationFailures"] == 0
        assert archive_report["verification"]["ok"] is True
        archive_report_path = Path(temp_dir) / "report-bundle-archive.json"
        archive_report_path.write_text(json.dumps(archive_report), encoding="utf-8")
        archive_html_path = Path(temp_dir) / "report-bundle-archive.html"
        completed_archive_report = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "report",
                "--input",
                str(archive_report_path),
                "--output",
                str(archive_html_path),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert Path(completed_archive_report.stdout.strip()) == archive_html_path
        archive_html = archive_html_path.read_text(encoding="utf-8")
        assert 'data-testid="report-bundle-archive-panel"' in archive_html
        assert str(archive_path) in archive_html
        archive_verification = _run_cli(
            [
                "verify-bundle-archive",
                "--path",
                str(archive_path),
            ]
        )
        assert archive_verification["schema"] == "edgp.report.bundle.archive.v1"
        assert archive_verification["ok"] is True
        assert archive_verification["archiveSha256"] == archive_report["archiveSha256"]
        assert archive_verification["bundleSha256"] == manifest["bundleSha256"]
        assert archive_verification["summary"]["files"] == 6
        assert archive_verification["summary"]["verificationFailures"] == 0
        completed_archive_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "archive-bundle",
                "--path",
                str(output_dir),
                "--output",
                str(archive_path),
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed_archive_text.stdout.startswith("OK files=6 bytes=")
        assert " verificationFailures=0 " in completed_archive_text.stdout
        assert " archiveSha256=" in completed_archive_text.stdout
        completed_archive_verify_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "verify-bundle-archive",
                "--path",
                str(archive_path),
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed_archive_verify_text.stdout.startswith("OK files=6 bytes=")
        assert " verificationFailures=0 " in completed_archive_verify_text.stdout
        archive_validation = _run_cli(["validate", "--path", str(archive_path)])
        assert archive_validation["schema"] == "edgp.validation.report.v1"
        assert archive_validation["ok"] is True
        assert archive_validation["targetType"] == "report-bundle-archive"
        assert archive_validation["contract"] == "edgp.report.bundle.archive.v1"
        assert archive_validation["bundleArchiveVerification"]["ok"] is True
        assert (
            archive_validation["bundleArchiveVerification"]["archiveSha256"]
            == archive_report["archiveSha256"]
        )
        archive_submission_plan = _run_cli(
            [
                "plan-bundle-submission",
                "--path",
                str(archive_path),
                "--target",
                "workbench",
                "--endpoint",
                "https://workbench.example/api/bundles",
            ]
        )
        assert archive_submission_plan["ok"] is True
        assert archive_submission_plan["source"]["inputType"] == "archive"
        assert (
            archive_submission_plan["source"]["archiveSha256"]
            == archive_report["archiveSha256"]
        )
        assert [artifact["role"] for artifact in archive_submission_plan["artifacts"]] == [
            "manifest",
            "index",
            "report-html",
            "report-html",
            "triage-html",
            "triage-source",
        ]
        completed_archive_validation_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "validate",
                "--path",
                str(archive_path),
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed_archive_validation_text.stdout.strip() == (
            "OK targetType=report-bundle-archive failures=0 "
            "contract=edgp.report.bundle.archive.v1 triageStatus=warn"
        )
        archive_triage = _run_cli(["triage-summary", "--bundle", str(archive_path)])
        assert archive_triage["schema"] == "edgp.triage.summary.v1"
        assert archive_triage["source"]["kind"] == "bundle-archive"
        assert archive_triage["source"]["archiveSha256"] == archive_report["archiveSha256"]
        assert archive_triage["source"]["bundleSha256"] == manifest["bundleSha256"]
        assert archive_triage["bundle"]["sourceKind"] == "edgp-json"
        assert archive_triage["status"] == "warn"
        assert archive_triage["summary"]["reports"] == 2
        assert archive_triage["summary"]["npmDiagnosticsReports"] == 1
        completed_archive_triage_gate = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "triage-summary",
                "--bundle",
                str(archive_path),
                "--fail-on-status",
                "warn",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed_archive_triage_gate.returncode == 2
        gated_archive_triage = json.loads(completed_archive_triage_gate.stdout)
        assert gated_archive_triage["source"]["kind"] == "bundle-archive"
        completed_validation_gate = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "validate",
                "--path",
                str(output_dir),
                "--fail-on-status",
                "warn",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed_validation_gate.returncode == 2
        gated_validation = json.loads(completed_validation_gate.stdout)
        assert gated_validation["ok"] is True
        assert gated_validation["triageSummary"]["status"] == "warn"
        assert manifest["schema"] == "edgp.report.bundle.v1"
        assert manifest["bundle"]["sourceKind"] == "edgp-json"
        assert manifest["bundle"]["command"].startswith("edgp report-bundle ")
        assert manifest["bundleSha256"][:12] in index_html
        assert manifest["reports"][1]["href"] == "002-npm-diagnostics-report.html"
        assert manifest["triageSummary"]["href"] == "triage-summary.html"
        triage = json.loads(
            (output_dir / "triage-summary.json").read_text(encoding="utf-8")
        )
        assert triage["schema"] == "edgp.triage.summary.v1"
        assert triage["status"] == "warn"
        assert triage["summary"]["reports"] == 2
        npm_html = (output_dir / "002-npm-diagnostics-report.html").read_text(
            encoding="utf-8"
        )
        assert 'data-testid="npm-unresolved-panel"' in npm_html


def _assert_bundle_catalog() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        graph_bundle = temp_path / "graph-bundle"
        diagnostics_bundle = temp_path / "diagnostics-bundle"
        diagnostics_archive = temp_path / "diagnostics-bundle.tar.gz"
        catalog_dir = temp_path / "catalog"
        catalog_archive = temp_path / "catalog.tar.gz"
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
                str(graph_bundle),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "npm-diagnostics-bundle",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
                "--output-dir",
                str(diagnostics_bundle),
                "--triage-summary",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "archive-bundle",
                "--path",
                str(diagnostics_bundle),
                "--output",
                str(diagnostics_archive),
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "bundle-catalog",
                "--bundle",
                str(graph_bundle),
                "--bundle",
                str(diagnostics_archive),
                "--output-dir",
                str(catalog_dir),
                "--archive-output",
                str(catalog_archive),
                "--triage-summary",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.stdout.strip() == str(catalog_dir / "index.html")
        manifest = json.loads((catalog_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, catalog_dir)
        _assert_verify_bundle_command(catalog_dir)
        assert manifest["bundle"]["sourceKind"] == "bundle-catalog"
        assert manifest["reports"][0]["href"] == "001-bundle-catalog.html"
        assert manifest["reports"][0]["schema"] == "edgp.bundle.catalog.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        catalog = json.loads(
            (catalog_dir / "bundle-catalog.json").read_text(encoding="utf-8")
        )
        assert catalog["schema"] == "edgp.bundle.catalog.v1"
        assert catalog["summary"]["bundles"] == 2
        assert catalog["summary"]["okBundles"] == 2
        assert catalog["summary"]["triageWarn"] == 1
        assert catalog["bundles"][0]["inputType"] == "directory"
        assert catalog["bundles"][1]["inputType"] == "archive"
        assert catalog["bundles"][1]["path"] == str(diagnostics_archive.resolve())
        triage = json.loads(
            (catalog_dir / "triage-summary.json").read_text(encoding="utf-8")
        )
        assert triage["schema"] == "edgp.triage.summary.v1"
        assert triage["status"] == "warn"
        assert triage["summary"]["catalogTriageWarn"] == 1
        catalog_html = (catalog_dir / "001-bundle-catalog.html").read_text(
            encoding="utf-8"
        )
        assert 'data-testid="bundle-catalog-filter-panel"' in catalog_html
        assert 'data-bundle-catalog-search' in catalog_html
        assert "catalogQuery" in catalog_html
        assert "catalogSource" in catalog_html
        assert "catalogStatus" in catalog_html
        assert "catalogProblems" in catalog_html
        assert 'data-testid="bundle-catalog-bundles-panel"' in catalog_html
        archive_report = _run_cli(["verify-bundle-archive", "--path", str(catalog_archive)])
        assert archive_report["schema"] == "edgp.report.bundle.archive.v1"
        assert archive_report["ok"] is True
        assert archive_report["bundleSha256"] == manifest["bundleSha256"]
        archive_validation = _run_cli(["validate", "--path", str(catalog_archive)])
        assert archive_validation["targetType"] == "report-bundle-archive"
        assert archive_validation["triageSummary"]["status"] == "warn"
        archive_triage = _run_cli(["triage-summary", "--bundle", str(catalog_archive)])
        assert archive_triage["source"]["kind"] == "bundle-archive"
        assert archive_triage["summary"]["catalogTriageWarn"] == 1


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
                "--fail-on-status",
                "warn",
            ],
            check=False,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 2
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
        assert manifest["triageSummary"]["href"] == "triage-summary.html"
        triage = json.loads(
            (output_dir / "triage-summary.json").read_text(encoding="utf-8")
        )
        assert triage["schema"] == "edgp.triage.summary.v1"
        assert triage["status"] == "warn"


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
                "--triage-summary",
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
    payload = _run_cli(["benchmark", "--nodes", "64", "--fanout", "3", "--backend", "auto"])
    assert payload["schema"] == "edgp.benchmark.v1"
    assert payload["stats"]["nodes"] == 64
    assert payload["stats"]["edges"] == 186
    assert payload["stats"]["reachableFromRoot"] == 63
    assert payload["accelerators"]["requestedBackend"] == "auto"
    benchmark_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "benchmark",
            "--nodes",
            "64",
            "--fanout",
            "3",
            "--backend",
            "auto",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert benchmark_text.startswith("OK schema=edgp.benchmark.v1")
    assert "nodes=64" in benchmark_text
    assert "edges=186" in benchmark_text
    assert "selectedBackend=" in benchmark_text

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "performance-report-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "performance-report-bundle",
                "--scenario",
                "16:2",
                "--scenario",
                "32:3",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "performance-report"
        assert manifest["reports"][0]["href"] == "001-performance-report.html"
        assert manifest["reports"][0]["schema"] == "edgp.performance.report.v1"
        assert manifest["triageSummary"]["source"] == "triage-summary.json"
        report = json.loads(
            (output_dir / "performance-report.json").read_text(encoding="utf-8")
        )
        assert report["schema"] == "edgp.performance.report.v1"
        assert report["summary"]["scenarios"] == 2
        assert report["summary"]["allContiguous"] is True
        assert 'data-testid="performance-results-panel"' in (
            output_dir / "001-performance-report.html"
        ).read_text(encoding="utf-8")
        text_output_dir = Path(temp_dir) / "performance-report-bundle-text"
        text_completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "performance-report-bundle",
                "--scenario",
                "16:2",
                "--scenario",
                "32:3",
                "--output-dir",
                str(text_output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert text_completed.stdout.startswith("BUNDLE index=")
        assert "performance-report-bundle-text/index.html" in text_completed.stdout
        assert "sourceKind=performance-report" in text_completed.stdout


def _assert_csr_artifact() -> None:
    from src.core_graph.artifacts import load_frozen_csr_artifact

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "csr-artifact"
        manifest = _run_cli(
            [
                "csr-artifact",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(output_dir),
            ]
        )
        loaded = load_frozen_csr_artifact(output_dir)
        assert manifest["schema"] == "edgp.csr.artifact.v1"
        assert manifest["nodes"] == 3
        assert manifest["edges"] == 2
        assert manifest["storageProfile"]["layout"] == "numpy.int32.c_contiguous"
        assert manifest["storageProfile"]["readOnly"] is True
        assert manifest["storageProfile"]["memoryMappable"] is True
        assert manifest["storageProfile"]["digestAlgorithm"] == "sha256"
        assert manifest["storageProfile"]["digestCoverage"] == [
            "values",
            "column_indices",
            "row_pointers",
            "reverse_values",
            "reverse_column_indices",
            "reverse_row_pointers",
        ]
        assert (output_dir / "manifest.json").exists()
        assert (output_dir / "column_indices.npy").exists()
        assert loaded.storage_profile()["memoryMapped"] is True
        csr_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "csr-artifact",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(output_dir / "text-artifact"),
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert csr_text.startswith("OK schema=edgp.csr.artifact.v1")
        assert "nodes=3" in csr_text
        assert "memoryMappable=true" in csr_text
        assert loaded.reachable_dependencies("app==1.0.0") == [
            "lib==2.0.0",
            "core==1.0.0",
        ]
        validation = _run_cli(["validate", "--path", str(output_dir)])
        assert validation["ok"] is True
        assert validation["targetType"] == "csr-artifact"
        assert validation["contract"] == "edgp.csr.artifact.v1"
        assert validation["csrArtifact"]["nodes"] == 3
        assert validation["csrArtifact"]["storageProfile"]["memoryMapped"] is True
        manifest_path = output_dir / "manifest.json"
        tampered_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        tampered_manifest["storageProfile"]["totalBytes"] += 4
        manifest_path.write_text(json.dumps(tampered_manifest), encoding="utf-8")
        validation_failure = _run_cli_allow_failure(["validate", "--path", str(output_dir)])
        assert validation_failure["ok"] is False
        assert validation_failure["targetType"] == "csr-artifact"
        assert (
            validation_failure["failures"][0]["code"]
            == "csrArtifact.verificationFailed"
        )
        try:
            load_frozen_csr_artifact(output_dir)
        except ValueError as exc:
            assert "storageProfile mismatch: totalBytes" in str(exc)
        else:
            raise AssertionError("tampered CSR storageProfile was accepted")


def _assert_accelerator_status() -> None:
    payload = _run_cli(["accelerator-status", "--backend", "auto"])
    assert payload["requestedBackend"] == "auto"
    assert payload["selectedBackend"] in {"python", "numba"}
    assert payload["numba"]["installExtra"] == ".[fast]"
    assert payload["graphblas"]["installExtra"] == ".[graphblas]"
    assert payload["graphblas"]["storageContract"] == "frozen CSR remains canonical"
    status_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "accelerator-status",
            "--backend",
            "auto",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert status_text.startswith("OK command=accelerator-status")
    assert "selectedBackend=" in status_text
    assert "graphblasAvailable=" in status_text


def _assert_parallel_query() -> None:
    payload = _run_cli(
        [
            "parallel-query",
            "--snapshot",
            "tests/fixtures/snapshot-right.json",
            "--query",
            "dependencies:app==1.0.0",
            "--query",
            "dependents:core==1.0.0",
            "--workers",
            "2",
            "--backend",
            "auto",
        ]
    )
    assert payload["schema"] == "edgp.parallel.query.report.v1"
    assert payload["summary"]["queries"] == 2
    assert payload["summary"]["workers"] == 2
    assert payload["results"][0]["nodes"] == ["lib==2.0.0", "core==1.0.0"]
    assert payload["results"][1]["nodes"] == ["lib==2.0.0", "app==1.0.0"]
    query_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "parallel-query",
            "--snapshot",
            "tests/fixtures/snapshot-right.json",
            "--query",
            "dependencies:app==1.0.0",
            "--query",
            "dependents:core==1.0.0",
            "--workers",
            "2",
            "--backend",
            "auto",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert query_text.startswith("OK schema=edgp.parallel.query.report.v1")
    assert "queries=2" in query_text
    assert "totalResultNodes=4" in query_text


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
        albs_build_url = (REPO_ROOT / "tests" / "fixtures" / "albs-build.json").as_uri()
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
                "--advisories",
                "tests/fixtures/rpm-advisories.json",
                "--public-advisory-feed",
                "tests/fixtures/public-osv.json",
                "--albs-build-url",
                albs_build_url,
                "--libsolv-transaction",
                "tests/fixtures/libsolv-transaction.txt",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["reports"][2]["href"] == "003-advisory-report.html"
        assert manifest["reports"][3]["href"] == "004-public-advisory-feed.html"
        assert manifest["reports"][4]["href"] == "005-public-advisory-report.html"
        assert manifest["reports"][5]["href"] == "006-rpm-albs-provenance.html"
        assert manifest["reports"][6]["href"] == "007-libsolv-bridge.html"
        assert manifest["triageSummary"]["href"] == "triage-summary.html"
        graph = json.loads(
            (output_dir / "rpm-installed-graph.json").read_text(encoding="utf-8")
        )
        assert graph["schema"] == "edgp.graph.snapshot.v1"
        assert graph["root"] == "rpm-installed==local"
        libsolv = json.loads(
            (output_dir / "libsolv-bridge.json").read_text(encoding="utf-8")
        )
        assert libsolv["schema"] == "edgp.libsolv.bridge.v1"
        assert libsolv["graphContext"]["schema"] == "edgp.graph.snapshot.v1"
        advisory = json.loads(
            (output_dir / "advisory-report.json").read_text(encoding="utf-8")
        )
        assert advisory["schema"] == "edgp.advisory.report.v1"
        public_feed = json.loads(
            (output_dir / "public-advisory-feed.json").read_text(encoding="utf-8")
        )
        assert public_feed["schema"] == "edgp.public.advisory_feed.v1"
        public_advisory = json.loads(
            (output_dir / "public-advisory-report.json").read_text(encoding="utf-8")
        )
        assert public_advisory["schema"] == "edgp.advisory.report.v1"
        provenance = json.loads(
            (output_dir / "rpm-albs-provenance.json").read_text(encoding="utf-8")
        )
        assert provenance["schema"] == "edgp.rpm.albs_provenance.v1"
        provenance_html = (output_dir / "006-rpm-albs-provenance.html").read_text(
            encoding="utf-8"
        )
        assert 'data-testid="rpm-albs-provenance-matches-panel"' in provenance_html
        triage = json.loads(
            (output_dir / "triage-summary.json").read_text(encoding="utf-8")
        )
        assert triage["schema"] == "edgp.triage.summary.v1"
        assert triage["source"]["kind"] == "report-bundle-input"


def _assert_rpm_albs_provenance_bundle() -> None:
    completed_provenance_text = subprocess.run(
        [
            sys.executable,
            "-B",
            "-m",
            "src.cli",
            "rpm-albs-provenance",
            "--path",
            "tests/fixtures/albs-build.json",
            "--rpm-limit",
            "5",
            "--max-requirements",
            "10",
            "--format",
            "text",
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    provenance_text = completed_provenance_text.stdout.strip()
    assert provenance_text.startswith(
        "RPM_ALBS_PROVENANCE schema=edgp.rpm.albs_provenance.v1"
    )
    assert "installedPackages=" in provenance_text
    assert "albsArtifacts=" in provenance_text
    assert "matchedPackages=" in provenance_text
    assert "unmatchedPackages=" in provenance_text

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "rpm-albs-provenance-bundle"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "rpm-albs-provenance-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
                "--rpm-limit",
                "5",
                "--max-requirements",
                "10",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
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
        assert manifest["bundle"]["sourceKind"] == "rpm-albs-provenance"
        assert manifest["bundle"]["command"].startswith(
            "edgp rpm-albs-provenance-bundle "
        )
        assert manifest["reports"][0]["href"] == "001-rpm-albs-provenance.html"
        assert manifest["reports"][0]["schema"] == "edgp.rpm.albs_provenance.v1"
        assert manifest["triageSummary"]["href"] == "triage-summary.html"
        provenance = json.loads(
            (output_dir / "rpm-albs-provenance.json").read_text(encoding="utf-8")
        )
        assert provenance["schema"] == "edgp.rpm.albs_provenance.v1"
        assert provenance["root"] == "rpm-installed==local"
        html = (output_dir / "001-rpm-albs-provenance.html").read_text(
            encoding="utf-8"
        )
        assert 'data-testid="rpm-albs-provenance-matches-panel"' in html
        assert 'data-testid="rpm-albs-provenance-unmatched-panel"' in html
        text_output_dir = Path(temp_dir) / "rpm-albs-provenance-bundle-text"
        completed_text = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "src.cli",
                "rpm-albs-provenance-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
                "--rpm-limit",
                "5",
                "--max-requirements",
                "10",
                "--output-dir",
                str(text_output_dir),
                "--triage-summary",
                "--format",
                "text",
            ],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        provenance_bundle_text = completed_text.stdout.strip()
        assert provenance_bundle_text.startswith("BUNDLE ")
        assert "sourceKind=rpm-albs-provenance" in provenance_bundle_text
        assert "reports=1" in provenance_bundle_text
        assert "triageStatus=pass" in provenance_bundle_text


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
        (
            "python translation unit descriptions",
            _assert_python_translation_unit_docstrings,
        ),
        ("lockfile snapshot", _assert_lockfile_snapshot),
        ("npm diagnostics", _assert_npm_diagnostics),
        ("validate command", _assert_validate_command),
        ("report bundle manifest schema", _assert_report_bundle_manifest_schema_document),
        (
            "report bundle verification schema",
            _assert_report_bundle_verification_schema_document,
        ),
        ("report json schemas", _assert_report_json_schemas_document),
        ("report schema docs local links", _assert_report_schema_docs_local_links),
        ("architecture doc local links", _assert_architecture_doc_local_links),
        ("architecture doc headings", _assert_architecture_doc_headings),
        ("architecture doc quick links", _assert_architecture_doc_quick_links),
        (
            "architecture doc extraction artifacts",
            _assert_architecture_doc_extraction_artifacts,
        ),
        ("architecture doc markdown lists", _assert_architecture_doc_markdown_lists),
        ("schema index", _assert_schema_index_document),
        ("submission plan index", _assert_submission_plan_index),
        ("failure example index", _assert_failure_example_index_document),
        (
            "validation failure example quick links",
            _assert_validation_failure_examples_quick_links,
        ),
        (
            "validation failure example local links",
            _assert_validation_failure_examples_local_links,
        ),
        (
            "readme validation guide anchors",
            _assert_readme_validation_guide_anchors,
        ),
        (
            "readme validation failure fixture links",
            _assert_readme_validation_failure_fixture_links,
        ),
        (
            "readme architecture research link",
            _assert_readme_architecture_research_link,
        ),
        (
            "readme architecture research anchors",
            _assert_readme_architecture_research_anchors,
        ),
        (
            "readme local documentation links",
            _assert_readme_local_documentation_links,
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
        ("export batch", _assert_export_batch),
        ("dot bundle", _assert_dot_bundle),
        ("albs build snapshot", _assert_albs_build_snapshot),
        ("albs build bundle", _assert_albs_build_bundle),
        ("public vertical reports", _assert_public_vertical_reports),
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
        (
            "browser smoke bundle catalog filters",
            _assert_browser_smoke_bundle_catalog_filters,
        ),
        (
            "browser smoke graph diff filters",
            _assert_browser_smoke_graph_diff_filters,
        ),
        (
            "browser smoke graph diff tree filters",
            _assert_browser_smoke_graph_diff_tree_filters,
        ),
        ("impact html report", _assert_impact_html_report),
        ("advisory html report", _assert_advisory_html_report),
        ("npm diagnostics html report", _assert_npm_diagnostics_html_report),
        ("report bundle", _assert_report_bundle),
        ("bundle catalog", _assert_bundle_catalog),
        ("verify bundle tamper detection", _assert_verify_bundle_detects_tampering),
        (
            "bundle validation failure fixtures",
            _assert_bundle_validation_failure_fixtures,
        ),
        ("npm bundle", _assert_npm_bundle),
        ("npm bundle impact advisory", _assert_npm_bundle_with_impact_and_advisory),
        ("synthetic benchmark", _assert_benchmark),
        ("accelerator status", _assert_accelerator_status),
        ("csr artifact", _assert_csr_artifact),
        ("parallel query", _assert_parallel_query),
    ]
    if args.include_rpm_installed:
        checks.append(("installed rpm graph", _assert_rpm_installed))
        checks.append(("installed rpm bundle", _assert_rpm_installed_bundle))
        checks.append(
            ("rpm albs provenance bundle", _assert_rpm_albs_provenance_bundle)
        )

    for label, check in checks:
        check()
        print(f"ok - {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
