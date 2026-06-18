"""Regenerate deterministic reports derived from public EDGP test fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.adapters.albs import AlbsBuildAdapter
from src.adapters.rpm_repository import RpmRepositoryAdapter
from src.albs_artifact_inventory import build_albs_artifact_inventory
from src.albs_build_diff import build_albs_build_diff_report
from src.albs_build_timing import build_albs_build_timing_report
from src.albs_log_intelligence import build_albs_log_intelligence_report
from src.albs_release_completeness import build_albs_release_completeness_report
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.libsolv_bridge import build_libsolv_bridge_report
from src.real_data_coverage import build_real_data_coverage_report
from src.real_data_coverage_diff import build_real_data_coverage_diff_report
from src.real_data_replacement_plan import build_real_data_replacement_plan_report
from src.real_data_replacement_plan_diff import (
    build_real_data_replacement_plan_diff_report,
)
from src.rpm_albs_provenance import build_rpm_albs_provenance_report
from src.rpm_repository_diff import build_rpm_repository_diff_report
from src.rpm_repository_summary import build_rpm_repository_summary_report
from scripts.generate_fixture_provenance import build_fixture_provenance

FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures"


def build_public_fixture_reports(
    fixture_dir: Path = FIXTURE_DIR,
) -> dict[Path, dict[str, Any]]:
    """Build every committed report fixture derived from public input fixtures."""

    left_albs = _json_fixture(fixture_dir / "albs-build.json")
    right_albs = _json_fixture(fixture_dir / "albs-build-updated.json")
    albs_graph = AlbsBuildAdapter().parse_file(fixture_dir / "albs-build.json")
    left_rpm_path = fixture_dir / "rpm-primary.xml"
    right_rpm_path = fixture_dir / "rpm-primary-updated.xml"
    left_rpm = RpmRepositoryAdapter().parse_primary(left_rpm_path)
    right_rpm = RpmRepositoryAdapter().parse_primary(right_rpm_path)
    installed_graph = _rpm_albs_fixture_graph()

    real_data_coverage = build_real_data_coverage_report(
        build_fixture_provenance(fixture_dir)
    )
    real_data_replacement_plan = build_real_data_replacement_plan_report(
        real_data_coverage
    )

    return {
        fixture_dir / "albs-artifact-inventory.json": build_albs_artifact_inventory(
            albs_graph.graph,
            root=albs_graph.root_identifier,
        ),
        fixture_dir / "albs-build-timing.json": build_albs_build_timing_report(
            left_albs
        ),
        fixture_dir / "albs-build-diff.json": build_albs_build_diff_report(
            left_albs,
            right_albs,
        ),
        fixture_dir / "albs-log-intelligence.json": (
            build_albs_log_intelligence_report(right_albs)
        ),
        fixture_dir / "albs-release-completeness.json": (
            build_albs_release_completeness_report([left_albs, right_albs])
        ),
        fixture_dir / "rpm-albs-provenance.json": build_rpm_albs_provenance_report(
            installed_graph,
            left_albs,
        ),
        fixture_dir / "rpm-repository-summary.json": (
            build_rpm_repository_summary_report(
                left_rpm.graph,
                root=left_rpm.root_identifier,
            )
        ),
        fixture_dir / "rpm-repository-diff.json": _rpm_repository_diff_report(
            left_rpm,
            right_rpm,
            left_rpm_path=left_rpm_path,
            right_rpm_path=right_rpm_path,
        ),
        fixture_dir / "libsolv-bridge.json": build_libsolv_bridge_report(
            fixture_dir / "libsolv-transaction.txt"
        ),
        fixture_dir / "real-data-coverage.json": real_data_coverage,
        fixture_dir / "real-data-replacement-plan.json": real_data_replacement_plan,
        fixture_dir / "real-data-replacement-plan-diff.json": (
            build_real_data_replacement_plan_diff_report(
                real_data_replacement_plan,
                real_data_replacement_plan,
                left_label="baseline",
                right_label="current",
            )
        ),
        fixture_dir / "real-data-coverage-diff.json": (
            build_real_data_coverage_diff_report(
                real_data_coverage,
                real_data_coverage,
                left_label="baseline",
                right_label="current",
            )
        ),
    }


def write_public_fixture_reports(
    fixture_dir: Path = FIXTURE_DIR,
) -> list[Path]:
    """Write regenerated public-derived report fixtures and return their paths."""

    generated = build_public_fixture_reports(fixture_dir)
    for path, payload in generated.items():
        path.write_text(_json(payload), encoding="utf-8")
    return sorted(generated)


def check_public_fixture_reports(
    fixture_dir: Path = FIXTURE_DIR,
) -> list[Path]:
    """Return public-derived report fixtures whose committed JSON is stale."""

    stale: list[Path] = []
    for path, payload in build_public_fixture_reports(fixture_dir).items():
        actual = _json_fixture(path)
        if actual != payload:
            stale.append(path)
    return sorted(stale)


def _rpm_albs_fixture_graph() -> CSRDependencyGraph:
    graph = CSRDependencyGraph()
    root = "rpm-installed==local"
    package_id = "nginx-core==1.20.1-16.el9_4.1"
    graph.add_vertex(
        root,
        metadata={"ecosystem": "rpm", "source": "rpmdb", "node_type": "root"},
    )
    graph.add_vertex(
        package_id,
        metadata={
            "ecosystem": "rpm",
            "source": "rpmdb",
            "arch": "x86_64",
            "source_rpm": "nginx-1.20.1-16.el9_4.1.src.rpm",
        },
    )
    graph.add_dependency_edge(root, package_id)
    return graph


def _rpm_repository_diff_report(
    left_rpm: Any,
    right_rpm: Any,
    *,
    left_rpm_path: Path,
    right_rpm_path: Path,
) -> dict[str, Any]:
    report = build_rpm_repository_diff_report(
        left_rpm.graph,
        right_rpm.graph,
        left_root=left_rpm.root_identifier,
        right_root=right_rpm.root_identifier,
    )
    _normalize_rpm_source_labels(report.get("left"), left_rpm_path)
    _normalize_rpm_source_labels(report.get("right"), right_rpm_path)
    return report


def _normalize_rpm_source_labels(value: object, source_path: Path) -> None:
    if not isinstance(value, dict):
        return
    label = _stable_fixture_label(source_path)
    value["primaryLocation"] = label
    value["sourceLabel"] = label


def _stable_fixture_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _json_fixture(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-dir",
        type=Path,
        default=FIXTURE_DIR,
        help="directory containing public-derived source and report fixtures",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if committed public-derived report fixtures are stale",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fixture_dir = args.fixture_dir.resolve()
    if args.check:
        stale = check_public_fixture_reports(fixture_dir)
        for path in stale:
            print(f"{path} is out of date")
        return 1 if stale else 0

    for path in write_public_fixture_reports(fixture_dir):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
