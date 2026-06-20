"""CLI tests for compact text summaries from graph exporters."""

from src.cli import main


def test_cli_graph_export_text_summarizes_all_fixture_backed_sources(capsys) -> None:
    cases = [
        (
            ["demo", "--format", "text"],
            [
                "root=app==1.0.0",
                "ecosystem=generic",
                "nodes=4",
                "edges=4",
                "topDependedUpon=core==1.5.0",
                "topDependents=2",
            ],
        ),
        (
            [
                "resolve",
                "--registry",
                "tests/fixtures/registry.json",
                "--root",
                "app",
                "--version",
                "1.0.0",
                "--format",
                "text",
            ],
            [
                "root=app==1.0.0",
                "ecosystem=generic",
                "nodes=4",
                "edges=4",
                "topDependedUpon=core==1.5.0",
                "topDependents=2",
            ],
        ),
        (
            [
                "lockfile",
                "--path",
                "tests/fixtures/package-lock.json",
                "--format",
                "text",
            ],
            [
                "root=demo-app==1.0.0",
                "ecosystem=npm",
                "nodes=4",
                "edges=4",
                "topDependedUpon=left-pad==1.3.0",
                "topDependents=2",
            ],
        ),
        (
            ["dot", "--path", "tests/fixtures/repograph.dot", "--format", "text"],
            [
                "root=nginx-core==unknown",
                "ecosystem=rpm",
                "nodes=4",
                "edges=5",
                "topDependedUpon=glibc==unknown",
                "topDependents=3",
            ],
        ),
        (
            ["sbom", "--path", "tests/fixtures/sample-bom.json", "--format", "text"],
            [
                "root=demo-app==1.0.0",
                "ecosystem=npm",
                "nodes=2",
                "edges=1",
                "topDependedUpon=left-pad==1.3.0",
                "topDependents=1",
            ],
        ),
        (
            [
                "maven-tree",
                "--path",
                "tests/fixtures/maven-tree.txt",
                "--format",
                "text",
            ],
            [
                "root=com.example:demo-app==1.0.0",
                "ecosystem=maven",
                "nodes=6",
                "edges=5",
                "topDependedUpon=com.fasterxml.jackson.core:jackson-core==2.17.0",
                "topDependents=1",
            ],
        ),
        (
            [
                "rpm-repo",
                "--source",
                "tests/fixtures/repodata/repomd.xml",
                "--format",
                "text",
            ],
            [
                "root=rpm-repository==public-rpm-repository",
                "ecosystem=rpm",
                "nodes=20",
                "edges=21",
                "topDependedUpon=nginx-core==1.20.1-28.el9_8.2.alma.1.x86_64",
                "topDependents=2",
            ],
        ),
        (
            [
                "albs-build",
                "--path",
                "tests/fixtures/albs-build.json",
                "--format",
                "text",
            ],
            [
                "root=albs-build:17812",
                "ecosystem=albs",
                "nodes=15",
                "edges=20",
                "topDependedUpon=albs-release:7396",
                "topDependents=6",
            ],
        ),
    ]

    for argv, expected_parts in cases:
        assert main(argv) == 0
        output = capsys.readouterr().out.strip()
        assert output.startswith("GRAPH schema=edgp.graph.snapshot.v1")
        for expected in expected_parts:
            assert expected in output
