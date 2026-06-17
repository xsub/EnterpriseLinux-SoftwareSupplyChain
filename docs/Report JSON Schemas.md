# Report JSON Schemas

EDGP report JSON documents use stable `schema` identifiers so static HTML
reports, bundles, future workbench views, and RAG context builders can ingest
them without guessing the payload shape. Draft 2020-12 JSON Schemas live in
[`docs/schemas`](schemas), and the deterministic catalog is
[`docs/schemas/index.json`](schemas/index.json).

Run these after editing schema files:

```bash
python -B scripts/generate_schema_index.py --check
python -B -m src.cli validate --path docs/schemas/index.json
python -B -m src.cli report --input docs/schemas/index.json --output /tmp/edgp-schema-index.html
```

## Contracts

- `edgp.graph.snapshot.v1`:
  [`edgp.graph.snapshot.v1.schema.json`](schemas/edgp.graph.snapshot.v1.schema.json)
  documents graph nodes, directed edges, size counters, and rankings.
- `edgp.graph.diff.v1`:
  [`edgp.graph.diff.v1.schema.json`](schemas/edgp.graph.diff.v1.schema.json)
  documents added, removed, and metadata-changed graph elements between two
  EDGP graph snapshots, including optional package-level change classifications
  top package-change findings, and graph-diff policy gate verdicts.
- `edgp.graph.diff_tree.v1`:
  [`edgp.graph.diff_tree.v1.schema.json`](schemas/edgp.graph.diff_tree.v1.schema.json)
  documents dependency or dependent cone changes around one selected node in two
  EDGP graph snapshots, including top focused package-change findings and
  optional diff-tree policy gate verdicts.
- `edgp.query.report.v1`:
  [`edgp.query.report.v1.schema.json`](schemas/edgp.query.report.v1.schema.json)
  documents dependency, dependent, reachability, shortest-path, and
  most-depended-upon traversal query results.
- `edgp.parallel.query.report.v1`:
  [`edgp.parallel.query.report.v1.schema.json`](schemas/edgp.parallel.query.report.v1.schema.json)
  documents concurrent reachability query batches against frozen CSR runtimes.
- `edgp.csr.artifact.v1`:
  [`edgp.csr.artifact.v1.schema.json`](schemas/edgp.csr.artifact.v1.schema.json)
  documents memory-mappable frozen CSR artifact manifests, array paths, shapes,
  and SHA-256 digests.
- `edgp.fixture.provenance.v1`:
  [`edgp.fixture.provenance.v1.schema.json`](schemas/edgp.fixture.provenance.v1.schema.json)
  documents public-derived fixture sources, generated report fixtures, synthetic
  fixture groups, refresh commands, and stable fixture fingerprints.
- `edgp.real_data.coverage.v1`:
  [`edgp.real_data.coverage.v1.schema.json`](schemas/edgp.real_data.coverage.v1.schema.json)
  documents public evidence coverage, remaining synthetic fixture groups, and
  replacement-priority decisions derived from fixture provenance, including
  optional policy gate failures for CI.
- `edgp.real_data.replacement_plan.v1`:
  [`edgp.real_data.replacement_plan.v1.schema.json`](schemas/edgp.real_data.replacement_plan.v1.schema.json)
  ranks fixture groups that should move toward public-derived evidence, keeps
  intentionally deferred synthetic groups visible, and carries optional
  priority policy failures for CI.
- `edgp.real_data.coverage_diff.v1`:
  [`edgp.real_data.coverage_diff.v1.schema.json`](schemas/edgp.real_data.coverage_diff.v1.schema.json)
  compares two real-data coverage reports, including public-evidence deltas,
  replacement-plan changes, and optional regression policy failures for CI.
- `edgp.impact.report.v1`:
  [`edgp.impact.report.v1.schema.json`](schemas/edgp.impact.report.v1.schema.json)
  documents reverse dependency impact for one selected node.
- `edgp.advisory.report.v1`:
  [`edgp.advisory.report.v1.schema.json`](schemas/edgp.advisory.report.v1.schema.json)
  documents local advisory findings and their embedded impact reports.
- `edgp.bundle.catalog.v1`:
  [`edgp.bundle.catalog.v1.schema.json`](schemas/edgp.bundle.catalog.v1.schema.json)
  documents verified static report-bundle catalogs with source-kind triage
  status and per-bundle graph-diff, diff-tree, real-data coverage, and
  real-data coverage diff policy details, including failure-code lists, for
  batch CI and workbench ingestion.
- `edgp.export.batch.archive.v1`:
  [`edgp.export.batch.archive.v1.schema.json`](schemas/edgp.export.batch.archive.v1.schema.json)
  documents deterministic graph export batch archives for portable CI handoff.
- `edgp.export.batch.submission_plan.v1`:
  [`edgp.export.batch.submission_plan.v1.schema.json`](schemas/edgp.export.batch.submission_plan.v1.schema.json)
  documents offline dry-run submission plans for verified graph export batch
  directories or archives.
- `edgp.export.batch.v1`:
  [`edgp.export.batch.v1.schema.json`](schemas/edgp.export.batch.v1.schema.json)
  documents local Cypher, CycloneDX, and snapshot egress artifacts written from
  an EDGP graph snapshot.
- `edgp.export.batch.verification.v1`:
  [`edgp.export.batch.verification.v1.schema.json`](schemas/edgp.export.batch.verification.v1.schema.json)
  documents manifest and artifact fingerprint checks for local graph export
  batches.
- `edgp.report.bundle.archive.v1`:
  [`edgp.report.bundle.archive.v1.schema.json`](schemas/edgp.report.bundle.archive.v1.schema.json)
  documents deterministic archive packaging results for verified static report
  bundles.
- `edgp.report.bundle.submission_plan.v1`:
  [`edgp.report.bundle.submission_plan.v1.schema.json`](schemas/edgp.report.bundle.submission_plan.v1.schema.json)
  documents offline dry-run submission plans for verified report bundle
  directories or archives.
- `edgp.submission.plan.index.v1`:
  [`edgp.submission.plan.index.v1.schema.json`](schemas/edgp.submission.plan.index.v1.schema.json)
  documents aggregate CI/workbench status over multiple dry-run submission
  plans.
- `edgp.npm.diagnostics.v1`:
  [`edgp.npm.diagnostics.v1.schema.json`](schemas/edgp.npm.diagnostics.v1.schema.json)
  documents duplicate package names, nested version conflicts, and unresolved
  npm dependency declarations.
- `edgp.albs.artifact_inventory.v1`:
  [`edgp.albs.artifact_inventory.v1.schema.json`](schemas/edgp.albs.artifact_inventory.v1.schema.json)
  documents public ALBS build artifact inventory grouped by build architecture.
- `edgp.albs.build_timing.v1`:
  [`edgp.albs.build_timing.v1.schema.json`](schemas/edgp.albs.build_timing.v1.schema.json)
  documents public ALBS build task, sign task, and artifact timing.
- `edgp.albs.build_diff.v1`:
  [`edgp.albs.build_diff.v1.schema.json`](schemas/edgp.albs.build_diff.v1.schema.json)
  documents public ALBS build-to-build artifact, commit, and timing changes,
  including compact top findings for build-diff review.
- `edgp.albs.log_intelligence.v1`:
  [`edgp.albs.log_intelligence.v1.schema.json`](schemas/edgp.albs.log_intelligence.v1.schema.json)
  documents build-log artifacts and extracted warning/error/failure signals.
- `edgp.albs.release_completeness.v1`:
  [`edgp.albs.release_completeness.v1.schema.json`](schemas/edgp.albs.release_completeness.v1.schema.json)
  documents release coverage across public ALBS build batches.
- `edgp.rpm.albs_provenance.v1`:
  [`edgp.rpm.albs_provenance.v1.schema.json`](schemas/edgp.rpm.albs_provenance.v1.schema.json)
  documents installed RPM to ALBS artifact joins.
- `edgp.rpm.repository_summary.v1`:
  [`edgp.rpm.repository_summary.v1.schema.json`](schemas/edgp.rpm.repository_summary.v1.schema.json)
  documents public RPM repository package, source RPM, architecture, and
  unresolved requirement coverage.
- `edgp.rpm.repository_diff.v1`:
  [`edgp.rpm.repository_diff.v1.schema.json`](schemas/edgp.rpm.repository_diff.v1.schema.json)
  documents added, removed, and changed packages between public RPM repository
  snapshots, including compact top findings for package and source-RPM drift.
- `edgp.schema.index.v1`:
  [`edgp.schema.index.v1.schema.json`](schemas/edgp.schema.index.v1.schema.json)
  documents the deterministic catalog of supported EDGP JSON Schema contracts.
- `edgp.libsolv.bridge.v1`:
  [`edgp.libsolv.bridge.v1.schema.json`](schemas/edgp.libsolv.bridge.v1.schema.json)
  documents libsolv command discovery, parsed transaction actions, normalized
  RPM metadata, graph node IDs, Package URLs, and optional EDGP graph snapshot
  matches with flat transaction impact rollups.
- `edgp.license.report.v1`:
  [`edgp.license.report.v1.schema.json`](schemas/edgp.license.report.v1.schema.json)
  documents license inventory and deny-list policy findings.
- `edgp.public.advisory_feed.v1`:
  [`edgp.public.advisory_feed.v1.schema.json`](schemas/edgp.public.advisory_feed.v1.schema.json)
  documents normalized public advisory feeds and generated EDGP overlays.
- `edgp.performance.report.v1`:
  [`edgp.performance.report.v1.schema.json`](schemas/edgp.performance.report.v1.schema.json)
  documents synthetic CSR benchmark scenarios and storage profiles.
- `edgp.triage.summary.v1`:
  [`edgp.triage.summary.v1.schema.json`](schemas/edgp.triage.summary.v1.schema.json)
  documents aggregate triage status for EDGP reports and report bundles,
  including graph-diff, diff-tree, and bundle-catalog policy gate failures.
- `edgp.validation.report.v1`:
  [`edgp.validation.report.v1.schema.json`](schemas/edgp.validation.report.v1.schema.json)
  documents validation results emitted by `edgp validate` for JSON reports,
  report bundles, bundle archives, and export batches, including optional
  source report status, summary context, and top findings for standalone JSON
  artifacts or embedded bundle triage summaries.
- `edgp.validation.failure.example.index.v1`:
  [`edgp.validation.failure.example.index.v1.schema.json`](schemas/edgp.validation.failure.example.index.v1.schema.json)
  documents the committed validation failure example index.
- `edgp.validation.failure.example.filters.v1`:
  [`edgp.validation.failure.example.filters.v1.schema.json`](schemas/edgp.validation.failure.example.filters.v1.schema.json)
  documents the filter value listing emitted by
  `failure-examples --list-codes`.

Report bundle contracts are documented separately:

- [`Report Bundle Manifest Schema.md`](Report%20Bundle%20Manifest%20Schema.md)
- [`Report Bundle Verification Schema.md`](Report%20Bundle%20Verification%20Schema.md)
