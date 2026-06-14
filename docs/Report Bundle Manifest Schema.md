# Report Bundle Manifest Schema

EDGP static report bundles include a machine-readable `manifest.json` beside
their `index.html`. The JSON Schema for the manifest is maintained at
[`docs/schemas/edgp.report.bundle.v1.schema.json`](schemas/edgp.report.bundle.v1.schema.json).
Run `edgp verify-bundle --path <bundle-dir>` to check the manifest shape,
member source and HTML digests, and top-level bundle fingerprint. JSON output
is the default and is documented in
[`docs/Report Bundle Verification Schema.md`](Report%20Bundle%20Verification%20Schema.md);
use `--format text` for a concise terminal summary.

## Top-Level Fields

- `schema`: always `edgp.report.bundle.v1`.
- `bundleSha256`: SHA-256 digest of the canonical manifest payload excluding
  this field. Because each report entry includes source and HTML digests, this
  value is a portable fingerprint for the bundle contents.
- `index`: local bundle index HTML path, usually `index.html`.
- `reportCount`: number of generated report entries. EDGP smoke validation
  enforces that this equals the length of `reports`.
- `bundle`: optional source metadata. CLI-generated bundles use
  `bundle.sourceKind` and `bundle.command`.
- `reports`: ordered generated member reports. Each report has `href`,
  `htmlSha256`, `schema`, `source`, `sourceSha256`, `summary`, and `title`.
  The digests are SHA-256 hashes of the rendered HTML bytes and source JSON
  bytes used for that member report.
- `triageSummary`: optional generated aggregate triage summary artifact. It
  mirrors report-entry digest fields, but is kept outside `reports` so the
  summary describes the original bundle inputs rather than summarizing itself.

## Source Kinds

The public source-kind values are:

- `advisory-report`
- `albs-build`
- `albs-build-diff`
- `albs-artifact-inventory`
- `albs-build-timing`
- `albs-log-intelligence`
- `albs-release-completeness`
- `npm-diagnostics`
- `npm-lockfile`
- `maven-dependency-tree`
- `dot`
- `graph-diff`
- `cyclonedx-sbom`
- `rpm-albs-provenance`
- `rpm-installed`
- `rpm-repository`
- `rpm-repository-diff`
- `rpm-repository-summary`
- `impact-report`
- `license-report`
- `libsolv-transaction`
- `performance-report`
- `public-advisory-feed`
- `edgp-json`

## Example

```json
{
  "bundle": {
    "command": "edgp npm-bundle --path package-lock.json --output-dir reports/npm",
    "sourceKind": "npm-lockfile"
  },
  "bundleSha256": "0a42ea7dbb2dfbdf3c0a47f15e9c0d130aa9d99b6a9703bdbd6d0da7042f1987",
  "index": "index.html",
  "reportCount": 2,
  "reports": [
    {
      "href": "001-npm-graph.html",
      "htmlSha256": "3d3b87b582fa92c66adbe5991b804cb0b3cf8ecf4fb84f7f8b21f3084a595737",
      "schema": "edgp.graph.snapshot.v1",
      "source": "npm-graph.json",
      "sourceSha256": "49776dce6e8a9ed7a3f64d2dc32936d5d8f0155266d84dcadef1c0c88c20e661",
      "summary": {
        "edges": 3,
        "nodes": 4
      },
      "title": "Graph Snapshot - app==1.0.0"
    },
    {
      "href": "002-npm-diagnostics.html",
      "htmlSha256": "16db88bb562a9a9d3f1d62570538fd85d035777a902ecfa0f5d6caed4b6cf253",
      "schema": "edgp.npm.diagnostics.v1",
      "source": "npm-diagnostics.json",
      "sourceSha256": "b6fb9cf3ee166cd39d39abce793cc896f329fd05a6c72312598f3d97521f738a",
      "summary": {
        "duplicatePackageNames": 1,
        "nestedResolutionConflicts": 1,
        "packages": 4,
        "unresolvedDependencies": 1
      },
      "title": "npm Diagnostics - app==1.0.0"
    }
  ],
  "schema": "edgp.report.bundle.v1"
}
```
