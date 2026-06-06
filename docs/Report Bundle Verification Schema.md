# Report Bundle Verification Schema

`edgp verify-bundle` emits an `edgp.report.bundle.verification.v1` JSON report
by default. The JSON Schema for that report is maintained at
[`docs/schemas/edgp.report.bundle.verification.v1.schema.json`](schemas/edgp.report.bundle.verification.v1.schema.json).
Use `--format text` when a shell script only needs a concise one-line status.

## Top-Level Fields

- `schema`: always `edgp.report.bundle.verification.v1`.
- `bundleDir`: resolved local bundle directory that was checked.
- `manifest`: manifest filename read from the bundle directory, usually
  `manifest.json`.
- `ok`: `true` when no verification failures were found.
- `bundleSha256`: the manifest bundle fingerprint when available, or `null`
  when the manifest could not provide a valid fingerprint.
- `summary`: compact counters for `reports` and `failures`.
- `failures`: ordered failure records. Each failure has `code`, `message`, and
  `path`.

## Failure Codes

Failure codes are stable machine categories for ingestion and triage. Current
codes cover manifest shape, bundle fingerprint, and referenced artifact checks:

- `manifestMissing`
- `manifestInvalid`
- `manifestInvalidJson`
- `manifestMissingField`
- `manifestUnknownField`
- `manifestSchemaMismatch`
- `bundleDigestInvalid`
- `bundleDigestMismatch`
- `bundleInvalid`
- `bundleSourceKindInvalid`
- `indexInvalid`
- `indexMissing`
- `reportsInvalid`
- `reportCountMismatch`
- `reportInvalid`
- `reportMissingField`
- `reportUnknownField`
- `reportFieldInvalid`
- `reportHrefInvalid`
- `reportDigestInvalid`
- `reportSummaryInvalid`
- `htmlMissing`
- `htmlDigestMismatch`
- `sourceMissing`
- `sourceDigestMismatch`

## Example

```json
{
  "bundleDir": "/tmp/edgp-report-bundle",
  "bundleSha256": "0a42ea7dbb2dfbdf3c0a47f15e9c0d130aa9d99b6a9703bdbd6d0da7042f1987",
  "failures": [],
  "manifest": "manifest.json",
  "ok": true,
  "schema": "edgp.report.bundle.verification.v1",
  "summary": {
    "failures": 0,
    "reports": 2
  }
}
```

Failure example:

```json
{
  "bundleDir": "/tmp/edgp-report-bundle",
  "bundleSha256": "0a42ea7dbb2dfbdf3c0a47f15e9c0d130aa9d99b6a9703bdbd6d0da7042f1987",
  "failures": [
    {
      "code": "htmlDigestMismatch",
      "message": "reports[1] digest mismatch",
      "path": "/tmp/edgp-report-bundle/001-snapshot-right.html"
    }
  ],
  "manifest": "manifest.json",
  "ok": false,
  "schema": "edgp.report.bundle.verification.v1",
  "summary": {
    "failures": 1,
    "reports": 1
  }
}
```

Committed normalized failure fixtures are available for common bundle failure
cases:

- [`tests/fixtures/report-bundle-verification-tampered-manifest.json`](../tests/fixtures/report-bundle-verification-tampered-manifest.json)
- [`tests/fixtures/report-bundle-verification-tampered-member.json`](../tests/fixtures/report-bundle-verification-tampered-member.json)
- [`tests/fixtures/report-bundle-verification-missing-html.json`](../tests/fixtures/report-bundle-verification-missing-html.json)
- [`tests/fixtures/report-bundle-verification-missing-source.json`](../tests/fixtures/report-bundle-verification-missing-source.json)
- [`tests/fixtures/report-bundle-verification-invalid-manifest-missing-report-count.json`](../tests/fixtures/report-bundle-verification-invalid-manifest-missing-report-count.json)
- [`tests/fixtures/report-bundle-verification-invalid-report-missing-title.json`](../tests/fixtures/report-bundle-verification-invalid-report-missing-title.json)
