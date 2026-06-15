"""CLI tests for local HTML EDGP JSON reports."""

import json
from pathlib import Path

from src.cli import main


def test_cli_report_writes_html_snapshot_report(tmp_path, capsys) -> None:
    output_path = tmp_path / "snapshot-report.html"

    assert (
        main(
            [
                "report",
                "--snapshot",
                "tests/fixtures/snapshot-right.json",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_path
    html = output_path.read_text(encoding="utf-8")
    assert 'data-testid="report-hero"' in html
    assert "core==1.0.0" in html


def test_cli_report_writes_html_impact_report_from_input(tmp_path, capsys) -> None:
    output_path = tmp_path / "impact-report.html"

    assert (
        main(
            [
                "report",
                "--input",
                "tests/fixtures/impact-report.json",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_path
    html = output_path.read_text(encoding="utf-8")
    assert 'data-testid="impact-chains-panel"' in html
    assert "left-pad==1.3.0" in html


def test_cli_report_writes_html_advisory_report_from_input(tmp_path, capsys) -> None:
    output_path = tmp_path / "advisory-report.html"

    assert (
        main(
            [
                "report",
                "--input",
                "tests/fixtures/advisory-report.json",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_path
    html = output_path.read_text(encoding="utf-8")
    assert 'data-testid="advisory-findings-panel"' in html
    assert "ADV-LOCAL-0001" in html


def test_cli_report_writes_html_npm_diagnostics_report_from_input(
    tmp_path, capsys
) -> None:
    output_path = tmp_path / "npm-diagnostics-report.html"

    assert (
        main(
            [
                "report",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == output_path
    html = output_path.read_text(encoding="utf-8")
    assert 'data-testid="npm-conflicts-panel"' in html
    assert 'data-testid="npm-unresolved-panel"' in html
    assert "missing" in html


def test_cli_report_bundle_writes_index_and_member_reports(tmp_path, capsys) -> None:
    output_dir = tmp_path / "bundle"

    assert (
        main(
            [
                "report-bundle",
                "--input",
                "tests/fixtures/snapshot-right.json",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )

    index_path = output_dir / "index.html"
    assert Path(capsys.readouterr().out.strip()) == index_path
    html = index_path.read_text(encoding="utf-8")
    assert 'data-testid="report-bundle-index"' in html
    assert 'data-testid="report-bundle-verification"' in html
    assert "001-snapshot-right.html" in html
    assert "002-npm-diagnostics-report.html" in html
    assert (output_dir / "002-npm-diagnostics-report.html").exists()
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "edgp.report.bundle.v1"
    assert manifest["bundle"]["sourceKind"] == "edgp-json"
    assert manifest["bundle"]["command"].startswith("edgp report-bundle ")
    assert manifest["bundleSha256"][:12] in html
    assert manifest["reports"][1]["schema"] == "edgp.npm.diagnostics.v1"

    assert main(["verify-bundle", "--path", str(output_dir)]) == 0
    verification = json.loads(capsys.readouterr().out)
    assert verification["schema"] == "edgp.report.bundle.verification.v1"
    assert verification["ok"] is True
    assert verification["summary"] == {"reports": 2, "failures": 0}
    fixture = json.loads(
        Path("tests/fixtures/report-bundle-verification.json").read_text(
            encoding="utf-8"
        )
    )
    assert _normalize_verification_report(verification) == fixture
    assert main(["verify-bundle", "--path", str(output_dir), "--format", "text"]) == 0
    text = capsys.readouterr().out.strip()
    assert text.startswith("OK reports=2 failures=0 bundleSha256=")


def test_cli_report_bundle_can_include_triage_summary(tmp_path, capsys) -> None:
    output_dir = tmp_path / "bundle"

    assert (
        main(
            [
                "report-bundle",
                "--input",
                "tests/fixtures/advisory-report.json",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )

    index_path = Path(capsys.readouterr().out.strip())
    assert index_path == output_dir / "index.html"
    assert 'data-testid="report-bundle-triage-summary"' in index_path.read_text(
        encoding="utf-8"
    )

    triage = json.loads(
        (output_dir / "triage-summary.json").read_text(encoding="utf-8")
    )
    assert triage["schema"] == "edgp.triage.summary.v1"
    assert triage["status"] == "fail"
    assert triage["summary"]["reports"] == 2

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["reportCount"] == 2
    assert manifest["triageSummary"]["href"] == "triage-summary.html"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    assert main(["verify-bundle", "--path", str(output_dir)]) == 0


def test_cli_report_bundle_can_fail_on_triage_status(tmp_path, capsys) -> None:
    output_dir = tmp_path / "bundle"

    assert (
        main(
            [
                "report-bundle",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--output-dir",
                str(output_dir),
                "--fail-on-status",
                "warn",
            ]
        )
        == 2
    )

    assert Path(capsys.readouterr().out.strip()) == output_dir / "index.html"
    triage = json.loads((output_dir / "triage-summary.json").read_text(encoding="utf-8"))
    assert triage["schema"] == "edgp.triage.summary.v1"
    assert triage["status"] == "warn"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["triageSummary"]["source"] == "triage-summary.json"


def test_cli_archive_bundle_verifies_and_writes_deterministic_archive(
    tmp_path,
    capsys,
) -> None:
    output_dir = tmp_path / "bundle"
    archive_path = tmp_path / "bundle.tar.gz"

    assert (
        main(
            [
                "report-bundle",
                "--input",
                "tests/fixtures/snapshot-right.json",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "archive-bundle",
                "--path",
                str(output_dir),
                "--output",
                str(archive_path),
            ]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "edgp.report.bundle.archive.v1"
    assert payload["ok"] is True
    assert payload["archive"] == str(archive_path)
    assert payload["archiveSha256"]
    assert payload["summary"]["files"] == 4
    assert payload["summary"]["verificationFailures"] == 0
    assert archive_path.exists()

    assert (
        main(
            [
                "archive-bundle",
                "--path",
                str(output_dir),
                "--output",
                str(archive_path),
                "--format",
                "text",
            ]
        )
        == 0
    )
    text = capsys.readouterr().out.strip()
    assert text.startswith("OK files=4 bytes=")
    assert " verificationFailures=0 " in text
    assert "archiveSha256=" in text

    assert (
        main(
            [
                "verify-bundle-archive",
                "--path",
                str(archive_path),
            ]
        )
        == 0
    )
    verified = json.loads(capsys.readouterr().out)
    assert verified["schema"] == "edgp.report.bundle.archive.v1"
    assert verified["ok"] is True
    assert verified["archive"] == str(archive_path.resolve())
    assert verified["archiveSha256"] == payload["archiveSha256"]
    assert verified["bundleSha256"] == payload["bundleSha256"]
    assert verified["summary"]["files"] == 4
    assert verified["summary"]["verificationFailures"] == 0

    assert (
        main(
            [
                "verify-bundle-archive",
                "--path",
                str(archive_path),
                "--format",
                "text",
            ]
        )
        == 0
    )
    verified_text = capsys.readouterr().out.strip()
    assert verified_text.startswith("OK files=4 bytes=")
    assert " verificationFailures=0 " in verified_text

    assert main(["validate", "--path", str(archive_path)]) == 0
    validation = json.loads(capsys.readouterr().out)
    assert validation["schema"] == "edgp.validation.report.v1"
    assert validation["ok"] is True
    assert validation["targetType"] == "report-bundle-archive"
    assert validation["contract"] == "edgp.report.bundle.archive.v1"
    assert validation["bundleArchiveVerification"]["ok"] is True
    assert (
        validation["bundleArchiveVerification"]["archiveSha256"]
        == payload["archiveSha256"]
    )

    assert (
        main(["validate", "--path", str(archive_path), "--format", "text"])
        == 0
    )
    validation_text = capsys.readouterr().out.strip()
    assert validation_text == (
        "OK targetType=report-bundle-archive failures=0 "
        "contract=edgp.report.bundle.archive.v1"
    )

    (output_dir / "001-snapshot-right.html").write_text(
        "<!doctype html><title>tampered</title>",
        encoding="utf-8",
    )
    assert (
        main(
            [
                "archive-bundle",
                "--path",
                str(output_dir),
                "--output",
                str(tmp_path / "failed.tar.gz"),
            ]
        )
        == 1
    )
    failed = json.loads(capsys.readouterr().out)
    assert failed["ok"] is False
    assert failed["archiveSha256"] is None
    assert failed["summary"]["verificationFailures"] == 1


def test_cli_bundle_catalog_writes_report_bundle(tmp_path, capsys) -> None:
    graph_bundle = tmp_path / "graph-bundle"
    diagnostics_bundle = tmp_path / "diagnostics-bundle"
    diagnostics_archive = tmp_path / "diagnostics-bundle.tar.gz"
    catalog_dir = tmp_path / "catalog"
    catalog_archive = tmp_path / "catalog.tar.gz"

    assert (
        main(
            [
                "report-bundle",
                "--input",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(graph_bundle),
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "npm-diagnostics-bundle",
                "--path",
                "tests/fixtures/package-lock-conflict.json",
                "--output-dir",
                str(diagnostics_bundle),
                "--triage-summary",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            [
                "archive-bundle",
                "--path",
                str(diagnostics_bundle),
                "--output",
                str(diagnostics_archive),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "bundle-catalog",
                "--bundle",
                str(graph_bundle),
                "--bundle",
                str(diagnostics_archive),
                "--output-dir",
                str(catalog_dir),
                "--archive-output",
                str(catalog_archive),
                "--triage-summary",
            ]
        )
        == 0
    )

    assert Path(capsys.readouterr().out.strip()) == catalog_dir / "index.html"
    manifest = json.loads((catalog_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["bundle"]["sourceKind"] == "bundle-catalog"
    assert manifest["reports"][0]["schema"] == "edgp.bundle.catalog.v1"
    assert manifest["reports"][0]["href"] == "001-bundle-catalog.html"
    assert manifest["triageSummary"]["source"] == "triage-summary.json"
    catalog = json.loads((catalog_dir / "bundle-catalog.json").read_text(encoding="utf-8"))
    assert catalog["schema"] == "edgp.bundle.catalog.v1"
    assert catalog["summary"]["bundles"] == 2
    assert catalog["summary"]["okBundles"] == 2
    assert catalog["summary"]["triageWarn"] == 1
    assert catalog["bundles"][0]["inputType"] == "directory"
    assert catalog["bundles"][1]["inputType"] == "archive"
    assert catalog["bundles"][1]["path"] == str(diagnostics_archive.resolve())
    triage = json.loads((catalog_dir / "triage-summary.json").read_text(encoding="utf-8"))
    assert triage["status"] == "warn"
    assert triage["summary"]["catalogTriageWarn"] == 1
    html = (catalog_dir / "001-bundle-catalog.html").read_text(encoding="utf-8")
    assert 'data-testid="bundle-catalog-bundles-panel"' in html
    assert 'data-testid="bundle-catalog-source-kinds-panel"' in html
    assert "archive" in html
    assert main(["verify-bundle", "--path", str(catalog_dir)]) == 0
    capsys.readouterr()
    assert catalog_archive.exists()
    assert main(["verify-bundle-archive", "--path", str(catalog_archive)]) == 0
    archive_verification = json.loads(capsys.readouterr().out)
    assert archive_verification["ok"] is True
    assert archive_verification["bundleSha256"] == manifest["bundleSha256"]
    assert main(["validate", "--path", str(catalog_archive)]) == 0
    archive_validation = json.loads(capsys.readouterr().out)
    assert archive_validation["targetType"] == "report-bundle-archive"
    assert archive_validation["ok"] is True
    assert archive_validation["triageSummary"]["status"] == "warn"
    assert main(["triage-summary", "--bundle", str(catalog_archive)]) == 0
    archive_triage = json.loads(capsys.readouterr().out)
    assert archive_triage["source"]["kind"] == "bundle-archive"
    assert archive_triage["status"] == "warn"
    assert archive_triage["summary"]["catalogTriageWarn"] == 1


def test_cli_verify_bundle_reports_tampered_html(tmp_path, capsys) -> None:
    output_dir = tmp_path / "bundle"
    assert (
        main(
            [
                "report-bundle",
                "--input",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()

    (output_dir / "001-snapshot-right.html").write_text(
        "<!doctype html><title>tampered</title>",
        encoding="utf-8",
    )

    assert main(["verify-bundle", "--path", str(output_dir)]) == 1
    verification = json.loads(capsys.readouterr().out)
    assert verification["ok"] is False
    assert verification["summary"]["failures"] == 1
    assert verification["failures"][0]["code"] == "htmlDigestMismatch"
    assert main(["verify-bundle", "--path", str(output_dir), "--format", "text"]) == 1
    text = capsys.readouterr().out.strip()
    assert text.startswith("FAIL reports=1 failures=1 bundleSha256=")
    assert "firstFailure=htmlDigestMismatch" in text


def test_cli_verify_and_validate_committed_bundle_failure_fixtures(capsys) -> None:
    cases = [
        (
            Path("tests/fixtures/tampered-report-bundle-manifest"),
            Path("tests/fixtures/report-bundle-verification-tampered-manifest.json"),
            Path("tests/fixtures/validation-failure-tampered-bundle-manifest.json"),
            "bundleDigestMismatch",
            "bundle.bundleDigestMismatch",
            1,
        ),
        (
            Path("tests/fixtures/tampered-report-bundle-member"),
            Path("tests/fixtures/report-bundle-verification-tampered-member.json"),
            Path("tests/fixtures/validation-failure-tampered-bundle-member.json"),
            "htmlDigestMismatch",
            "bundle.htmlDigestMismatch",
            1,
        ),
        (
            Path("tests/fixtures/missing-html-report-bundle"),
            Path("tests/fixtures/report-bundle-verification-missing-html.json"),
            Path("tests/fixtures/validation-failure-missing-bundle-html.json"),
            "htmlMissing",
            "bundle.htmlMissing",
            1,
        ),
        (
            Path("tests/fixtures/missing-source-report-bundle"),
            Path("tests/fixtures/report-bundle-verification-missing-source.json"),
            Path("tests/fixtures/validation-failure-missing-bundle-source.json"),
            "sourceMissing",
            "bundle.sourceMissing",
            1,
        ),
        (
            Path("tests/fixtures/invalid-manifest-missing-report-count-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-manifest-missing-report-count.json"
            ),
            Path(
                "tests/fixtures/"
                "validation-failure-invalid-manifest-missing-report-count.json"
            ),
            "manifestMissingField",
            "bundle.manifestMissingField",
            2,
        ),
        (
            Path("tests/fixtures/invalid-report-missing-title-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-missing-title.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-report-missing-title.json"),
            "reportMissingField",
            "bundle.reportMissingField",
            2,
        ),
        (
            Path("tests/fixtures/invalid-manifest-unknown-field-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-manifest-unknown-field.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-manifest-unknown-field.json"),
            "manifestUnknownField",
            "bundle.manifestUnknownField",
            1,
        ),
        (
            Path("tests/fixtures/invalid-report-unknown-field-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-unknown-field.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-report-unknown-field.json"),
            "reportUnknownField",
            "bundle.reportUnknownField",
            1,
        ),
        (
            Path("tests/fixtures/invalid-bundle-source-kind-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-bundle-source-kind.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-bundle-source-kind.json"),
            "bundleSourceKindInvalid",
            "bundle.bundleSourceKindInvalid",
            1,
        ),
        (
            Path("tests/fixtures/invalid-report-digest-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-digest.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-report-digest.json"),
            "reportDigestInvalid",
            "bundle.reportDigestInvalid",
            1,
        ),
        (
            Path("tests/fixtures/invalid-bundle-metadata-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-bundle-metadata.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-bundle-metadata.json"),
            "bundleInvalid",
            "bundle.bundleInvalid",
            1,
        ),
        (
            Path("tests/fixtures/invalid-index-path-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-index-path.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-index-path.json"),
            "indexInvalid",
            "bundle.indexInvalid",
            1,
        ),
        (
            Path("tests/fixtures/invalid-manifest-schema-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-manifest-schema.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-manifest-schema.json"),
            "manifestSchemaMismatch",
            "bundle.manifestSchemaMismatch",
            1,
        ),
        (
            Path("tests/fixtures/invalid-bundle-digest-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-bundle-digest.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-bundle-digest.json"),
            "bundleDigestInvalid",
            "bundle.bundleDigestInvalid",
            1,
        ),
        (
            Path("tests/fixtures/invalid-reports-list-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-reports-list.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-reports-list.json"),
            "reportsInvalid",
            "bundle.reportsInvalid",
            1,
        ),
        (
            Path("tests/fixtures/invalid-report-entry-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-entry.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-report-entry.json"),
            "reportInvalid",
            "bundle.reportInvalid",
            1,
        ),
        (
            Path("tests/fixtures/invalid-report-field-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-field.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-report-field.json"),
            "reportFieldInvalid",
            "bundle.reportFieldInvalid",
            1,
        ),
        (
            Path("tests/fixtures/invalid-report-summary-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-summary.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-report-summary.json"),
            "reportSummaryInvalid",
            "bundle.reportSummaryInvalid",
            1,
        ),
        (
            Path("tests/fixtures/invalid-report-count-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-count.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-report-count.json"),
            "reportCountMismatch",
            "bundle.reportCountMismatch",
            1,
        ),
        (
            Path("tests/fixtures/invalid-report-href-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-report-href.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-report-href.json"),
            "reportHrefInvalid",
            "bundle.reportHrefInvalid",
            1,
        ),
        (
            Path("tests/fixtures/missing-index-report-bundle"),
            Path("tests/fixtures/report-bundle-verification-missing-index.json"),
            Path("tests/fixtures/validation-failure-missing-index.json"),
            "indexMissing",
            "bundle.indexMissing",
            1,
        ),
        (
            Path("tests/fixtures/source-digest-mismatch-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-source-digest-mismatch.json"
            ),
            Path("tests/fixtures/validation-failure-source-digest-mismatch.json"),
            "sourceDigestMismatch",
            "bundle.sourceDigestMismatch",
            1,
        ),
        (
            Path("tests/fixtures/missing-manifest-report-bundle"),
            Path("tests/fixtures/report-bundle-verification-missing-manifest.json"),
            Path("tests/fixtures/validation-failure-missing-manifest.json"),
            "manifestMissing",
            "bundle.manifestMissing",
            1,
        ),
        (
            Path("tests/fixtures/invalid-json-manifest-bundle"),
            Path(
                "tests/fixtures/"
                "report-bundle-verification-invalid-json-manifest.json"
            ),
            Path("tests/fixtures/validation-failure-invalid-json-manifest.json"),
            "manifestInvalidJson",
            "bundle.manifestInvalidJson",
            1,
        ),
        (
            Path("tests/fixtures/invalid-manifest-type-bundle"),
            Path("tests/fixtures/report-bundle-verification-invalid-manifest-type.json"),
            Path("tests/fixtures/validation-failure-invalid-manifest-type.json"),
            "manifestInvalid",
            "bundle.manifestInvalid",
            1,
        ),
    ]

    for (
        bundle_dir,
        verification_fixture,
        validation_fixture,
        verify_code,
        validate_code,
        failure_count,
    ) in cases:
        assert main(["verify-bundle", "--path", str(bundle_dir)]) == 1
        verification = json.loads(capsys.readouterr().out)
        expected_verification = json.loads(
            verification_fixture.read_text(encoding="utf-8")
        )
        assert _normalize_verification_report(verification) == expected_verification

        assert (
            main(["verify-bundle", "--path", str(bundle_dir), "--format", "text"])
            == 1
        )
        verification_text = capsys.readouterr().out.strip()
        no_report_codes = {
            "manifestInvalid",
            "manifestInvalidJson",
            "manifestMissing",
            "reportsInvalid",
        }
        no_bundle_sha_codes = {
            "bundleDigestInvalid",
            "manifestInvalid",
            "manifestInvalidJson",
            "manifestMissing",
        }
        report_count = 0 if verify_code in no_report_codes else 1
        if verify_code in no_bundle_sha_codes:
            assert verification_text.startswith(
                f"FAIL reports={report_count} failures={failure_count} "
            )
            assert "bundleSha256=" not in verification_text
        else:
            assert verification_text.startswith(
                f"FAIL reports={report_count} failures={failure_count} "
                "bundleSha256="
            )
        assert f"firstFailure={verify_code}" in verification_text

        assert main(["validate", "--path", str(bundle_dir)]) == 1
        validation = json.loads(capsys.readouterr().out)
        expected_validation = json.loads(validation_fixture.read_text(encoding="utf-8"))
        assert _normalize_validation_report(validation) == expected_validation

        assert main(["validate", "--path", str(bundle_dir), "--format", "text"]) == 1
        validation_text = capsys.readouterr().out.strip()
        assert validation_text == (
            f"FAIL targetType=report-bundle failures={failure_count} "
            f"contract=edgp.report.bundle.v1 firstFailure={validate_code}"
        )


def test_cli_validate_reports_json_contract(capsys) -> None:
    assert main(["validate", "--path", "tests/fixtures/snapshot-right.json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema"] == "edgp.validation.report.v1"
    assert report["ok"] is True
    assert report["targetType"] == "json-file"
    assert report["contract"] == "edgp.graph.snapshot.v1"

    assert (
        main(
            [
                "validate",
                "--path",
                "tests/fixtures/snapshot-right.json",
                "--format",
                "text",
            ]
        )
        == 0
    )
    text = capsys.readouterr().out.strip()
    assert text == (
        "OK targetType=json-file failures=0 contract=edgp.graph.snapshot.v1"
    )


def test_cli_validate_reports_json_contract_failure(capsys) -> None:
    path = "tests/fixtures/invalid-snapshot-missing-edge-count.json"

    assert main(["validate", "--path", path]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is False
    assert report["failures"] == [
        {
            "code": "requiredMissing",
            "message": "Missing required field edges",
            "path": "$.stats.edges",
        }
    ]

    assert main(["validate", "--path", path, "--format", "text"]) == 1
    text = capsys.readouterr().out.strip()
    assert text == (
        "FAIL targetType=json-file failures=1 "
        "contract=edgp.graph.snapshot.v1 firstFailure=requiredMissing"
    )


def test_cli_validate_reports_bundle_contract(tmp_path, capsys) -> None:
    output_dir = tmp_path / "bundle"
    assert (
        main(
            [
                "report-bundle",
                "--input",
                "tests/fixtures/snapshot-right.json",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(["validate", "--path", str(output_dir)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["targetType"] == "report-bundle"
    assert report["bundleVerification"]["ok"] is True


def test_cli_validate_can_fail_on_bundle_triage_status(tmp_path, capsys) -> None:
    output_dir = tmp_path / "bundle"
    assert (
        main(
            [
                "report-bundle",
                "--input",
                "tests/fixtures/npm-diagnostics-report.json",
                "--output-dir",
                str(output_dir),
                "--triage-summary",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        main(
            [
                "validate",
                "--path",
                str(output_dir),
                "--fail-on-status",
                "warn",
            ]
        )
        == 2
    )
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    assert report["triageSummary"]["status"] == "warn"

    assert (
        main(
            [
                "validate",
                "--path",
                str(output_dir),
                "--fail-on-status",
                "fail",
            ]
        )
        == 0
    )


def _normalize_verification_report(payload: dict[str, object]) -> dict[str, object]:
    normalized = dict(payload)
    bundle_dir = str(normalized.get("bundleDir", ""))
    normalized["bundleDir"] = "<bundle-dir>"
    if normalized.get("bundleSha256") is not None:
        normalized["bundleSha256"] = "<bundleSha256>"
    normalized["failures"] = _normalize_failure_paths(
        normalized.get("failures", []),
        bundle_dir,
    )
    return normalized


def _normalize_validation_report(payload: dict[str, object]) -> dict[str, object]:
    normalized = dict(payload)
    bundle_verification = normalized.get("bundleVerification")
    bundle_dir = ""
    if isinstance(bundle_verification, dict):
        bundle = dict(bundle_verification)
        bundle_dir = str(bundle.get("bundleDir", ""))
        bundle["bundleDir"] = "<bundle-dir>"
        if bundle.get("bundleSha256") is not None:
            bundle["bundleSha256"] = "<bundleSha256>"
        bundle["failures"] = _normalize_failure_paths(
            bundle.get("failures", []),
            bundle_dir,
        )
        normalized["bundleVerification"] = bundle
    normalized["target"] = "<target>"
    normalized["failures"] = _normalize_failure_paths(
        normalized.get("failures", []),
        bundle_dir,
    )
    return normalized


def _normalize_failure_paths(
    failures: object,
    bundle_dir: str,
) -> list[dict[str, object]]:
    normalized = []
    if not isinstance(failures, list):
        return normalized
    for failure in failures:
        if not isinstance(failure, dict):
            continue
        item = dict(failure)
        if bundle_dir and isinstance(item.get("path"), str):
            item["path"] = item["path"].replace(bundle_dir, "<bundle-dir>", 1)
        normalized.append(item)
    return normalized
