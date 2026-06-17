"""Advisory overlay tests for local vulnerability-style graph context."""

import json
from pathlib import Path

from src.adapters.cyclonedx import CycloneDXAdapter
from src.adapters.rpm_repository import RpmRepositoryAdapter
from src.adapters.npm import NpmAdapter
from src.advisory_overlay import build_advisory_report, build_advisory_report_from_file
from src.public_advisory_feed import build_public_advisory_feed_report


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
    assert payload["findings"][0]["package"] == "nginx==1.20.1-28.el9_8.2.alma.1.x86_64"


def test_advisory_overlay_matches_osv_range_for_rpm_evr() -> None:
    resolved = RpmRepositoryAdapter().parse_source(
        Path("tests/fixtures/repodata/repomd.xml")
    )
    feed = build_public_advisory_feed_report(
        json.loads(
            Path("tests/fixtures/public-osv-ranges.json").read_text(encoding="utf-8")
        ),
        ecosystem=resolved.ecosystem,
    )

    payload = build_advisory_report(
        feed["overlay"],
        resolved.graph,
        root=resolved.root_identifier,
        ecosystem=resolved.ecosystem,
    )

    assert payload["summary"]["findings"] == 1
    assert payload["findings"][0]["package"] == "nginx==1.20.1-28.el9_8.2.alma.1.x86_64"
    assert payload["findings"][0]["advisory"]["ranges"][0]["fixed"] == (
        "1.20.1-28.el9_8.2.alma.2"
    )

    nonmatching = build_advisory_report(
        {
            "schema": "edgp.advisory.overlay.v1",
            "advisories": [
                {
                    "id": "OSV-2026-0003",
                    "ecosystem": "rpm",
                    "package": "nginx",
                    "ranges": [
                        {
                            "type": "ECOSYSTEM",
                            "introduced": "1.20.1-28.el9_8.2.alma.2",
                            "fixed": "1.20.1-28.el9_8.2.alma.3",
                        }
                    ],
                }
            ],
        },
        resolved.graph,
        root=resolved.root_identifier,
        ecosystem=resolved.ecosystem,
    )
    assert nonmatching["summary"]["findings"] == 0


def test_advisory_overlay_matches_component_package_url() -> None:
    resolved = CycloneDXAdapter().parse_graph(Path("tests/fixtures/sample-bom.json"))

    payload = build_advisory_report(
        {
            "schema": "edgp.advisory.overlay.v1",
            "advisories": [
                {
                    "id": "ADV-PURL-0001",
                    "ecosystem": "npm",
                    "purl": "pkg:npm/left-pad@1.3.0?vendor=public",
                    "severity": "high",
                    "summary": "PURL-only advisory locator fixture.",
                }
            ],
        },
        resolved.graph,
        root=resolved.root_identifier,
        ecosystem=resolved.ecosystem,
    )

    assert payload["summary"]["findings"] == 1
    assert payload["findings"][0]["package"] == "left-pad==1.3.0"
