"""CLI tests for compact text summaries from static report bundles."""

from src.cli import main


def test_cli_source_bundles_can_print_text_summaries(tmp_path, capsys) -> None:
    cases = [
        (
            "npm",
            [
                "npm-bundle",
                "--path",
                "tests/fixtures/package-lock.json",
            ],
            "npm-lockfile",
        ),
        (
            "dot",
            [
                "dot-bundle",
                "--path",
                "tests/fixtures/repograph.dot",
            ],
            "dot",
        ),
        (
            "sbom",
            [
                "sbom-bundle",
                "--path",
                "tests/fixtures/sample-bom.json",
            ],
            "cyclonedx-sbom",
        ),
        (
            "maven",
            [
                "maven-bundle",
                "--path",
                "tests/fixtures/maven-tree.txt",
            ],
            "maven-dependency-tree",
        ),
        (
            "rpm-repo",
            [
                "rpm-repo-bundle",
                "--source",
                "tests/fixtures/repodata/repomd.xml",
            ],
            "rpm-repository",
        ),
        (
            "albs-build",
            [
                "albs-build-bundle",
                "--path",
                "tests/fixtures/albs-build.json",
            ],
            "albs-build",
        ),
    ]

    for label, base_args, source_kind in cases:
        output_dir = tmp_path / label
        assert (
            main(
                [
                    *base_args,
                    "--output-dir",
                    str(output_dir),
                    "--triage-summary",
                    "--format",
                    "text",
                ]
            )
            == 0
        )
        output = capsys.readouterr().out.strip()
        assert output.startswith("BUNDLE ")
        assert f"index={output_dir / 'index.html'}" in output
        assert f"sourceKind={source_kind}" in output
        assert "reports=" in output
        assert "triageStatus=pass" in output
        assert (output_dir / "index.html").exists()
        assert (output_dir / "manifest.json").exists()
