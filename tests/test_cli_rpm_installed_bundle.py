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
        graph.add_dependency_edge("rpm-installed==local", "bash==5.2.26-6.el10")
        graph.add_dependency_edge("rpm-installed==local", "glibc==2.39-1.el10")
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

    assert (
        cli.main(
            [
                "rpm-installed-bundle",
                "--impact-node",
                "glibc",
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

    assert graph["schema"] == "edgp.graph.snapshot.v1"
    assert graph["ecosystem"] == "rpm"
    assert impact["node"] == "glibc==2.39-1.el10"
    assert impact["summary"]["affectedDependents"] == 2
    assert manifest["bundle"]["sourceKind"] == "rpm-installed"
    assert manifest["bundle"]["command"].startswith("edgp rpm-installed-bundle ")
    assert [report["schema"] for report in manifest["reports"]] == [
        "edgp.graph.snapshot.v1",
        "edgp.impact.report.v1",
    ]
    assert (output_dir / "001-rpm-installed-graph.html").exists()
    assert (output_dir / "002-impact-glibc-2.39-1.el10.html").exists()
