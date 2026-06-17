"""Generate a deterministic provenance catalog for committed test fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"
OUTPUT_PATH = FIXTURE_DIR / "fixture-provenance.json"
SCHEMA = "edgp.fixture.provenance.v1"

ALMALINUX_REPO_URL = "https://repo.almalinux.org/almalinux/9/AppStream/x86_64/os/"
ALBS_BUILD_URL = "https://build.almalinux.org/api/v1/builds/17812/"

PUBLIC_INPUTS: list[dict[str, Any]] = [
    {
        "path": "rpm-primary.xml",
        "kind": "public-derived-source",
        "source": "AlmaLinux 9 AppStream x86_64 primary.xml.gz excerpt",
        "sourceUrl": ALMALINUX_REPO_URL,
        "refreshedAt": "2026-06-17",
        "notes": (
            "Curated public RPM metadata excerpt preserving real nginx, "
            "nginx-core, and nginx-filesystem package metadata."
        ),
    },
    {
        "path": "rpm-primary-updated.xml",
        "kind": "deterministic-public-derived-variant",
        "source": "AlmaLinux 9 AppStream x86_64 primary.xml.gz excerpt",
        "sourceUrl": ALMALINUX_REPO_URL,
        "derivedFrom": ["tests/fixtures/rpm-primary.xml"],
        "refreshedAt": "2026-06-17",
        "notes": "Companion snapshot used to exercise repository diff behavior.",
    },
    {
        "path": "repodata/repomd.xml",
        "kind": "local-pointer-fixture",
        "source": "Local repomd.xml pointer for the committed primary excerpt",
        "sourceUrl": ALMALINUX_REPO_URL,
        "derivedFrom": ["tests/fixtures/rpm-primary.xml"],
        "refreshedAt": "2026-06-17",
        "notes": "Keeps repodata discovery tests offline and deterministic.",
    },
    {
        "path": "albs-build.json",
        "kind": "public-derived-source",
        "source": "Public ALBS build 17812 API excerpt",
        "sourceUrl": ALBS_BUILD_URL,
        "refreshedAt": "2026-06-17",
        "notes": (
            "Compact excerpt preserving real build ID, artifacts, build tasks, "
            "sign tasks, and package names."
        ),
    },
    {
        "path": "albs-build-updated.json",
        "kind": "deterministic-public-derived-variant",
        "source": "Public ALBS build 17812 API excerpt",
        "sourceUrl": ALBS_BUILD_URL,
        "derivedFrom": ["tests/fixtures/albs-build.json"],
        "refreshedAt": "2026-06-17",
        "notes": "Companion snapshot used for build diff and release coverage tests.",
    },
]

GENERATED_REPORTS: list[dict[str, Any]] = [
    {
        "path": "rpm-repository-summary.json",
        "reportSchema": "edgp.rpm.repository_summary.v1",
        "derivedFrom": ["tests/fixtures/rpm-primary.xml"],
    },
    {
        "path": "rpm-repository-diff.json",
        "reportSchema": "edgp.rpm.repository_diff.v1",
        "derivedFrom": [
            "tests/fixtures/rpm-primary.xml",
            "tests/fixtures/rpm-primary-updated.xml",
        ],
    },
    {
        "path": "albs-artifact-inventory.json",
        "reportSchema": "edgp.albs.artifact_inventory.v1",
        "derivedFrom": ["tests/fixtures/albs-build.json"],
    },
    {
        "path": "albs-build-timing.json",
        "reportSchema": "edgp.albs.build_timing.v1",
        "derivedFrom": ["tests/fixtures/albs-build.json"],
    },
    {
        "path": "albs-build-diff.json",
        "reportSchema": "edgp.albs.build_diff.v1",
        "derivedFrom": [
            "tests/fixtures/albs-build.json",
            "tests/fixtures/albs-build-updated.json",
        ],
    },
    {
        "path": "albs-log-intelligence.json",
        "reportSchema": "edgp.albs.log_intelligence.v1",
        "derivedFrom": ["tests/fixtures/albs-build-updated.json"],
    },
    {
        "path": "albs-release-completeness.json",
        "reportSchema": "edgp.albs.release_completeness.v1",
        "derivedFrom": [
            "tests/fixtures/albs-build.json",
            "tests/fixtures/albs-build-updated.json",
        ],
    },
    {
        "path": "rpm-albs-provenance.json",
        "reportSchema": "edgp.rpm.albs_provenance.v1",
        "derivedFrom": ["tests/fixtures/albs-build.json"],
        "notes": "Joins a tiny installed RPM graph to the public ALBS artifact excerpt.",
    },
    {
        "path": "libsolv-bridge.json",
        "reportSchema": "edgp.libsolv.bridge.v1",
        "derivedFrom": ["tests/fixtures/libsolv-transaction.txt"],
    },
    {
        "path": "real-data-coverage.json",
        "reportSchema": "edgp.real_data.coverage.v1",
        "derivedFrom": ["tests/fixtures/fixture-provenance.json"],
        "notes": (
            "Summarizes which committed fixtures are public-derived, generated, "
            "or intentionally synthetic."
        ),
    },
    {
        "path": "real-data-replacement-plan.json",
        "reportSchema": "edgp.real_data.replacement_plan.v1",
        "derivedFrom": ["tests/fixtures/real-data-coverage.json"],
        "notes": (
            "Ranks synthetic fixture groups that should move toward public "
            "evidence where doing so improves data fidelity."
        ),
    },
    {
        "path": "real-data-coverage-diff.json",
        "reportSchema": "edgp.real_data.coverage_diff.v1",
        "derivedFrom": ["tests/fixtures/real-data-coverage.json"],
        "notes": (
            "No-regression baseline for comparing public evidence coverage "
            "between two fixture snapshots."
        ),
    },
]

SYNTHETIC_GROUPS: list[dict[str, Any]] = [
    {
        "group": "npm lockfiles and registry mock",
        "kind": "synthetic-edge-case",
        "files": ["package-lock.json", "package-lock-conflict.json", "registry.json"],
        "reason": "Small lockfile topologies make duplicate and conflict assertions auditable.",
    },
    {
        "group": "Python and Rust lockfiles",
        "kind": "synthetic-edge-case",
        "files": ["poetry.lock", "Cargo.lock"],
        "reason": "Parser smoke inputs cover additional ecosystem formats offline.",
    },
    {
        "group": "Maven dependency trees",
        "kind": "synthetic-edge-case",
        "files": [
            "maven-tree.txt",
            "maven-tree-classifier.txt",
            "maven-tree-markers.txt",
            "maven-tree-packaging.txt",
        ],
        "reason": "Hand-sized snippets isolate classifier, scope, marker, and packaging behavior.",
    },
    {
        "group": "Generic graph and SBOM examples",
        "kind": "synthetic-edge-case",
        "files": [
            "snapshot-left.json",
            "snapshot-right.json",
            "graph-diff.json",
            "graph-diff-tree.json",
            "query-report.json",
            "impact-report.json",
            "sample-bom.json",
            "repograph.dot",
        ],
        "reason": "Tiny graphs keep traversal, diff, and export assertions readable.",
    },
    {
        "group": "Advisory and OSV-shaped samples",
        "kind": "synthetic-public-shape",
        "files": [
            "advisories.json",
            "advisory-report.json",
            "rpm-advisories.json",
            "rpm-repo-advisories.json",
            "public-osv.json",
            "public-osv-ranges.json",
            "public-osv-purl.json",
            "public-osv-cvss-score.json",
            "public-advisory-feed.json",
        ],
        "reason": "Shape-compatible advisory samples exercise severity and matching logic without live feeds.",
    },
    {
        "group": "Report and export bundle fixtures",
        "kind": "synthetic-validation-case",
        "files": [
            "bundle-catalog.json",
            "export-batch.json",
            "export-batch-archive.json",
            "export-batch-submission-plan.json",
            "export-batch-verification.json",
            "report-bundle-archive.json",
            "report-bundle-submission-plan.json",
            "report-bundle-verification.json",
            "submission-plan-index.json",
            "triage-summary.json",
        ],
        "reason": "Committed outputs document portable bundle, archive, and submission-plan contracts.",
    },
    {
        "group": "Validation failure examples",
        "kind": "synthetic-validation-case",
        "files": [
            "validation-failure-invalid-bundle-digest.json",
            "validation-failure-invalid-bundle-metadata.json",
            "validation-failure-invalid-bundle-source-kind.json",
            "validation-failure-invalid-index-path.json",
            "validation-failure-invalid-json-manifest.json",
            "validation-failure-invalid-manifest-missing-report-count.json",
            "validation-failure-invalid-manifest-schema.json",
            "validation-failure-invalid-manifest-type.json",
            "validation-failure-invalid-manifest-unknown-field.json",
            "validation-failure-invalid-report-count.json",
            "validation-failure-invalid-report-digest.json",
            "validation-failure-invalid-report-entry.json",
            "validation-failure-invalid-report-field.json",
            "validation-failure-invalid-report-href.json",
            "validation-failure-invalid-report-missing-title.json",
            "validation-failure-invalid-report-summary.json",
            "validation-failure-invalid-report-unknown-field.json",
            "validation-failure-invalid-reports-list.json",
            "validation-failure-missing-bundle-archive.json",
            "validation-failure-missing-bundle-html.json",
            "validation-failure-missing-bundle-source.json",
            "validation-failure-missing-edge-count.json",
            "validation-failure-missing-index.json",
            "validation-failure-missing-manifest.json",
            "validation-failure-source-digest-mismatch.json",
            "validation-failure-tampered-bundle-manifest.json",
            "validation-failure-tampered-bundle-member.json",
            "validation-failure-unsupported-schema.json",
        ],
        "reason": "Negative fixtures make validator behavior reviewable and reproducible.",
    },
    {
        "group": "Performance, CSR, and license reports",
        "kind": "synthetic-report",
        "files": [
            "csr-artifact-manifest.json",
            "license-report.json",
            "parallel-query-report.json",
            "performance-report.json",
            "npm-diagnostics-report.json",
        ],
        "reason": "Stable report samples cover static rendering and schema contracts.",
    },
]


def build_fixture_provenance(fixture_dir: Path = FIXTURE_DIR) -> dict[str, Any]:
    """Build the committed fixture provenance catalog."""

    entries = [
        _entry(fixture_dir, item)
        for item in [*PUBLIC_INPUTS, *_generated_report_inputs()]
    ]
    synthetic_groups = [_synthetic_group(fixture_dir, group) for group in SYNTHETIC_GROUPS]
    source_urls = [
        {
            "label": "AlmaLinux 9 AppStream x86_64 repository metadata",
            "url": ALMALINUX_REPO_URL,
            "access": "public",
            "refreshedAt": "2026-06-17",
        },
        {
            "label": "AlmaLinux Build System build 17812 API",
            "url": ALBS_BUILD_URL,
            "access": "public",
            "refreshedAt": "2026-06-17",
        },
    ]
    cataloged_files = {
        str(entry["path"])
        for entry in entries
    } | {
        file_path
        for group in synthetic_groups
        for file_path in group.get("files", [])
        if isinstance(file_path, str)
    }
    return {
        "schema": SCHEMA,
        "generatedBy": "scripts/generate_fixture_provenance.py",
        "fixtureRoot": _repo_label(fixture_dir),
        "summary": {
            "publicDerivedSources": sum(
                1 for entry in entries if entry["kind"] == "public-derived-source"
            ),
            "deterministicPublicDerivedVariants": sum(
                1
                for entry in entries
                if entry["kind"] == "deterministic-public-derived-variant"
            ),
            "generatedPublicReports": sum(
                1 for entry in entries if entry["kind"] == "generated-public-report"
            ),
            "syntheticGroups": len(synthetic_groups),
            "catalogedFiles": len(cataloged_files),
            "sourceUrls": len(source_urls),
        },
        "sourceUrls": source_urls,
        "entries": entries,
        "syntheticGroups": synthetic_groups,
        "refresh": {
            "commands": [
                "python -B scripts/generate_public_fixture_reports.py",
                "python -B scripts/generate_fixture_provenance.py",
            ],
            "checkCommands": [
                "python -B scripts/generate_public_fixture_reports.py --check",
                "python -B scripts/generate_fixture_provenance.py --check",
            ],
            "checkedBy": [
                "tests/test_public_fixture_freshness.py",
                "tests/test_fixture_provenance.py",
            ],
        },
    }


def write_fixture_provenance(
    output_path: Path = OUTPUT_PATH,
    *,
    fixture_dir: Path = FIXTURE_DIR,
) -> Path:
    """Write the deterministic fixture provenance report."""

    output_path.write_text(
        json.dumps(build_fixture_provenance(fixture_dir), indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return output_path


def check_fixture_provenance(
    output_path: Path = OUTPUT_PATH,
    *,
    fixture_dir: Path = FIXTURE_DIR,
) -> bool:
    """Return true when the committed fixture provenance report is current."""

    try:
        actual = json.loads(output_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return actual == build_fixture_provenance(fixture_dir)


def _generated_report_inputs() -> list[dict[str, Any]]:
    return [
        {
            **item,
            "kind": "generated-public-report",
            "generator": "scripts/generate_public_fixture_reports.py",
        }
        for item in GENERATED_REPORTS
    ]


def _entry(fixture_dir: Path, item: dict[str, Any]) -> dict[str, Any]:
    path = fixture_dir / str(item["path"])
    entry = {key: value for key, value in item.items() if key != "path"}
    entry.update(_file_record(path))
    return entry


def _synthetic_group(fixture_dir: Path, group: dict[str, Any]) -> dict[str, Any]:
    files = [_file_record(fixture_dir / file_name) for file_name in group["files"]]
    return {
        "group": group["group"],
        "kind": group["kind"],
        "reason": group["reason"],
        "fileCount": len(files),
        "files": [file_record["path"] for file_record in files],
        "sha256": _group_digest(files),
    }


def _file_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    return {
        "path": _repo_label(path),
        "bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _group_digest(files: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for file_record in sorted(files, key=lambda item: str(item["path"])):
        digest.update(str(file_record["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(file_record["sha256"]).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def _repo_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=FIXTURE_DIR,
        help="directory containing committed test fixtures",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help="fixture provenance report path",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the committed fixture provenance report is stale",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fixture_dir = args.fixture_dir.resolve()
    output_path = args.output.resolve()
    if args.check:
        if check_fixture_provenance(output_path, fixture_dir=fixture_dir):
            return 0
        print(f"{output_path} is out of date")
        return 1

    print(write_fixture_provenance(output_path, fixture_dir=fixture_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
