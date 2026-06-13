"""CLI tests for installed RPM report bundles."""

import json
from pathlib import Path

import src.cli as cli
from src.adapters.base import ResolvedProjectGraph
from src.core_graph.sparse_matrix import CSRDependencyGraph


class FakeInstalledRpmAdapter:
    def parse_installed(
        self,
        *,
        limit: int = 100,
        max_requirements: int = 40,
    ) -> ResolvedProjectGraph:
        graph = CSRDependencyGraph()
        graph.add_vertex(
            "rpm-installed==local",
            metadata={"ecosystem": "rpm", "source": "rpmdb", "node_type": "root"},
        )
        graph.add_vertex(
            "bash==5.2.26-6.el10",
            metadata={"ecosystem": "rpm", "source": "rpmdb", "arch": "x86_64"},
        )
        graph.add_vertex(
            "glibc==2.39-1.el10",
            metadata={"ecosystem": "rpm", "source": "rpmdb", "arch": "x86_64"},
        )
        graph.add_vertex(
            "nginx-core==1.20.1-16.el9_4.1",
            metadata={"ecosystem": "rpm", "source": "rpmdb", "arch": "x86_64"},
        )
        graph.add_dependency_edge("rpm-installed==local", "bash==5.2.26-6.el10")
        graph.add_dependency_edge("rpm-installed==local", "glibc==2.39-1.el10")
        graph.add_dependency_edge(
            "rpm-installed==local",
            "nginx-core==1.20.1-16.el9_4.1",
        )
        graph.add_dependency_edge("bash==5.2.26-6.el10", "glibc==2.39-1.el10")
        return ResolvedProjectGraph(
            root_identifier="rpm-installed==local",
            graph=graph,
            ecosystem="rpm",
        )


def test_cli_rpm_installed_bundle_writes_graph_and_impact_reports(
    tmp_path, capsys, monkeypatch
) -> None:
    monkeypatch.setattr(cli, "InstalledRpmAdapter", FakeInstalledRpmAdapter)
    output_dir = tmp_path / "rpm-installed-bundle"
    transaction_path = tmp_path / "libsolv-transaction.txt"
    transaction_path.write_text(
        "install glibc-2.39-1.el10.x86_64\n",
        encoding="utf-8",
    )
    public_feed_path = tmp_path / "public-osv.json"
    public_feed_path.write_text(
        json.dumps(
            {
                "id": "OSV-RPM-LOCAL-0001",
                "summary": "Demo public advisory for installed glibc.",
                "affected": [{"package": {"ecosystem": "rpm", "name": "glibc"}}],
            }
        ),
        encoding="utf-8",
    )

    assert (
        cli.main(
            [
                "rpm-installed-bundle",
                "--impact-node",
                "glibc",
                "--advisories",
                "tests/fixtures/rpm-advisories.json",
                "--public-advisory-feed",
                str(public_feed_path),
                "--libsolv-transaction",
                str(transaction_path),
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    graph = json.loads(
        (output_dir / "rpm-installed-graph.json").read_text(encoding="utf-8")
    )
    impact = json.loads(
        (output_dir / "impact-glibc-2.39-1.el10.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    advisory = json.loads(
        (output_dir / "advisory-report.json").read_text(encoding="utf-8")
    )
    public_feed = json.loads(
        (output_dir / "public-advisory-feed.json").read_text(encoding="utf-8")
    )
    public_advisory = json.loads(
        (output_dir / "public-advisory-report.json").read_text(encoding="utf-8")
    )
    libsolv = json.loads((output_dir / "libsolv-bridge.json").read_text(encoding="utf-8"))

    assert graph["schema"] == "edgp.graph.snapshot.v1"
    assert graph["ecosystem"] == "rpm"
    assert impact["node"] == "glibc==2.39-1.el10"
    assert impact["summary"]["affectedDependents"] == 2
    assert advisory["schema"] == "edgp.advisory.report.v1"
    assert advisory["summary"]["findings"] == 1
    assert public_feed["schema"] == "edgp.public.advisory_feed.v1"
    assert public_feed["summary"]["advisories"] == 1
    assert public_advisory["schema"] == "edgp.advisory.report.v1"
    assert public_advisory["summary"]["findings"] == 1
    assert libsolv["schema"] == "edgp.libsolv.bridge.v1"
    assert libsolv["transactionActions"][0]["graphMatchStatus"] == "candidate"
    assert libsolv["transactionImpact"][0]["matchedNodeIds"] == ["glibc==2.39-1.el10"]
    assert libsolv["transactionImpact"][0]["affectedDependents"] == 2
    assert manifest["bundle"]["sourceKind"] == "rpm-installed"
    assert manifest["bundle"]["command"].startswith("edgp rpm-installed-bundle ")
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.impact.report.v1",
        "edgp.advisory.report.v1",
        "edgp.public.advisory_feed.v1",
        "edgp.advisory.report.v1",
        "edgp.libsolv.bridge.v1",
    ]
    assert (output_dir / "001-rpm-installed-graph.html").exists()
    assert (output_dir / "002-impact-glibc-2.39-1.el10.html").exists()
    assert (output_dir / "003-advisory-report.html").exists()
    assert (output_dir / "004-public-advisory-feed.html").exists()
    assert (output_dir / "005-public-advisory-report.html").exists()
    assert (output_dir / "006-libsolv-bridge.html").exists()


def test_cli_rpm_albs_provenance_bundle_writes_static_report(
    tmp_path, capsys, monkeypatch
) -> None:
    monkeypatch.setattr(cli, "InstalledRpmAdapter", FakeInstalledRpmAdapter)
    output_dir = tmp_path / "rpm-albs-provenance-bundle"

    assert (
        cli.main(
            [
                "rpm-albs-provenance-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
                "--rpm-limit",
                "10",
                "--max-requirements",
                "10",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads(
        (output_dir / "rpm-albs-provenance.json").read_text(encoding="utf-8")
    )

    assert manifest["bundle"]["sourceKind"] == "rpm-albs-provenance"
    assert manifest["reports"][0]["href"] == "001-rpm-albs-provenance.html"
    assert manifest["reports"][0]["schema"] == "edgp.rpm.albs_provenance.v1"
    assert manifest["triageSummary"]["href"] == "triage-summary.html"
    assert report["schema"] == "edgp.rpm.albs_provenance.v1"
    assert report["summary"]["matchedPackages"] == 1
    assert report["matches"][0]["installedPackage"]["nodeId"] == (
        "nginx-core==1.20.1-16.el9_4.1"
    )
    assert report["matches"][0]["albsArtifact"]["filename"] == (
        "nginx-core-1.20.1-16.el9_4.1.x86_64.rpm"
    )
    html = (output_dir / "001-rpm-albs-provenance.html").read_text(encoding="utf-8")
    assert 'data-testid="rpm-albs-provenance-matches-panel"' in html

    assert cli.main(["verify-bundle", "--path", str(output_dir)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["ok"] is True
