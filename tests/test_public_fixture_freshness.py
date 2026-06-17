"""Freshness checks for public-derived report fixtures."""

import json
from pathlib import Path

from src.adapters.albs import AlbsBuildAdapter
from src.adapters.rpm_repository import RpmRepositoryAdapter
from src.albs_artifact_inventory import build_albs_artifact_inventory
from src.albs_build_diff import build_albs_build_diff_report
from src.albs_build_timing import build_albs_build_timing_report
from src.albs_log_intelligence import build_albs_log_intelligence_report
from src.albs_release_completeness import build_albs_release_completeness_report
from src.libsolv_bridge import build_libsolv_bridge_report
from src.rpm_repository_diff import build_rpm_repository_diff_report
from src.rpm_repository_summary import build_rpm_repository_summary_report


def _fixture(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_public_derived_report_fixtures_match_generators() -> None:
    left_albs = _fixture("tests/fixtures/albs-build.json")
    right_albs = _fixture("tests/fixtures/albs-build-updated.json")
    albs_graph = AlbsBuildAdapter().parse_file(Path("tests/fixtures/albs-build.json"))
    left_rpm = RpmRepositoryAdapter().parse_primary(Path("tests/fixtures/rpm-primary.xml"))
    right_rpm = RpmRepositoryAdapter().parse_primary(
        Path("tests/fixtures/rpm-primary-updated.xml")
    )

    expected = {
        "tests/fixtures/albs-artifact-inventory.json": build_albs_artifact_inventory(
            albs_graph.graph,
            root=albs_graph.root_identifier,
        ),
        "tests/fixtures/albs-build-timing.json": build_albs_build_timing_report(
            left_albs
        ),
        "tests/fixtures/albs-build-diff.json": build_albs_build_diff_report(
            left_albs,
            right_albs,
        ),
        "tests/fixtures/albs-log-intelligence.json": (
            build_albs_log_intelligence_report(right_albs)
        ),
        "tests/fixtures/albs-release-completeness.json": (
            build_albs_release_completeness_report([left_albs, right_albs])
        ),
        "tests/fixtures/rpm-repository-summary.json": (
            build_rpm_repository_summary_report(
                left_rpm.graph,
                root=left_rpm.root_identifier,
            )
        ),
        "tests/fixtures/rpm-repository-diff.json": build_rpm_repository_diff_report(
            left_rpm.graph,
            right_rpm.graph,
            left_root=left_rpm.root_identifier,
            right_root=right_rpm.root_identifier,
        ),
        "tests/fixtures/libsolv-bridge.json": build_libsolv_bridge_report(
            Path("tests/fixtures/libsolv-transaction.txt")
        ),
    }

    for fixture_path, generated in expected.items():
        assert _fixture(fixture_path) == generated, fixture_path

