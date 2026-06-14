"""Deterministic static HTML bundles for EDGP JSON reports."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.output.html_report import render_report
from src.triage_summary import build_triage_summary_report

BUNDLE_SHA256_KEY = "bundleSha256"
MANIFEST_SCHEMA = "edgp.report.bundle.v1"
VERIFICATION_SCHEMA = "edgp.report.bundle.verification.v1"
SOURCE_KINDS = {
    "advisory-report",
    "albs-build",
    "albs-build-diff",
    "albs-artifact-inventory",
    "albs-build-timing",
    "albs-log-intelligence",
    "albs-release-completeness",
    "cyclonedx-sbom",
    "dot",
    "edgp-json",
    "graph-diff",
    "impact-report",
    "license-report",
    "libsolv-transaction",
    "maven-dependency-tree",
    "npm-diagnostics",
    "npm-lockfile",
    "performance-report",
    "public-advisory-feed",
    "query-report",
    "rpm-albs-provenance",
    "rpm-installed",
    "rpm-repository",
    "rpm-repository-diff",
    "rpm-repository-summary",
}

_MANIFEST_REQUIRED_KEYS = {
    "schema",
    BUNDLE_SHA256_KEY,
    "index",
    "reportCount",
    "reports",
}
_MANIFEST_ALLOWED_KEYS = _MANIFEST_REQUIRED_KEYS | {"bundle", "triageSummary"}
_TRIAGE_SUMMARY_REQUIRED_KEYS = {
    "href",
    "htmlSha256",
    "schema",
    "source",
    "sourceSha256",
    "summary",
    "title",
}
_TRIAGE_SUMMARY_ALLOWED_KEYS = _TRIAGE_SUMMARY_REQUIRED_KEYS
_REPORT_REQUIRED_KEYS = {
    "href",
    "htmlSha256",
    "schema",
    "source",
    "sourceSha256",
    "summary",
    "title",
}
_REPORT_ALLOWED_KEYS = _REPORT_REQUIRED_KEYS


@dataclass(frozen=True)
class BundleEntry:
    source_path: Path
    output_path: Path
    schema: str
    title: str
    summary: dict[str, Any]
    source_sha256: str
    html_sha256: str


def write_report_bundle(
    input_paths: Sequence[Path],
    output_dir: Path,
    *,
    index_name: str = "index.html",
    manifest_name: str = "manifest.json",
    bundle_metadata: Mapping[str, object] | None = None,
    include_triage_summary: bool = False,
    triage_summary_name: str = "triage-summary.json",
) -> Path:
    if not input_paths:
        raise ValueError("At least one --input is required for a report bundle")

    output_dir.mkdir(parents=True, exist_ok=True)
    entries = []
    payloads = []
    for index, input_path in enumerate(input_paths, start=1):
        source_bytes = input_path.read_bytes()
        payload = json.loads(source_bytes.decode("utf-8"))
        payloads.append(payload)
        html = render_report(payload)
        html_bytes = html.encode("utf-8")
        output_path = output_dir / f"{index:03d}-{_safe_stem(input_path)}.html"
        output_path.write_bytes(html_bytes)
        entries.append(
            BundleEntry(
                source_path=input_path,
                output_path=output_path,
                schema=str(payload.get("schema", "")),
                title=_report_title(payload),
                summary=_report_summary(payload),
                source_sha256=_sha256(source_bytes),
                html_sha256=_sha256(html_bytes),
            )
        )

    triage_summary = None
    if include_triage_summary:
        triage_summary = _write_triage_summary_artifact(
            payloads,
            output_dir,
            source_name=triage_summary_name,
        )

    manifest = render_bundle_manifest(
        entries,
        index_name=index_name,
        bundle_metadata=bundle_metadata,
        triage_summary=triage_summary,
    )
    index_path = output_dir / index_name
    index_path.write_text(
        render_bundle_index(entries, manifest=manifest, triage_summary=triage_summary),
        encoding="utf-8",
    )
    manifest_path = output_dir / manifest_name
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return index_path


def render_bundle_manifest(
    entries: Sequence[BundleEntry],
    *,
    index_name: str = "index.html",
    bundle_metadata: Mapping[str, object] | None = None,
    triage_summary: BundleEntry | None = None,
) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "index": index_name,
        "reportCount": len(entries),
        "reports": [_manifest_entry(entry) for entry in entries],
    }
    if bundle_metadata:
        manifest["bundle"] = {
            str(key): str(value)
            for key, value in sorted(bundle_metadata.items())
            if value is not None
        }
    if triage_summary is not None:
        manifest["triageSummary"] = _manifest_entry(triage_summary)
    manifest[BUNDLE_SHA256_KEY] = _manifest_sha256(manifest)
    return manifest


def _write_triage_summary_artifact(
    payloads: Sequence[dict[str, Any]],
    output_dir: Path,
    *,
    source_name: str,
) -> BundleEntry:
    triage_report = build_triage_summary_report(
        payloads,
        source={"kind": "report-bundle-input", "reports": len(payloads)},
    )
    source_path = output_dir / source_name
    source_bytes = json.dumps(triage_report, indent=2, sort_keys=True).encode("utf-8")
    source_path.write_bytes(source_bytes)
    html = render_report(triage_report)
    html_bytes = html.encode("utf-8")
    output_path = output_dir / f"{_safe_stem(source_path)}.html"
    output_path.write_bytes(html_bytes)
    return BundleEntry(
        source_path=source_path,
        output_path=output_path,
        schema=str(triage_report.get("schema", "")),
        title=_report_title(triage_report),
        summary=_report_summary(triage_report),
        source_sha256=_sha256(source_bytes),
        html_sha256=_sha256(html_bytes),
    )


def _manifest_entry(entry: BundleEntry) -> dict[str, Any]:
    return {
        "href": entry.output_path.name,
        "htmlSha256": entry.html_sha256,
        "schema": entry.schema,
        "source": _source_label(entry),
        "sourceSha256": entry.source_sha256,
        "summary": entry.summary,
        "title": entry.title,
    }


def verify_report_bundle(
    bundle_dir: Path,
    *,
    manifest_name: str = "manifest.json",
) -> dict[str, Any]:
    bundle_dir = bundle_dir.resolve()
    manifest_path = bundle_dir / manifest_name
    failures: list[dict[str, str]] = []
    manifest: dict[str, Any] = {}

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            manifest = payload
        else:
            _add_failure(
                failures,
                "manifestInvalid",
                "Manifest must be a JSON object",
                manifest_path,
            )
    except FileNotFoundError:
        _add_failure(failures, "manifestMissing", f"Missing {manifest_name}", manifest_path)
    except json.JSONDecodeError as error:
        _add_failure(failures, "manifestInvalidJson", str(error), manifest_path)

    if manifest:
        _verify_manifest_shape(manifest, failures, manifest_path)
        _verify_manifest_fingerprint(manifest, failures, manifest_path)
        _verify_manifest_files(manifest, failures, bundle_dir)

    return {
        "schema": VERIFICATION_SCHEMA,
        "bundleDir": str(bundle_dir),
        "manifest": manifest_name,
        "ok": not failures,
        "bundleSha256": _verified_bundle_sha256(manifest),
        "summary": {
            "reports": len(manifest.get("reports", []))
            if isinstance(manifest.get("reports"), list)
            else 0,
            "failures": len(failures),
        },
        "failures": failures,
    }


def _verified_bundle_sha256(manifest: Mapping[str, Any]) -> str | None:
    bundle_sha = manifest.get(BUNDLE_SHA256_KEY)
    if isinstance(bundle_sha, str) and _is_sha256(bundle_sha):
        return bundle_sha
    return None


def _verify_manifest_shape(
    manifest: Mapping[str, Any],
    failures: list[dict[str, str]],
    manifest_path: Path,
) -> None:
    missing_keys = sorted(_MANIFEST_REQUIRED_KEYS - set(manifest))
    for key in missing_keys:
        _add_failure(
            failures,
            "manifestMissingField",
            f"Missing top-level field: {key}",
            manifest_path,
        )
    extra_keys = sorted(set(manifest) - _MANIFEST_ALLOWED_KEYS)
    for key in extra_keys:
        _add_failure(
            failures,
            "manifestUnknownField",
            f"Unsupported top-level field: {key}",
            manifest_path,
        )

    if manifest.get("schema") != MANIFEST_SCHEMA:
        _add_failure(
            failures,
            "manifestSchemaMismatch",
            f"Expected schema {MANIFEST_SCHEMA}",
            manifest_path,
        )
    if not _is_sha256(manifest.get(BUNDLE_SHA256_KEY)):
        _add_failure(
            failures,
            "bundleDigestInvalid",
            f"{BUNDLE_SHA256_KEY} must be a SHA-256 hex digest",
            manifest_path,
        )
    if not isinstance(manifest.get("index"), str) or not manifest.get("index"):
        _add_failure(
            failures,
            "indexInvalid",
            "index must be a non-empty string",
            manifest_path,
        )
    elif _bundle_member_path(bundle_dir=manifest_path.parent, label=manifest["index"]) is None:
        _add_failure(
            failures,
            "indexInvalid",
            "index must be a bundle-local relative path",
            manifest_path,
        )
    bundle = manifest.get("bundle")
    if bundle is not None:
        if not isinstance(bundle, dict):
            _add_failure(
                failures,
                "bundleInvalid",
                "bundle must be an object when present",
                manifest_path,
            )
        elif not all(isinstance(value, str) for value in bundle.values()):
            _add_failure(
                failures,
                "bundleInvalid",
                "bundle metadata values must be strings",
                manifest_path,
            )
        elif "sourceKind" in bundle and bundle["sourceKind"] not in SOURCE_KINDS:
            _add_failure(
                failures,
                "bundleSourceKindInvalid",
                "bundle.sourceKind is not a supported public source kind",
                manifest_path,
            )

    reports = manifest.get("reports")
    if not isinstance(reports, list) or not reports:
        _add_failure(
            failures,
            "reportsInvalid",
            "reports must be a non-empty list",
            manifest_path,
        )
        return

    if manifest.get("reportCount") != len(reports):
        _add_failure(
            failures,
            "reportCountMismatch",
            "reportCount must equal the number of reports",
            manifest_path,
        )

    for index, report in enumerate(reports, start=1):
        if not isinstance(report, dict):
            _add_failure(
                failures,
                "reportInvalid",
                f"reports[{index}] must be an object",
                manifest_path,
            )
            continue
        missing_report_keys = sorted(_REPORT_REQUIRED_KEYS - set(report))
        extra_report_keys = sorted(set(report) - _REPORT_ALLOWED_KEYS)
        for key in missing_report_keys:
            _add_failure(
                failures,
                "reportMissingField",
                f"reports[{index}] missing field: {key}",
                manifest_path,
            )
        for key in extra_report_keys:
            _add_failure(
                failures,
                "reportUnknownField",
                f"reports[{index}] has unsupported field: {key}",
                manifest_path,
            )
        for key in ("href", "schema", "source", "title"):
            if not isinstance(report.get(key), str) or not report.get(key):
                _add_failure(
                    failures,
                    "reportFieldInvalid",
                    f"reports[{index}].{key} must be a non-empty string",
                    manifest_path,
                )
        if isinstance(report.get("href"), str) and _bundle_member_path(
            bundle_dir=manifest_path.parent,
            label=report["href"],
        ) is None:
            _add_failure(
                failures,
                "reportHrefInvalid",
                f"reports[{index}].href must be a bundle-local relative path",
                manifest_path,
            )
        for key in ("htmlSha256", "sourceSha256"):
            if not _is_sha256(report.get(key)):
                _add_failure(
                    failures,
                    "reportDigestInvalid",
                    f"reports[{index}].{key} must be a SHA-256 hex digest",
                    manifest_path,
                )
        if not isinstance(report.get("summary"), dict):
            _add_failure(
                failures,
                "reportSummaryInvalid",
                f"reports[{index}].summary must be an object",
                manifest_path,
            )

    triage_summary = manifest.get("triageSummary")
    if triage_summary is not None:
        _verify_triage_summary_shape(triage_summary, failures, manifest_path)


def _verify_triage_summary_shape(
    triage_summary: object,
    failures: list[dict[str, str]],
    manifest_path: Path,
) -> None:
    if not isinstance(triage_summary, dict):
        _add_failure(
            failures,
            "triageSummaryInvalid",
            "triageSummary must be an object when present",
            manifest_path,
        )
        return
    missing_keys = sorted(_TRIAGE_SUMMARY_REQUIRED_KEYS - set(triage_summary))
    extra_keys = sorted(set(triage_summary) - _TRIAGE_SUMMARY_ALLOWED_KEYS)
    for key in missing_keys:
        _add_failure(
            failures,
            "triageSummaryMissingField",
            f"triageSummary missing field: {key}",
            manifest_path,
        )
    for key in extra_keys:
        _add_failure(
            failures,
            "triageSummaryUnknownField",
            f"triageSummary has unsupported field: {key}",
            manifest_path,
        )
    for key in ("href", "schema", "source", "title"):
        if not isinstance(triage_summary.get(key), str) or not triage_summary.get(key):
            _add_failure(
                failures,
                "triageSummaryFieldInvalid",
                f"triageSummary.{key} must be a non-empty string",
                manifest_path,
            )
    if triage_summary.get("schema") != "edgp.triage.summary.v1":
        _add_failure(
            failures,
            "triageSummarySchemaMismatch",
            "triageSummary.schema must be edgp.triage.summary.v1",
            manifest_path,
        )
    if isinstance(triage_summary.get("href"), str) and _bundle_member_path(
        bundle_dir=manifest_path.parent,
        label=triage_summary["href"],
    ) is None:
        _add_failure(
            failures,
            "triageSummaryHrefInvalid",
            "triageSummary.href must be a bundle-local relative path",
            manifest_path,
        )
    for key in ("htmlSha256", "sourceSha256"):
        if not _is_sha256(triage_summary.get(key)):
            _add_failure(
                failures,
                "triageSummaryDigestInvalid",
                f"triageSummary.{key} must be a SHA-256 hex digest",
                manifest_path,
            )
    if not isinstance(triage_summary.get("summary"), dict):
        _add_failure(
            failures,
            "triageSummarySummaryInvalid",
            "triageSummary.summary must be an object",
            manifest_path,
        )


def _verify_manifest_fingerprint(
    manifest: Mapping[str, Any],
    failures: list[dict[str, str]],
    manifest_path: Path,
) -> None:
    if not _is_sha256(manifest.get(BUNDLE_SHA256_KEY)):
        return
    actual = _manifest_sha256(manifest)
    if manifest.get(BUNDLE_SHA256_KEY) != actual:
        _add_failure(
            failures,
            "bundleDigestMismatch",
            f"{BUNDLE_SHA256_KEY} does not match canonical manifest payload",
            manifest_path,
        )


def _verify_manifest_files(
    manifest: Mapping[str, Any],
    failures: list[dict[str, str]],
    bundle_dir: Path,
) -> None:
    index_path = _bundle_member_path(bundle_dir, str(manifest.get("index", "")))
    if index_path is not None and not index_path.exists():
        _add_failure(failures, "indexMissing", "Index HTML is missing", index_path)

    reports = manifest.get("reports")
    if not isinstance(reports, list):
        return
    for index, report in enumerate(reports, start=1):
        if not isinstance(report, dict):
            continue
        html_path = _bundle_member_path(bundle_dir, str(report.get("href", "")))
        if html_path is None:
            continue
        _verify_file_digest(
            failures,
            code_prefix="html",
            expected=report.get("htmlSha256"),
            path=html_path,
            report_index=index,
        )
        source_path = _resolve_manifest_source(bundle_dir, str(report.get("source", "")))
        _verify_file_digest(
            failures,
            code_prefix="source",
            expected=report.get("sourceSha256"),
            path=source_path,
            report_index=index,
        )
    triage_summary = manifest.get("triageSummary")
    if isinstance(triage_summary, dict):
        html_path = _bundle_member_path(bundle_dir, str(triage_summary.get("href", "")))
        if html_path is not None:
            _verify_file_digest(
                failures,
                code_prefix="triageSummaryHtml",
                expected=triage_summary.get("htmlSha256"),
                path=html_path,
                report_index=0,
                subject="triageSummary",
            )
        source_path = _resolve_manifest_source(
            bundle_dir,
            str(triage_summary.get("source", "")),
        )
        _verify_file_digest(
            failures,
            code_prefix="triageSummarySource",
            expected=triage_summary.get("sourceSha256"),
            path=source_path,
            report_index=0,
            subject="triageSummary",
        )


def _verify_file_digest(
    failures: list[dict[str, str]],
    *,
    code_prefix: str,
    expected: object,
    path: Path,
    report_index: int,
    subject: str | None = None,
) -> None:
    label = subject or f"reports[{report_index}]"
    if not path.exists():
        _add_failure(
            failures,
            f"{code_prefix}Missing",
            f"{label} referenced file is missing",
            path,
        )
        return
    if not _is_sha256(expected):
        return
    actual = _sha256(path.read_bytes())
    if expected != actual:
        _add_failure(
            failures,
            f"{code_prefix}DigestMismatch",
            f"{label} digest mismatch",
            path,
        )


def _resolve_manifest_source(bundle_dir: Path, source_label: str) -> Path:
    source_path = Path(source_label)
    if source_path.is_absolute():
        return source_path
    for candidate in (bundle_dir / source_path, Path.cwd() / source_path):
        if candidate.exists():
            return candidate
    return bundle_dir / source_path


def _bundle_member_path(bundle_dir: Path, label: str) -> Path | None:
    member_path = Path(label)
    if member_path.is_absolute() or ".." in member_path.parts:
        return None
    return bundle_dir / member_path


def _add_failure(
    failures: list[dict[str, str]],
    code: str,
    message: str,
    path: Path,
) -> None:
    failures.append(
        {
            "code": code,
            "message": message,
            "path": str(path),
        }
    )


def _source_label(entry: BundleEntry) -> str:
    try:
        return str(entry.source_path.relative_to(entry.output_path.parent))
    except ValueError:
        return str(entry.source_path)


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _manifest_sha256(manifest: Mapping[str, Any]) -> str:
    digest_payload = {
        key: value for key, value in manifest.items() if key != BUNDLE_SHA256_KEY
    }
    canonical = json.dumps(
        digest_payload,
        separators=(",", ":"),
        sort_keys=True,
    )
    return _sha256(canonical.encode("utf-8"))


def render_bundle_index(
    entries: Sequence[BundleEntry],
    *,
    manifest: Mapping[str, Any],
    triage_summary: BundleEntry | None = None,
) -> str:
    cards = "\n".join(_entry_card(entry) for entry in entries)
    verification = _verification_summary(manifest)
    triage = _triage_summary_card(triage_summary)
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>EDGP Report Bundle</title>",
            f"<style>{_styles()}</style>",
            "</head>",
            "<body>",
            '<main class="bundle-shell">',
            '<section class="hero" data-testid="report-bundle-index">',
            "<div>",
            '<p class="eyebrow">EDGP</p>',
            "<h1>Report Bundle</h1>",
            "</div>",
            f"<p>{len(entries)} reports rendered for local dependency triage.</p>",
            "</section>",
            verification,
            triage,
            '<section class="reports">',
            cards,
            "</section>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def _triage_summary_card(entry: BundleEntry | None) -> str:
    if entry is None:
        return ""
    summary = entry.summary
    metrics = [
        ("Status", _read_generated_triage_status(entry.source_path)),
        ("Failed Checks", summary.get("failedChecks", 0)),
        ("Advisories", summary.get("advisoryFindings", 0)),
        ("Denied Licenses", summary.get("deniedLicenseFindings", 0)),
        ("npm Signals", _npm_signal_count(summary)),
    ]
    metric_items = "".join(
        "<li>"
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(str(value))}</strong>"
        "</li>"
        for label, value in metrics
    )
    return f"""
<section class="triage-summary" data-testid="report-bundle-triage-summary">
  <div>
    <p class="schema">{escape(entry.schema)}</p>
    <h2><a href="{escape(entry.output_path.name)}">{escape(entry.title)}</a></h2>
    <p class="source">{escape(entry.source_path.name)}</p>
  </div>
  <ul>{metric_items}</ul>
</section>""".strip()


def _read_generated_triage_status(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "n/a"
    return str(payload.get("status", "n/a"))


def _npm_signal_count(summary: Mapping[str, Any]) -> int:
    return sum(
        int(summary.get(key, 0))
        for key in (
            "npmDuplicatePackageNames",
            "npmNestedResolutionConflicts",
            "npmUnresolvedDependencies",
        )
    )


def _verification_summary(manifest: Mapping[str, Any]) -> str:
    bundle_sha = str(manifest.get(BUNDLE_SHA256_KEY, ""))
    bundle_sha_short = f"{bundle_sha[:12]}..." if bundle_sha else "n/a"
    report_count = escape(str(manifest.get("reportCount", 0)))
    schema = escape(str(manifest.get("schema", "")))
    return f"""
<section class="verification" data-testid="report-bundle-verification">
  <div>
    <span>Reports</span>
    <strong>{report_count}</strong>
  </div>
  <div>
    <span>Manifest</span>
    <strong>{schema}</strong>
  </div>
  <div>
    <span>Bundle SHA-256</span>
    <strong title="{escape(bundle_sha)}">{escape(bundle_sha_short)}</strong>
  </div>
</section>""".strip()


def _safe_stem(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip(".-_")
    return stem or "report"


def _report_title(payload: dict[str, Any]) -> str:
    schema = payload.get("schema")
    if schema == "edgp.graph.snapshot.v1":
        return f"Graph Snapshot - {payload.get('root') or 'graph'}"
    if schema == "edgp.graph.diff.v1":
        return "Graph Diff"
    if schema == "edgp.impact.report.v1":
        return f"Impact Report - {payload.get('node') or 'package'}"
    if schema == "edgp.advisory.report.v1":
        return f"Advisory Report - {payload.get('root') or 'graph'}"
    if schema == "edgp.npm.diagnostics.v1":
        return f"npm Diagnostics - {payload.get('root') or 'package-lock'}"
    if schema == "edgp.albs.artifact_inventory.v1":
        return f"ALBS Artifact Inventory - {payload.get('root') or 'build'}"
    if schema == "edgp.albs.build_timing.v1":
        return f"ALBS Build Timing - {payload.get('root') or 'build'}"
    if schema == "edgp.albs.build_diff.v1":
        left = payload.get("left", {})
        right = payload.get("right", {})
        if isinstance(left, dict) and isinstance(right, dict):
            return f"ALBS Build Diff - {left.get('buildId', '?')} to {right.get('buildId', '?')}"
        return "ALBS Build Diff"
    if schema == "edgp.rpm.albs_provenance.v1":
        return "RPM to ALBS Provenance"
    if schema == "edgp.rpm.repository_summary.v1":
        return f"RPM Repository Summary - {payload.get('root') or 'repository'}"
    if schema == "edgp.rpm.repository_diff.v1":
        return "RPM Repository Diff"
    if schema == "edgp.albs.log_intelligence.v1":
        return f"ALBS Log Intelligence - {payload.get('root') or 'build'}"
    if schema == "edgp.albs.release_completeness.v1":
        return "ALBS Release Completeness"
    if schema == "edgp.libsolv.bridge.v1":
        return "libsolv Bridge"
    if schema == "edgp.public.advisory_feed.v1":
        return "Public Advisory Feed"
    if schema == "edgp.query.report.v1":
        return f"Query Report - {payload.get('operation') or 'query'}"
    if schema == "edgp.performance.report.v1":
        return "Performance Report"
    if schema == "edgp.triage.summary.v1":
        return "Triage Summary"
    return str(schema or "EDGP Report")


def _report_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        return summary
    stats = payload.get("stats")
    if isinstance(stats, dict):
        return stats
    return {}


def _entry_card(entry: BundleEntry) -> str:
    metrics = "".join(
        "<li>"
        f"<span>{escape(_humanize_key(key))}</span>"
        f"<strong>{escape(str(value))}</strong>"
        "</li>"
        for key, value in sorted(entry.summary.items())
    )
    metrics = metrics or "<li><span>Summary</span><strong>n/a</strong></li>"
    href = escape(entry.output_path.name)
    return f"""
<article class="report-card" data-testid="report-bundle-entry">
  <div>
    <p class="schema">{escape(entry.schema)}</p>
    <h2><a href="{href}">{escape(entry.title)}</a></h2>
    <p class="source">{escape(str(entry.source_path))}</p>
  </div>
  <ul>{metrics}</ul>
</article>""".strip()


def _humanize_key(key: str) -> str:
    words = re.sub(r"(?<!^)([A-Z])", r" \1", key).replace("_", " ")
    return words.title()


def _styles() -> str:
    return """
:root {
  color-scheme: light;
  --ink: #172026;
  --muted: #5f6f7a;
  --line: #d8e1e5;
  --panel: #ffffff;
  --wash: #f5f7f4;
  --green: #2e7d5b;
  --blue: #2f6f9f;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--wash);
  color: var(--ink);
  font: 15px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.bundle-shell {
  width: min(1120px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 28px 0 40px;
}
.hero, .verification, .triage-summary, .report-card {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: end;
  padding: 28px;
  border-top: 5px solid var(--green);
}
.eyebrow, .schema {
  margin: 0 0 8px;
  color: var(--green);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}
h1, h2, p { margin-top: 0; letter-spacing: 0; }
h1 { margin-bottom: 0; font-size: 30px; line-height: 1.15; overflow-wrap: anywhere; }
h2 { margin-bottom: 8px; font-size: 18px; line-height: 1.25; overflow-wrap: anywhere; }
a { color: var(--blue); text-decoration-thickness: 2px; text-underline-offset: 3px; }
.verification {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 0;
  margin-top: 14px;
  overflow: hidden;
}
.verification div {
  min-width: 0;
  padding: 14px 16px;
  border-left: 1px solid var(--line);
}
.verification div:first-child { border-left: 0; }
.verification span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}
.verification strong {
  display: block;
  margin-top: 3px;
  overflow-wrap: anywhere;
}
.reports { display: grid; gap: 14px; margin-top: 18px; }
.triage-summary, .report-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, auto);
  gap: 20px;
  padding: 18px;
}
.triage-summary { margin-top: 14px; border-top: 5px solid var(--blue); }
.source { color: var(--muted); margin-bottom: 0; overflow-wrap: anywhere; }
ul {
  display: grid;
  grid-template-columns: repeat(2, minmax(96px, 1fr));
  gap: 10px;
  list-style: none;
  margin: 0;
  padding: 0;
}
li {
  min-width: 0;
  padding: 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
}
li span { display: block; color: var(--muted); font-size: 12px; }
li strong { display: block; margin-top: 2px; font-size: 18px; overflow-wrap: anywhere; }
@media (max-width: 760px) {
  .bundle-shell { width: min(100vw - 20px, 1120px); padding-top: 10px; }
  .hero, .triage-summary, .report-card { grid-template-columns: 1fr; display: grid; }
  .verification { grid-template-columns: 1fr; }
  .verification div { border-left: 0; border-top: 1px solid var(--line); }
  .verification div:first-child { border-top: 0; }
  ul { grid-template-columns: 1fr; }
}
""".strip()
