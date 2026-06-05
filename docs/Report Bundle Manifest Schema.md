# Report Bundle Manifest Schema

EDGP static report bundles include a machine-readable `manifest.json` beside
their `index.html`. The JSON Schema for the manifest is maintained at
[`docs/schemas/edgp.report.bundle.v1.schema.json`](schemas/edgp.report.bundle.v1.schema.json).

## Top-Level Fields

- `schema`: always `edgp.report.bundle.v1`.
- `index`: local bundle index HTML path, usually `index.html`.
- `reportCount`: number of generated report entries. EDGP smoke validation
  enforces that this equals the length of `reports`.
- `bundle`: optional source metadata. CLI-generated bundles use
  `bundle.sourceKind` and `bundle.command`.
- `reports`: ordered generated member reports. Each report has `href`,
  `schema`, `source`, `summary`, and `title`.

## Source Kinds

The public source-kind values are:

- `npm-lockfile`
- `maven-dependency-tree`
- `dot`
- `cyclonedx-sbom`
- `rpm-installed`
- `edgp-json`

## Example

```json
{
  "bundle": {
    "command": "edgp npm-bundle --path package-lock.json --output-dir reports/npm",
    "sourceKind": "npm-lockfile"
  },
  "index": "index.html",
  "reportCount": 2,
  "reports": [
    {
      "href": "001-npm-graph.html",
      "schema": "edgp.graph.snapshot.v1",
      "source": "npm-graph.json",
      "summary": {
        "edges": 3,
        "nodes": 4
      },
      "title": "Graph Snapshot - app==1.0.0"
    },
    {
      "href": "002-npm-diagnostics.html",
      "schema": "edgp.npm.diagnostics.v1",
      "source": "npm-diagnostics.json",
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
