"""Fixture provenance catalog tests."""

import json
from pathlib import Path

from scripts.generate_fixture_provenance import build_fixture_provenance, main
from src.cli import main as cli_main
from src.output.html_report import render_report
from src.schema_validation import validate_target


FIXTURE_PATH = Path("tests/fixtures/fixture-provenance.json")


def _fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_fixture_provenance_matches_generator() -> None:
    assert _fixture() == build_fixture_provenance()


def test_fixture_provenance_generator_check_mode_passes() -> None:
    assert main(["--check"]) == 0


def test_fixture_provenance_validates_against_schema() -> None:
    report = validate_target(FIXTURE_PATH)

    assert report["ok"] is True
    assert report["contract"] == "edgp.fixture.provenance.v1"


def test_fixture_provenance_documents_public_and_generated_sources() -> None:
    payload = _fixture()
    entries = {entry["path"]: entry for entry in payload["entries"]}

    assert payload["summary"]["publicDerivedSources"] == 3
    assert payload["summary"]["generatedPublicReports"] == 14
    assert entries["tests/fixtures/rpm-primary.xml"]["sourceUrl"].startswith(
        "https://repo.almalinux.org/"
    )
    assert entries["tests/fixtures/albs-build.json"]["sourceUrl"].startswith(
        "https://build.almalinux.org/"
    )
    assert entries["tests/fixtures/public-osv-npm-lodash.json"]["sourceUrl"].startswith(
        "https://api.osv.dev/"
    )
    assert entries["tests/fixtures/rpm-repository-summary.json"]["generator"] == (
        "scripts/generate_public_fixture_reports.py"
    )


def test_fixture_provenance_renders_static_html() -> None:
    html = render_report(_fixture())

    assert "<!doctype html>" in html
    assert 'data-testid="fixture-provenance-entries-panel"' in html
    assert 'data-testid="fixture-provenance-synthetic-groups-panel"' in html
    assert "AlmaLinux 9 AppStream" in html


def test_cli_fixture_provenance_outputs_current_catalog(capsys) -> None:
    assert cli_main(["fixture-provenance", "--fixture-dir", "tests/fixtures"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == build_fixture_provenance()
    assert payload["schema"] == "edgp.fixture.provenance.v1"


def test_cli_fixture_provenance_bundle_writes_verifiable_bundle(
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "fixture-provenance-bundle"

    assert (
        cli_main(
            [
                "fixture-provenance-bundle",
                "--fixture-dir",
                "tests/fixtures",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert capsys.readouterr().out.strip() == str(output_dir / "index.html")
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "fixture-provenance"
    assert manifest["reports"][0]["href"] == "001-fixture-provenance.html"
    assert manifest["reports"][0]["schema"] == "edgp.fixture.provenance.v1"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"

    report = json.loads((output_dir / "fixture-provenance.json").read_text())
    assert report["summary"]["publicDerivedSources"] == 3
    html = (output_dir / "001-fixture-provenance.html").read_text(encoding="utf-8")
    assert 'data-testid="fixture-provenance-entries-panel"' in html

    assert cli_main(["verify-bundle", "--path", str(output_dir), "--format", "text"]) == 0
    assert capsys.readouterr().out.startswith("OK ")
