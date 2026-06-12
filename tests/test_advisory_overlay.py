"""Advisory overlay tests for local vulnerability-style graph context."""

from pathlib import Path

from src.adapters.rpm_repository import RpmRepositoryAdapter
from src.adapters.npm import NpmAdapter
from src.advisory_overlay import build_advisory_report_from_file


def test_advisory_overlay_matches_packages_and_embeds_impact() -> None:
    resolved = NpmAdapter().parse_lockfile_graph(Path("tests/fixtures/package-lock.json"))

    payload = build_advisory_report_from_file(
        Path("tests/fixtures/advisories.json"),
        resolved.graph,
        root=resolved.root_identifier,
        ecosystem=resolved.ecosystem,
    )

    assert payload["schema"] == "edgp.advisory.report.v1"
    assert payload["summary"] == {
        "advisories": 2,
        "findings": 1,
        "matchedPackages": 1,
        "affectedDependents": 2,
    }
    finding = payload["findings"][0]
    assert finding["advisory"]["id"] == "ADV-LOCAL-0001"
    assert finding["package"] == "left-pad==1.3.0"
    assert finding["impact"]["summary"]["affectedDependents"] == 2


def test_advisory_overlay_matches_rpm_repo_evr_without_arch_suffix() -> None:
    resolved = RpmRepositoryAdapter().parse_source(
        Path("tests/fixtures/repodata/repomd.xml")
    )

    payload = build_advisory_report_from_file(
        Path("tests/fixtures/rpm-repo-advisories.json"),
        resolved.graph,
        root=resolved.root_identifier,
        ecosystem=resolved.ecosystem,
    )

    assert payload["summary"]["findings"] == 1
    assert payload["findings"][0]["package"] == "nginx==1.20.1-16.el9_4.1.x86_64"
