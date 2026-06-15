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
from src.output.json_export import GraphJsonExporter
from src.performance_report import build_performance_report
from src.public_advisory_feed import build_public_advisory_feed_report
from src.rpm_albs_provenance import build_rpm_albs_provenance_report
from src.rpm_repository_diff import build_rpm_repository_diff_report
from src.rpm_repository_summary import build_rpm_repository_summary_report


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


def test_rpm_repository_adapter_discovers_primary_from_repomd() -> None:
    resolved = RpmRepositoryAdapter().parse_source(
        Path("tests/fixtures/repodata/repomd.xml")
    )

    root_metadata = resolved.graph.get_vertex_metadata(resolved.root_identifier)
    assert root_metadata["primary_location"].endswith("tests/fixtures/rpm-primary.xml")
    assert resolved.graph.get_dependencies("rpm-repository==public-rpm-repository")


def test_rpm_repository_summary_counts_arches_and_source_rpms() -> None:
    resolved = RpmRepositoryAdapter().parse_primary(
        Path("tests/fixtures/rpm-primary.xml")
    )
    report = build_rpm_repository_summary_report(
        resolved.graph,
        root=resolved.root_identifier,
    )

    assert report["schema"] == "edgp.rpm.repository_summary.v1"
    assert report["summary"] == {
        "packages": 2,
        "sourceRpms": 1,
        "architectures": 1,
        "requirementEdges": 1,
        "unresolvedRequirements": 0,
    }
    assert report["architectures"] == [{"arch": "x86_64", "packages": 2}]


def test_rpm_repository_diff_detects_snapshot_changes() -> None:
    left = RpmRepositoryAdapter().parse_primary(Path("tests/fixtures/rpm-primary.xml"))
    right = RpmRepositoryAdapter().parse_primary(
        Path("tests/fixtures/rpm-primary-updated.xml")
    )

    report = build_rpm_repository_diff_report(
        left.graph,
        right.graph,
        left_root=left.root_identifier,
        right_root=right.root_identifier,
    )

    assert report["schema"] == "edgp.rpm.repository_diff.v1"
    assert report["summary"] == {
        "leftPackages": 2,
        "rightPackages": 2,
        "addedPackages": 1,
        "removedPackages": 1,
        "changedPackages": 1,
        "unchangedPackages": 0,
        "addedSourceRpms": 1,
        "removedSourceRpms": 1,
    }
    assert report["changedPackages"][0]["name"] == "nginx"
    assert report["changedPackages"][0]["changedFields"] == [
        "release",
        "sourceRpm",
        "summary",
        "nodeId",
    ]
    assert report["addedPackages"][0]["name"] == "nginx-filesystem"
    assert report["removedPackages"][0]["name"] == "nginx-core"


def test_libsolv_bridge_parses_transaction_actions() -> None:
    report = build_libsolv_bridge_report(Path("tests/fixtures/libsolv-transaction.txt"))

    assert report["schema"] == "edgp.libsolv.bridge.v1"
    assert report["summary"]["transactionActions"] == 3
    assert report["summary"]["parsedPackages"] == 4
    assert report["summary"]["upgrades"] == 1
    assert report["summary"]["architectures"] == [{"arch": "x86_64", "actions": 3}]
    install = report["transactionActions"][0]
    assert install["packageName"] == "nginx"
    assert install["nodeId"] == "nginx==1.20.1-16.el9_4.1.x86_64"
    assert install["purl"] == "pkg:rpm/nginx@1.20.1-16.el9_4.1?arch=x86_64"
    upgrade = report["transactionActions"][1]
    assert upgrade["oldNodeId"] == "openssl==3.0.7-1.el9.x86_64"
    assert upgrade["newNodeId"] == "openssl==3.0.7-2.el9.x86_64"
    assert upgrade["newPackageMetadata"]["name"] == "openssl"


def test_libsolv_bridge_matches_transaction_actions_to_graph_snapshot(
    tmp_path: Path,
) -> None:
    resolved = RpmRepositoryAdapter().parse_primary(Path("tests/fixtures/rpm-primary.xml"))
    snapshot_path = tmp_path / "rpm-repo-snapshot.json"
    snapshot_path.write_text(
        GraphJsonExporter.export_to_json(
            resolved.graph,
            root=resolved.root_identifier,
            ecosystem=resolved.ecosystem,
        ),
        encoding="utf-8",
    )

    report = build_libsolv_bridge_report(
        Path("tests/fixtures/libsolv-transaction.txt"),
        snapshot_path,
    )

    assert report["graphContext"]["schema"] == "edgp.graph.snapshot.v1"
    assert report["graphContext"]["nodes"] == 3
    assert report["summary"]["graphMatchedActions"] == 1
    assert report["summary"]["graphImpactedActions"] == 1
    assert report["summary"]["graphExactActions"] == 1
    assert report["summary"]["graphUnmatchedActions"] == 2
    assert report["summary"]["maxGraphAffectedDependents"] == 1
    assert report["transactionImpact"][0]["actionIndex"] == 1
    assert report["transactionImpact"][0]["matchStatus"] == "exact"
    assert report["transactionImpact"][0]["matchedNodeIds"] == [
        "nginx==1.20.1-16.el9_4.1.x86_64"
    ]
    assert report["transactionImpact"][0]["affectedDependents"] == 1
    install = report["transactionActions"][0]
    assert install["graphMatchStatus"] == "exact"
    assert install["graphMatchedNodeIds"] == [
        "nginx==1.20.1-16.el9_4.1.x86_64"
    ]
    assert install["graphMatches"][0]["directDependencies"] == 1
    assert install["graphMatches"][0]["affectedDependents"] == 1
    assert report["transactionActions"][1]["graphMatchStatus"] == "unmatched"


def test_cli_libsolv_bundle_writes_report_bundle(tmp_path: Path, capsys) -> None:
    resolved = RpmRepositoryAdapter().parse_primary(Path("tests/fixtures/rpm-primary.xml"))
    snapshot_path = tmp_path / "rpm-repo-snapshot.json"
    snapshot_path.write_text(
        GraphJsonExporter.export_to_json(
            resolved.graph,
            root=resolved.root_identifier,
            ecosystem=resolved.ecosystem,
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "libsolv-bundle"

    assert main(
        [
            "libsolv-bundle",
            "--transaction",
            "tests/fixtures/libsolv-transaction.txt",
            "--graph-snapshot",
            str(snapshot_path),
            "--output-dir",
            str(output_dir),
            "--triage-summary",
        ]
    ) == 0

    index_path = Path(capsys.readouterr().out.strip())
    assert index_path == output_dir / "index.html"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "libsolv-transaction"
    assert manifest["reports"][0]["source"] == "libsolv-bridge.json"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    report = json.loads((output_dir / "libsolv-bridge.json").read_text(encoding="utf-8"))
    assert report["summary"]["graphExactActions"] == 1
    html = (output_dir / manifest["reports"][0]["href"]).read_text(encoding="utf-8")
    assert 'data-testid="libsolv-transaction-panel"' in html
    assert 'data-testid="libsolv-impact-panel"' in html
    assert "exact" in html

    assert main(["verify-bundle", "--path", str(output_dir)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["ok"] is True


def test_public_advisory_feed_normalizes_osv_to_overlay() -> None:
    report = build_public_advisory_feed_report(
        _fixture("tests/fixtures/public-osv.json"),
        ecosystem="rpm",
    )

    assert report["schema"] == "edgp.public.advisory_feed.v1"
    assert report["overlay"]["schema"] == "edgp.advisory.overlay.v1"
    assert report["advisories"][0]["package"] == "nginx"

    range_report = build_public_advisory_feed_report(
        _fixture("tests/fixtures/public-osv-ranges.json"),
        ecosystem="rpm",
    )
    range_advisory = range_report["advisories"][0]
    assert range_advisory["versions"] == []
    assert range_advisory["ranges"] == [
        {
            "type": "ECOSYSTEM",
            "introduced": "1.20.1-16.el9_4.0",
            "fixed": "1.20.1-16.el9_4.2",
        }
    ]
    cvss_report = build_public_advisory_feed_report(
        _fixture("tests/fixtures/public-osv-cvss-score.json"),
        ecosystem="rpm",
    )
    assert cvss_report["advisories"][0]["severity"] == "9.8"
    purl_report = build_public_advisory_feed_report(
        _fixture("tests/fixtures/public-osv-purl.json"),
        ecosystem="npm",
    )
    assert purl_report["advisories"][0]["package"] == "left-pad"
    assert purl_report["advisories"][0]["purl"] == "pkg:npm/left-pad@1.3.0"


def test_performance_report_keeps_numpy_storage_visible() -> None:
    report = build_performance_report([(10, 2)])

    assert report["schema"] == "edgp.performance.report.v1"
    assert report["summary"]["allContiguous"] is True
    assert report["results"][0]["storage"]["layout"] == "numpy.int32.c_contiguous"
    assert report["results"][0]["reverseReachableFromTail"] == 9
    assert report["results"][0]["reverseReachableMs"] >= 0


def test_cli_public_vertical_commands(capsys, tmp_path: Path) -> None:
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
    rpm_repo_snapshot = json.loads(capsys.readouterr().out)
    assert rpm_repo_snapshot["schema"] == "edgp.graph.snapshot.v1"
    rpm_repo_snapshot_path = tmp_path / "rpm-repo-snapshot.json"
    rpm_repo_snapshot_path.write_text(json.dumps(rpm_repo_snapshot), encoding="utf-8")

    assert main(
        [
            "libsolv-bridge",
            "--transaction",
            "tests/fixtures/libsolv-transaction.txt",
            "--graph-snapshot",
            str(rpm_repo_snapshot_path),
        ]
    ) == 0
    libsolv = json.loads(capsys.readouterr().out)
    assert libsolv["schema"] == "edgp.libsolv.bridge.v1"
    assert libsolv["summary"]["graphExactActions"] == 1

    assert main(
        [
            "rpm-repo-summary",
            "--source",
            "tests/fixtures/repodata/repomd.xml",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema"] == (
        "edgp.rpm.repository_summary.v1"
    )

    output_dir = tmp_path / "rpm-repo-summary-bundle"
    assert (
        main(
            [
                "rpm-repo-summary-bundle",
                "--source",
                "tests/fixtures/repodata/repomd.xml",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
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
    assert main(["verify-bundle", "--path", str(output_dir), "--format", "text"]) == 0
    assert capsys.readouterr().out.startswith("OK ")

    assert main(
        [
            "rpm-repo-diff",
            "--left-primary",
            "tests/fixtures/rpm-primary.xml",
            "--right-primary",
            "tests/fixtures/rpm-primary-updated.xml",
        ]
    ) == 0
    assert json.loads(capsys.readouterr().out)["schema"] == (
        "edgp.rpm.repository_diff.v1"
    )

    assert main(
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
    ) == 0
    query = json.loads(capsys.readouterr().out)
    assert query["node"] == "nginx==1.20.1-16.el9_4.1.x86_64"
    assert query["result"] == ["nginx-core==1.20.1-16.el9_4.1.x86_64"]

    assert main(
        [
            "impact",
            "--source",
            "rpm-repo",
            "--path",
            "tests/fixtures/repodata/repomd.xml",
            "--node",
            "nginx-core",
        ]
    ) == 0
    impact = json.loads(capsys.readouterr().out)
    assert impact["schema"] == "edgp.impact.report.v1"
    assert impact["node"] == "nginx-core==1.20.1-16.el9_4.1.x86_64"
    assert "nginx==1.20.1-16.el9_4.1.x86_64" in impact["directDependents"]

    assert main(
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
    ) == 0
    advisory = json.loads(capsys.readouterr().out)
    assert advisory["schema"] == "edgp.advisory.report.v1"
    assert advisory["summary"]["findings"] == 1
    assert advisory["findings"][0]["package"] == "nginx==1.20.1-16.el9_4.1.x86_64"

    assert main(
        [
            "advisory",
            "--source",
            "rpm-repo",
            "--path",
            "tests/fixtures/repodata/repomd.xml",
            "--public-advisory-feed-url",
            Path("tests/fixtures/public-osv-ranges.json").resolve().as_uri(),
            "--ecosystem",
            "rpm",
        ]
    ) == 0
    public_advisory = json.loads(capsys.readouterr().out)
    assert public_advisory["schema"] == "edgp.advisory.report.v1"
    assert public_advisory["summary"]["findings"] == 1
    assert public_advisory["findings"][0]["advisory"]["ranges"][0]["fixed"] == (
        "1.20.1-16.el9_4.2"
    )

    assert (
        main(
            [
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
            ]
        )
        == 2
    )
    failing_advisory = json.loads(capsys.readouterr().out)
    assert failing_advisory["schema"] == "edgp.advisory.report.v1"
    assert failing_advisory["summary"]["findings"] == 1

    output_dir = tmp_path / "advisory-bundle"
    assert (
        main(
            [
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
            ]
        )
        == 2
    )
    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
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
    assert main(["verify-bundle", "--path", str(output_dir), "--format", "text"]) == 0
    assert capsys.readouterr().out.startswith("OK ")

    assert (
        main(
            [
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
            ]
        )
        == 0
    )
    noncritical_advisory = json.loads(capsys.readouterr().out)
    assert noncritical_advisory["schema"] == "edgp.advisory.report.v1"
    assert noncritical_advisory["summary"]["findings"] == 1

    assert (
        main(
            [
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
            ]
        )
        == 2
    )
    critical_advisory = json.loads(capsys.readouterr().out)
    assert critical_advisory["schema"] == "edgp.advisory.report.v1"
    assert critical_advisory["findings"][0]["advisory"]["severity"] == "9.8"

    assert main(
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
    ) == 0
    purl_advisory = json.loads(capsys.readouterr().out)
    assert purl_advisory["schema"] == "edgp.advisory.report.v1"
    assert purl_advisory["summary"]["findings"] == 1
    assert purl_advisory["findings"][0]["package"] == "left-pad==1.3.0"

    assert main(
        [
            "license-report",
            "--source",
            "sbom",
            "--path",
            "tests/fixtures/sample-bom.json",
            "--deny-license",
            "WTFPL",
            "--fail-on-denied",
        ]
    ) == 2
    license_report = json.loads(capsys.readouterr().out)
    assert license_report["schema"] == "edgp.license.report.v1"
    assert license_report["summary"]["deniedFindings"] == 1
    assert license_report["findings"][0]["package"] == "left-pad==1.3.0"

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

    assert main(
        [
            "public-advisory-feed",
            "--url",
            Path("tests/fixtures/public-osv.json").resolve().as_uri(),
        ]
    ) == 0
    public_feed = json.loads(capsys.readouterr().out)
    assert public_feed["schema"] == "edgp.public.advisory_feed.v1"
    assert public_feed["summary"]["advisories"] == 1


def test_cli_public_advisory_feed_bundle_writes_report_bundle(
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "public-advisory-feed-bundle"

    assert (
        main(
            [
                "public-advisory-feed-bundle",
                "--url",
                Path("tests/fixtures/public-osv.json").resolve().as_uri(),
                "--ecosystem",
                "rpm",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "public-advisory-feed"
    assert manifest["reports"][0]["href"] == "001-public-advisory-feed.html"
    assert manifest["reports"][0]["schema"] == "edgp.public.advisory_feed.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    report = json.loads(
        (output_dir / "public-advisory-feed.json").read_text(encoding="utf-8")
    )
    assert report["schema"] == "edgp.public.advisory_feed.v1"
    assert report["summary"]["advisories"] == 1
    assert report["overlay"]["schema"] == "edgp.advisory.overlay.v1"
    assert 'data-testid="public-advisory-feed-panel"' in (
        output_dir / "001-public-advisory-feed.html"
    ).read_text(encoding="utf-8")

    assert main(["verify-bundle", "--path", str(output_dir), "--format", "text"]) == 0
    assert capsys.readouterr().out.startswith("OK ")


def test_cli_rpm_repo_bundle_writes_graph_and_summary(tmp_path, capsys) -> None:
    output_dir = tmp_path / "rpm-repo-bundle"

    assert main(
        [
            "rpm-repo-bundle",
            "--source",
            "tests/fixtures/repodata/repomd.xml",
            "--output-dir",
            str(output_dir),
            "--impact-node",
            "nginx-core",
            "--advisories",
            "tests/fixtures/rpm-repo-advisories.json",
            "--public-advisory-feed-url",
            Path("tests/fixtures/public-osv-ranges.json").resolve().as_uri(),
            "--libsolv-transaction",
            "tests/fixtures/libsolv-transaction.txt",
            "--triage-summary",
        ]
    ) == 0

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "rpm-repository"
    assert manifest["reports"][0]["href"] == "001-rpm-repository-graph.html"
    assert manifest["reports"][1]["href"] == "002-rpm-repository-summary.html"
    assert manifest["reports"][2]["href"] == (
        "003-impact-nginx-core-1.20.1-16.el9_4.1.x86_64.html"
    )
    assert manifest["reports"][3]["href"] == "004-advisory-report.html"
    assert manifest["reports"][4]["href"] == "005-public-advisory-feed.html"
    assert manifest["reports"][5]["href"] == "006-public-advisory-report.html"
    assert manifest["reports"][6]["href"] == "007-libsolv-bridge.html"
    assert manifest["triageSummary"]["href"] == "triage-summary.html"
    summary = json.loads(
        (output_dir / "rpm-repository-summary.json").read_text(encoding="utf-8")
    )
    assert summary["schema"] == "edgp.rpm.repository_summary.v1"
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
    assert public_feed["advisories"][0]["ranges"][0]["fixed"] == (
        "1.20.1-16.el9_4.2"
    )
    public_advisory = json.loads(
        (output_dir / "public-advisory-report.json").read_text(encoding="utf-8")
    )
    assert public_advisory["schema"] == "edgp.advisory.report.v1"
    assert public_advisory["summary"]["findings"] == 1
    advisory_html = (output_dir / "004-advisory-report.html").read_text(
        encoding="utf-8"
    )
    assert 'data-testid="advisory-findings-panel"' in advisory_html
    public_feed_html = (output_dir / "005-public-advisory-feed.html").read_text(
        encoding="utf-8"
    )
    assert 'data-testid="public-advisory-feed-panel"' in public_feed_html
    public_advisory_html = (output_dir / "006-public-advisory-report.html").read_text(
        encoding="utf-8"
    )
    assert 'data-testid="advisory-findings-panel"' in public_advisory_html
    libsolv = json.loads(
        (output_dir / "libsolv-bridge.json").read_text(encoding="utf-8")
    )
    assert libsolv["schema"] == "edgp.libsolv.bridge.v1"
    assert libsolv["summary"]["graphExactActions"] == 1
    assert libsolv["transactionImpact"][0]["matchStatus"] == "exact"
    libsolv_html = (output_dir / "007-libsolv-bridge.html").read_text(encoding="utf-8")
    assert 'data-testid="libsolv-transaction-panel"' in libsolv_html
    assert 'data-testid="libsolv-impact-panel"' in libsolv_html
    triage = json.loads(
        (output_dir / "triage-summary.json").read_text(encoding="utf-8")
    )
    assert triage["schema"] == "edgp.triage.summary.v1"
    assert triage["status"] == "fail"
    assert triage["summary"]["reports"] == 7
    assert triage["summary"]["advisoryFindings"] == 2


def test_cli_rpm_repo_diff_bundle_writes_report_bundle(tmp_path, capsys) -> None:
    output_dir = tmp_path / "rpm-repo-diff-bundle"

    assert main(
        [
            "rpm-repo-diff-bundle",
            "--left-primary",
            "tests/fixtures/rpm-primary.xml",
            "--right-primary",
            "tests/fixtures/rpm-primary-updated.xml",
            "--output-dir",
            str(output_dir),
        ]
    ) == 0

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "rpm-repository-diff"
    assert manifest["reports"][0]["href"] == "001-rpm-repository-diff.html"
    diff = json.loads(
        (output_dir / "rpm-repository-diff.json").read_text(encoding="utf-8")
    )
    assert diff["schema"] == "edgp.rpm.repository_diff.v1"
    assert diff["summary"]["changedPackages"] == 1
    html = (output_dir / "001-rpm-repository-diff.html").read_text(encoding="utf-8")
    assert 'data-testid="rpm-repository-diff-changed-panel"' in html


def test_cli_albs_artifact_inventory_bundle_writes_report_bundle(
    tmp_path, capsys
) -> None:
    output_dir = tmp_path / "albs-artifact-inventory-bundle"

    assert main(
        [
            "albs-artifact-inventory-bundle",
            "--path",
            "tests/fixtures/albs-build.json",
            "--output-dir",
            str(output_dir),
            "--triage-summary",
        ]
    ) == 0

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "albs-artifact-inventory"
    assert manifest["reports"][0]["href"] == "001-albs-artifact-inventory.html"
    assert manifest["reports"][0]["schema"] == "edgp.albs.artifact_inventory.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    report = json.loads(
        (output_dir / "albs-artifact-inventory.json").read_text(encoding="utf-8")
    )
    assert report["schema"] == "edgp.albs.artifact_inventory.v1"
    assert report["summary"]["artifacts"] == 4
    html = (output_dir / "001-albs-artifact-inventory.html").read_text(
        encoding="utf-8"
    )
    assert 'data-testid="albs-artifact-table-panel"' in html

    assert main(["verify-bundle", "--path", str(output_dir)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["ok"] is True


def test_cli_albs_build_timing_bundle_writes_report_bundle(tmp_path, capsys) -> None:
    output_dir = tmp_path / "albs-build-timing-bundle"

    assert main(
        [
            "albs-build-timing-bundle",
            "--path",
            "tests/fixtures/albs-build.json",
            "--output-dir",
            str(output_dir),
            "--triage-summary",
        ]
    ) == 0

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "albs-build-timing"
    assert manifest["reports"][0]["href"] == "001-albs-build-timing.html"
    assert manifest["reports"][0]["schema"] == "edgp.albs.build_timing.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    report = json.loads(
        (output_dir / "albs-build-timing.json").read_text(encoding="utf-8")
    )
    assert report["schema"] == "edgp.albs.build_timing.v1"
    assert report["summary"]["criticalBuildTaskWallSeconds"] == 371.070048
    html = (output_dir / "001-albs-build-timing.html").read_text(encoding="utf-8")
    assert 'data-testid="albs-artifact-timing-panel"' in html

    assert main(["verify-bundle", "--path", str(output_dir)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["ok"] is True


def test_cli_albs_commands_accept_public_json_urls(tmp_path, capsys) -> None:
    build_url = Path("tests/fixtures/albs-build.json").resolve().as_uri()
    updated_url = Path("tests/fixtures/albs-build-updated.json").resolve().as_uri()

    assert main(["albs-build", "--url", build_url]) == 0
    graph = json.loads(capsys.readouterr().out)
    assert graph["schema"] == "edgp.graph.snapshot.v1"
    assert graph["root"] == "albs-build:17812"

    assert (
        main(["albs-build-diff", "--left-url", build_url, "--right-url", updated_url])
        == 0
    )
    diff = json.loads(capsys.readouterr().out)
    assert diff["schema"] == "edgp.albs.build_diff.v1"
    assert diff["summary"]["changedArtifacts"] == 3

    assert main(
        ["albs-release-completeness", "--url", build_url, "--url", updated_url]
    ) == 0
    completeness = json.loads(capsys.readouterr().out)
    assert completeness["schema"] == "edgp.albs.release_completeness.v1"
    assert completeness["summary"]["builds"] == 2

    output_dir = tmp_path / "albs-build-timing-url-bundle"
    assert main(
        [
            "albs-build-timing-bundle",
            "--url",
            build_url,
            "--output-dir",
            str(output_dir),
        ]
    ) == 0
    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    report = json.loads(
        (output_dir / "albs-build-timing.json").read_text(encoding="utf-8")
    )
    assert report["schema"] == "edgp.albs.build_timing.v1"
    assert report["summary"]["criticalBuildTaskWallSeconds"] == 371.070048


def test_cli_albs_build_diff_bundle_writes_report_bundle(tmp_path, capsys) -> None:
    output_dir = tmp_path / "albs-build-diff-bundle"

    assert main(
        [
            "albs-build-diff-bundle",
            "--left-path",
            "tests/fixtures/albs-build.json",
            "--right-path",
            "tests/fixtures/albs-build-updated.json",
            "--output-dir",
            str(output_dir),
            "--triage-summary",
        ]
    ) == 0

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "albs-build-diff"
    assert manifest["reports"][0]["href"] == "001-albs-build-diff.html"
    assert manifest["reports"][0]["schema"] == "edgp.albs.build_diff.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    diff = json.loads((output_dir / "albs-build-diff.json").read_text(encoding="utf-8"))
    assert diff["schema"] == "edgp.albs.build_diff.v1"
    assert diff["summary"]["changedArtifacts"] == 3
    html = (output_dir / "001-albs-build-diff.html").read_text(encoding="utf-8")
    assert "EDGP ALBS Build Diff" in html

    assert main(["verify-bundle", "--path", str(output_dir)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["ok"] is True


def test_cli_albs_log_intelligence_bundle_writes_report_bundle(
    tmp_path, capsys
) -> None:
    output_dir = tmp_path / "albs-log-intelligence-bundle"

    assert main(
        [
            "albs-log-intelligence-bundle",
            "--path",
            "tests/fixtures/albs-build-updated.json",
            "--output-dir",
            str(output_dir),
            "--triage-summary",
        ]
    ) == 0

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "albs-log-intelligence"
    assert manifest["reports"][0]["href"] == "001-albs-log-intelligence.html"
    assert manifest["reports"][0]["schema"] == "edgp.albs.log_intelligence.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    report = json.loads(
        (output_dir / "albs-log-intelligence.json").read_text(encoding="utf-8")
    )
    assert report["schema"] == "edgp.albs.log_intelligence.v1"
    assert report["signalCounts"]["missing"] == 1
    html = (output_dir / "001-albs-log-intelligence.html").read_text(encoding="utf-8")
    assert 'data-testid="albs-log-intelligence-panel"' in html

    assert main(["verify-bundle", "--path", str(output_dir)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["ok"] is True


def test_cli_albs_release_completeness_bundle_writes_report_bundle(
    tmp_path, capsys
) -> None:
    output_dir = tmp_path / "albs-release-completeness-bundle"

    assert main(
        [
            "albs-release-completeness-bundle",
            "--path",
            "tests/fixtures/albs-build.json",
            "--path",
            "tests/fixtures/albs-build-updated.json",
            "--output-dir",
            str(output_dir),
            "--triage-summary",
        ]
    ) == 0

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "albs-release-completeness"
    assert manifest["reports"][0]["href"] == "001-albs-release-completeness.html"
    assert manifest["reports"][0]["schema"] == "edgp.albs.release_completeness.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    report = json.loads(
        (output_dir / "albs-release-completeness.json").read_text(encoding="utf-8")
    )
    assert report["schema"] == "edgp.albs.release_completeness.v1"
    assert report["summary"]["builds"] == 2
    html = (output_dir / "001-albs-release-completeness.html").read_text(
        encoding="utf-8"
    )
    assert 'data-testid="albs-release-completeness-panel"' in html

    assert main(["verify-bundle", "--path", str(output_dir)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["ok"] is True
