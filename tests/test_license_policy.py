"""License policy report tests for public graph metadata."""

from pathlib import Path

from src.adapters.cyclonedx import CycloneDXAdapter
from src.license_policy import build_license_report


def test_license_report_counts_missing_and_denied_licenses() -> None:
    resolved = CycloneDXAdapter().parse_graph(Path("tests/fixtures/sample-bom.json"))

    report = build_license_report(
        resolved.graph,
        root=resolved.root_identifier,
        ecosystem=resolved.ecosystem,
        denied_licenses=["WTFPL"],
    )

    assert report["schema"] == "edgp.license.report.v1"
    assert report["summary"] == {
        "packages": 2,
        "licensedPackages": 1,
        "missingLicenses": 1,
        "distinctLicenses": 1,
        "deniedFindings": 1,
    }
    assert report["licenses"] == [{"license": "WTFPL", "packages": 1}]
    assert report["findings"][0]["package"] == "left-pad==1.3.0"
    assert report["findings"][0]["matchedDeniedLicenses"] == ["WTFPL"]
    assert report["missingLicenses"][0]["package"] == "demo-app==1.0.0"


def test_license_report_matches_spdx_expression_tokens() -> None:
    resolved = CycloneDXAdapter().parse_graph(Path("tests/fixtures/sample-bom.json"))
    resolved.graph.set_vertex_metadata(
        "left-pad==1.3.0",
        {"license": "MIT OR Apache-2.0"},
    )

    report = build_license_report(
        resolved.graph,
        root=resolved.root_identifier,
        ecosystem=resolved.ecosystem,
        denied_licenses=["Apache-2.0"],
    )

    assert report["summary"]["deniedFindings"] == 1
    assert report["findings"][0]["license"] == "MIT OR Apache-2.0"
