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
        ),
        (
            Path("tests/fixtures/tampered-report-bundle-member"),
            Path("tests/fixtures/report-bundle-verification-tampered-member.json"),
            Path("tests/fixtures/validation-failure-tampered-bundle-member.json"),
            "htmlDigestMismatch",
            "bundle.htmlDigestMismatch",
        ),
        (
            Path("tests/fixtures/missing-html-report-bundle"),
            Path("tests/fixtures/report-bundle-verification-missing-html.json"),
            Path("tests/fixtures/validation-failure-missing-bundle-html.json"),
            "htmlMissing",
            "bundle.htmlMissing",
        ),
        (
            Path("tests/fixtures/missing-source-report-bundle"),
            Path("tests/fixtures/report-bundle-verification-missing-source.json"),
            Path("tests/fixtures/validation-failure-missing-bundle-source.json"),
            "sourceMissing",
            "bundle.sourceMissing",
        ),
    ]

    for (
        bundle_dir,
        verification_fixture,
        validation_fixture,
        verify_code,
        validate_code,
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
        assert verification_text.startswith("FAIL reports=1 failures=1 bundleSha256=")
        assert f"firstFailure={verify_code}" in verification_text

        assert main(["validate", "--path", str(bundle_dir)]) == 1
        validation = json.loads(capsys.readouterr().out)
        expected_validation = json.loads(validation_fixture.read_text(encoding="utf-8"))
        assert _normalize_validation_report(validation) == expected_validation

        assert main(["validate", "--path", str(bundle_dir), "--format", "text"]) == 1
        validation_text = capsys.readouterr().out.strip()
        assert validation_text == (
            "FAIL targetType=report-bundle failures=1 "
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
