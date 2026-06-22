"""CLI tests for parallel frozen-CSR reachability queries."""

import json

from src.cli import main


def test_cli_parallel_query_runs_multiple_reachability_queries(capsys) -> None:
    assert (
        main(
            [
                "parallel-query",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--query",
                "dependencies:app==1.0.0",
                "--query",
                "dependents:core==1.0.0",
                "--workers",
                "2",
                "--backend",
                "auto",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.parallel.query.report.v1"
    assert payload["summary"]["queries"] == 2
    assert payload["summary"]["nodeQueries"] == 2
    assert payload["summary"]["pathQueries"] == 0
    assert payload["summary"]["workers"] == 2
    assert payload["summary"]["backend"] == "auto"
    assert payload["summary"]["inputType"] == "snapshot"
    assert payload["summary"]["memoryMapped"] is False
    assert payload["results"][0]["nodes"] == ["lib==2.0.0", "core==1.0.0"]
    assert payload["results"][1]["nodes"] == ["lib==2.0.0", "app==1.0.0"]


def test_cli_parallel_query_outputs_text_summary(capsys) -> None:
    assert (
        main(
            [
                "parallel-query",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--query",
                "dependencies:app==1.0.0",
                "--query",
                "dependents:core==1.0.0",
                "--workers",
                "2",
                "--backend",
                "auto",
                "--format",
                "text",
            ]
        )
        == 0
    )

    output = capsys.readouterr().out.strip()
    assert output.startswith("OK schema=edgp.parallel.query.report.v1 ")
    assert "inputType=snapshot" in output
    assert "memoryMapped=false" in output
    assert "queries=2" in output
    assert "nodeQueries=2" in output
    assert "pathQueries=0" in output
    assert "workers=2" in output
    assert "backend=auto" in output
    assert "selectedBackend=" in output
    assert "totalResultNodes=4" in output
    assert "firstQuery=dependencies" in output
    assert "firstNode=app==1.0.0" in output
    assert "firstResultKind=nodes" in output


def test_cli_parallel_query_reads_memory_mapped_csr_artifact(tmp_path, capsys) -> None:
    artifact_dir = tmp_path / "csr-artifact"

    assert (
        main(
            [
                "csr-artifact",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(artifact_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "parallel-query",
                "--csr-artifact",
                str(artifact_dir),
                "--query",
                "dependencies:app==1.0.0",
                "--query",
                "dependents:core==1.0.0",
                "--query",
                "dependency-path:app==1.0.0->core==1.0.0",
                "--workers",
                "3",
                "--backend",
                "auto",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["inputType"] == "csr-artifact"
    assert payload["summary"]["memoryMapped"] is True
    assert payload["summary"]["nodeQueries"] == 2
    assert payload["summary"]["pathQueries"] == 1
    assert payload["results"][0]["nodes"] == ["lib==2.0.0", "core==1.0.0"]
    assert payload["results"][1]["nodes"] == ["lib==2.0.0", "app==1.0.0"]
    assert payload["results"][2]["resultKind"] == "path"
    assert payload["results"][2]["nodes"] == [
        "app==1.0.0",
        "lib==2.0.0",
        "core==1.0.0",
    ]

    assert (
        main(
            [
                "parallel-query",
                "--csr-artifact",
                str(artifact_dir),
                "--query",
                "dependencies:app==1.0.0",
                "--workers",
                "1",
                "--format",
                "text",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out.strip()
    assert "inputType=csr-artifact" in output
    assert "memoryMapped=true" in output
    assert "totalResultNodes=2" in output


def test_cli_parallel_query_bundle_writes_verifiable_static_bundle(
    tmp_path,
    capsys,
) -> None:
    artifact_dir = tmp_path / "csr-artifact"
    output_dir = tmp_path / "parallel-query-bundle"
    catalog_dir = tmp_path / "parallel-query-catalog"

    assert (
        main(
            [
                "csr-artifact",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(artifact_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "parallel-query-bundle",
                "--csr-artifact",
                str(artifact_dir),
                "--query",
                "dependencies:app==1.0.0",
                "--query",
                "dependents:core==1.0.0",
                "--query",
                "dependency-path:app==1.0.0->core==1.0.0",
                "--workers",
                "3",
                "--backend",
                "auto",
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
    assert output.startswith("BUNDLE index=")
    assert "sourceKind=parallel-query" in output
    assert "reports=1" in output
    assert "triageStatus=pass" in output
    assert "parallelQueryReports=1" in output
    assert "parallelQueryQueries=3" in output
    assert "parallelQueryNodeQueries=2" in output
    assert "parallelQueryPathQueries=1" in output
    assert "parallelQueryResultNodes=7" in output
    assert "parallelQueryPathResultNodes=3" in output
    assert "parallelQueryMemoryMappedReports=1" in output

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "parallel-query"
    assert manifest["reports"][0]["title"] == "Parallel Query Report"
    assert manifest["reports"][0]["href"] == "001-parallel-query-report.html"
    assert manifest["reports"][0]["schema"] == "edgp.parallel.query.report.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"

    report = json.loads(
        (output_dir / "parallel-query-report.json").read_text(encoding="utf-8")
    )
    assert report["summary"]["inputType"] == "csr-artifact"
    assert report["summary"]["memoryMapped"] is True
    assert report["summary"]["nodeQueries"] == 2
    assert report["summary"]["pathQueries"] == 1
    assert report["results"][1]["nodes"] == ["lib==2.0.0", "app==1.0.0"]
    assert report["results"][2]["resultKind"] == "path"
    assert report["results"][2]["target"] == "core==1.0.0"
    assert report["results"][2]["nodes"] == [
        "app==1.0.0",
        "lib==2.0.0",
        "core==1.0.0",
    ]
    triage = json.loads((output_dir / "triage-summary.json").read_text())
    assert triage["summary"]["parallelQueryReports"] == 1
    assert triage["summary"]["parallelQueryQueries"] == 3
    assert triage["summary"]["parallelQueryNodeQueries"] == 2
    assert triage["summary"]["parallelQueryPathQueries"] == 1
    assert triage["summary"]["parallelQueryResultNodes"] == 7
    assert triage["summary"]["parallelQueryPathResultNodes"] == 3
    assert triage["summary"]["parallelQueryMemoryMappedReports"] == 1

    html = (output_dir / "001-parallel-query-report.html").read_text(
        encoding="utf-8"
    )
    assert 'data-testid="parallel-query-runtime-panel"' in html
    assert 'data-testid="parallel-query-results-panel"' in html
    assert "csr-artifact" in html
    assert "Path Queries" in html
    assert "core==1.0.0" in html
    index_html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "Parallel Query Report" in index_html

    assert main(["verify-bundle", "--path", str(output_dir), "--format", "text"]) == 0
    assert capsys.readouterr().out.startswith("OK ")

    assert (
        main(
            [
                "bundle-catalog",
                "--bundle",
                str(output_dir),
                "--output-dir",
                str(catalog_dir),
                "--format",
                "text",
            ]
        )
        == 0
    )
    catalog_output = capsys.readouterr().out.strip()
    assert "parallelQueryReports=1" in catalog_output
    assert "parallelQueryQueries=3" in catalog_output
    assert "parallelQueryNodeQueries=2" in catalog_output
    assert "parallelQueryPathQueries=1" in catalog_output
    assert "parallelQueryResultNodes=7" in catalog_output
    assert "parallelQueryPathResultNodes=3" in catalog_output
    assert "parallelQueryMemoryMappedReports=1" in catalog_output
    catalog = json.loads((catalog_dir / "bundle-catalog.json").read_text())
    assert catalog["summary"]["parallelQueryReports"] == 1
    assert catalog["summary"]["parallelQueryQueries"] == 3
    assert catalog["summary"]["parallelQueryNodeQueries"] == 2
    assert catalog["summary"]["parallelQueryPathQueries"] == 1
    assert catalog["summary"]["parallelQueryResultNodes"] == 7
    assert catalog["summary"]["parallelQueryPathResultNodes"] == 3
    assert catalog["summary"]["parallelQueryMemoryMappedReports"] == 1
