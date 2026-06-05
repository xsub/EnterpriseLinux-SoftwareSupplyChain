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
REPORT_BUNDLE_SCHEMA_PATH = (
    REPO_ROOT / "docs" / "schemas" / "edgp.report.bundle.v1.schema.json"
)


def _run_cli(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "src.cli", *args],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


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


def _load_report_bundle_manifest_schema() -> dict[str, Any]:
    return json.loads(REPORT_BUNDLE_SCHEMA_PATH.read_text(encoding="utf-8"))


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


def _assert_verify_bundle_command(output_dir: Path) -> None:
    payload = _run_cli(["verify-bundle", "--path", str(output_dir)])
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


def _assert_verify_bundle_fixture(output_dir: Path) -> None:
    payload = _run_cli(["verify-bundle", "--path", str(output_dir)])
    fixture = json.loads(
        (REPO_ROOT / "tests/fixtures/report-bundle-verification.json").read_text(
            encoding="utf-8"
        )
    )
    assert _normalize_verification_report(payload) == fixture


def _normalize_verification_report(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["bundleDir"] = "<bundle-dir>"
    normalized["bundleSha256"] = "<bundleSha256>"
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
        assert "EDGP Snapshot Report - app==1.0.0" in html


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
        assert "002-npm-diagnostics-report.html" in index_html
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        _assert_report_bundle_manifest_contract(manifest, output_dir)
        _assert_verify_bundle_command(output_dir)
        _assert_verify_bundle_fixture(output_dir)
        assert manifest["schema"] == "edgp.report.bundle.v1"
        assert manifest["bundle"]["sourceKind"] == "edgp-json"
        assert manifest["bundle"]["command"].startswith("edgp report-bundle ")
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
        assert payload["ok"] is False
        assert payload["failures"][0]["code"] == "htmlDigestMismatch"


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
        ("report bundle manifest schema", _assert_report_bundle_manifest_schema_document),
        ("poetry lockfile snapshot", _assert_poetry_lockfile_snapshot),
        ("poetry query", _assert_poetry_query),
        ("cargo lockfile snapshot", _assert_cargo_lockfile_snapshot),
        ("cargo query", _assert_cargo_query),
        ("maven tree snapshot", _assert_maven_tree_snapshot),
        ("maven tree query", _assert_maven_tree_query),
        ("maven classifier snapshot", _assert_maven_tree_classifier_snapshot),
        ("maven packaging snapshot", _assert_maven_tree_packaging_snapshot),
        ("maven marker snapshot", _assert_maven_tree_marker_snapshot),
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
        ("impact html report", _assert_impact_html_report),
        ("advisory html report", _assert_advisory_html_report),
        ("npm diagnostics html report", _assert_npm_diagnostics_html_report),
        ("report bundle", _assert_report_bundle),
        ("verify bundle tamper detection", _assert_verify_bundle_detects_tampering),
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
