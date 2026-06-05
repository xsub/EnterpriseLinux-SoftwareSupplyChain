"""Run dependency graph smoke checks without external test dependencies."""

from __future__ import annotations

import argparse
import compileall
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


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


def _assert_dot_snapshot() -> None:
    payload = _run_cli(["dot", "--path", "tests/fixtures/repograph.dot", "--format", "json"])
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "rpm"
    assert payload["stats"] == {"edges": 5, "nodes": 4}
    assert payload["rankings"]["mostDependedUpon"][0] == {
        "package": "glibc==unknown",
        "dependents": 3,
    }


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


def _assert_rpm_installed() -> None:
    payload = _run_cli(
        ["rpm-installed", "--limit", "5", "--max-requirements", "10", "--format", "json"]
    )
    assert payload["schema"] == "edgp.graph.snapshot.v1"
    assert payload["ecosystem"] == "rpm"
    assert payload["root"] == "rpm-installed==local"
    assert payload["stats"]["nodes"] >= 1


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
        ("poetry lockfile snapshot", _assert_poetry_lockfile_snapshot),
        ("poetry query", _assert_poetry_query),
        ("dot snapshot", _assert_dot_snapshot),
        ("sbom query", _assert_sbom_query),
        ("snapshot diff", _assert_snapshot_diff),
        ("impact report", _assert_impact_report),
        ("advisory overlay", _assert_advisory_overlay),
        ("rpm advisory overlay", _assert_rpm_advisory_overlay),
        ("html report", _assert_html_report),
    ]
    if args.include_rpm_installed:
        checks.append(("installed rpm graph", _assert_rpm_installed))

    for label, check in checks:
        check()
        print(f"ok - {label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
