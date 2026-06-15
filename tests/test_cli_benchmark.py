"""CLI tests for synthetic CSR graph benchmarks."""

import json

from src.cli import main


def test_cli_benchmark_outputs_json(capsys) -> None:
    assert main(["benchmark", "--nodes", "6", "--fanout", "2"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.benchmark.v1"
    assert payload["stats"]["nodes"] == 6
    assert payload["stats"]["edges"] == 9
    assert payload["storage"]["layout"] == "numpy.int32.c_contiguous"


def test_cli_performance_report_bundle_writes_verifiable_bundle(
    capsys,
    tmp_path,
) -> None:
    output_dir = tmp_path / "performance-bundle"

    assert (
        main(
            [
                "performance-report-bundle",
                "--scenario",
                "8:2",
                "--scenario",
                "16:3",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "performance-report"
    assert manifest["reports"][0]["href"] == "001-performance-report.html"
    assert manifest["reports"][0]["schema"] == "edgp.performance.report.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"

    report = json.loads(
        (output_dir / "performance-report.json").read_text(encoding="utf-8")
    )
    assert report["schema"] == "edgp.performance.report.v1"
    assert report["summary"]["scenarios"] == 2
    assert report["summary"]["allContiguous"] is True
    assert report["summary"]["layout"] == "numpy.int32.c_contiguous"
    assert report["results"][0]["reverseReachableMs"] >= 0
    assert 'data-testid="performance-results-panel"' in (
        output_dir / "001-performance-report.html"
    ).read_text(encoding="utf-8")

    assert main(["verify-bundle", "--path", str(output_dir), "--format", "text"]) == 0
    assert capsys.readouterr().out.startswith("OK ")
