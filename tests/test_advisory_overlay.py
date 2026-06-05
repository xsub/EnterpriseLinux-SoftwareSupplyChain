"""Advisory overlay tests for local vulnerability-style graph context."""

from pathlib import Path

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
