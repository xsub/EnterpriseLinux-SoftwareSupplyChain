"""Public-access vertical report tests for ALBS, RPM, libsolv, and advisories."""

import json
from pathlib import Path

from src.albs_build_diff import build_albs_build_diff_report
from src.albs_log_intelligence import build_albs_log_intelligence_report
from src.albs_release_completeness import build_albs_release_completeness_report
from src.adapters.rpm_repository import RpmRepositoryAdapter
from src.cli import main
from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.libsolv_bridge import build_libsolv_bridge_report
from src.performance_report import build_performance_report
from src.public_advisory_feed import build_public_advisory_feed_report
from src.rpm_albs_provenance import build_rpm_albs_provenance_report


def _fixture(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_albs_build_diff_detects_artifact_and_commit_changes() -> None:
    report = build_albs_build_diff_report(
        _fixture("tests/fixtures/albs-build.json"),
        _fixture("tests/fixtures/albs-build-updated.json"),
    )

    assert report["schema"] == "edgp.albs.build_diff.v1"
    assert report["summary"]["addedArtifacts"] == 1
    assert report["summary"]["removedArtifacts"] == 1
    assert report["summary"]["changedArtifacts"] == 3
    assert report["summary"]["gitCommitChanged"] is True


def test_albs_log_intelligence_extracts_inline_signals() -> None:
    report = build_albs_log_intelligence_report(
        _fixture("tests/fixtures/albs-build-updated.json")
    )

    assert report["schema"] == "edgp.albs.log_intelligence.v1"
    assert report["summary"]["logsWithInlineContent"] == 1
    assert report["signalCounts"] == {
        "error": 1,
        "failed": 1,
        "missing": 1,
        "warning": 1,
    }


def test_albs_release_completeness_marks_missing_public_arches() -> None:
    report = build_albs_release_completeness_report(
        [_fixture("tests/fixtures/albs-build.json")]
    )

    assert report["schema"] == "edgp.albs.release_completeness.v1"
    assert report["summary"]["buildsWithMissingArchitectures"] == 1
    assert report["builds"][0]["missingBuildArchitectures"] == [
        "aarch64",
        "s390x",
        "i686",
    ]


def test_rpm_albs_provenance_matches_installed_package_to_build_artifact() -> None:
    graph = CSRDependencyGraph()
    graph.add_vertex(
        "nginx-core==1.20.1-16.el9_4.1",
        metadata={
            "ecosystem": "rpm",
            "source": "rpmdb",
            "arch": "x86_64",
            "source_rpm": "nginx-1.20.1-16.el9_4.1.src.rpm",
        },
    )

    report = build_rpm_albs_provenance_report(
        graph,
        _fixture("tests/fixtures/albs-build.json"),
    )

    assert report["schema"] == "edgp.rpm.albs_provenance.v1"
    assert report["summary"]["matchedPackages"] == 1
    assert report["matches"][0]["albsArtifact"]["filename"] == (
        "nginx-core-1.20.1-16.el9_4.1.x86_64.rpm"
    )


def test_rpm_repository_adapter_links_requires_to_providers() -> None:
    resolved = RpmRepositoryAdapter().parse_primary(
        Path("tests/fixtures/rpm-primary.xml")
    )

    assert resolved.root_identifier == "rpm-repository==public-rpm-repository"
    assert "nginx-core==1.20.1-16.el9_4.1.x86_64" in resolved.graph.get_dependencies(
        "nginx==1.20.1-16.el9_4.1.x86_64"
    )


def test_libsolv_bridge_parses_transaction_actions() -> None:
    report = build_libsolv_bridge_report(Path("tests/fixtures/libsolv-transaction.txt"))

    assert report["schema"] == "edgp.libsolv.bridge.v1"
    assert report["summary"]["transactionActions"] == 3
    assert report["summary"]["upgrades"] == 1


def test_public_advisory_feed_normalizes_osv_to_overlay() -> None:
    report = build_public_advisory_feed_report(
        _fixture("tests/fixtures/public-osv.json"),
        ecosystem="rpm",
    )

    assert report["schema"] == "edgp.public.advisory_feed.v1"
    assert report["overlay"]["schema"] == "edgp.advisory.overlay.v1"
    assert report["advisories"][0]["package"] == "nginx"


def test_performance_report_keeps_numpy_storage_visible() -> None:
    report = build_performance_report([(10, 2)])

    assert report["schema"] == "edgp.performance.report.v1"
    assert report["summary"]["allContiguous"] is True
    assert report["results"][0]["storage"]["layout"] == "numpy.int32.c_contiguous"


def test_cli_public_vertical_commands(capsys) -> None:
    assert main(
        [
            "albs-build-diff",
            "--left-path",
            "tests/fixtures/albs-build.json",
            "--right-path",
            "tests/fixtures/albs-build-updated.json",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema"] == "edgp.albs.build_diff.v1"

    assert main(["rpm-repo", "--primary", "tests/fixtures/rpm-primary.xml"]) == 0
    assert json.loads(capsys.readouterr().out)["schema"] == "edgp.graph.snapshot.v1"

    assert main(
        [
            "public-advisory-feed",
            "--path",
            "tests/fixtures/public-osv.json",
            "--format",
            "overlay",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema"] == "edgp.advisory.overlay.v1"
