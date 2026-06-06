# MVP Loop And Public Boundary

This project is developed in vertical slices:

1. Pick the next public, AlmaLinux-compatible capability.
2. Implement the smallest useful path end to end.
3. Validate locally with dependency-free smoke checks.
4. Validate on the AlmaLinux VPS when the slice touches host/runtime behavior.
5. Commit and push to `origin/main`.
6. Reassess the next vertical.

## Current Public Boundary

The MVP intentionally avoids CloudLinux-only resources. The supported public
surfaces are:

- local Python 3.12+ execution;
- npm `package-lock.json` files;
- Poetry `poetry.lock` files;
- Cargo `Cargo.lock` files;
- Maven `dependency:tree` text output;
- CycloneDX JSON SBOMs;
- local advisory overlay JSON;
- directed DOT graphs, including `dnf repograph`-style block edges;
- installed RPM database inspection on AlmaLinux via the public `rpm` command;
- local graph traversal, impact reporting, diffing, and JSON/Cypher/CycloneDX
  export.

## Current Capabilities

- Build CSR dependency graphs from mock registries, npm lockfiles, DOT graphs,
  Poetry lockfiles, Cargo lockfiles, Maven dependency trees, CycloneDX SBOMs,
  and installed RPM metadata.
- Document `edgp.graph.snapshot.v1`, `edgp.impact.report.v1`,
  `edgp.advisory.report.v1`, and `edgp.npm.diagnostics.v1` with Draft 2020-12
  JSON Schemas and smoke validation against fixture payloads.
- Disambiguate Maven classifier-bearing and non-jar artifacts in graph node
  identifiers while preserving full Maven coordinates in node metadata.
- Preserve Maven dependency-tree optional and verbose omitted markers as node
  metadata when those markers are present in public text output.
- Emit Maven relationship types for dependency-tree edges: ordinary (`1`),
  optional (`2`), omitted (`3`), and excluded (`4`) when visible in public text
  output.
- Generate Maven dependency-tree graph bundle directories with optional impact
  reports.
- Generate DOT/RPM graph bundle directories with optional impact reports.
- Generate CycloneDX SBOM graph bundle directories with optional impact reports.
- Generate bounded installed RPM database bundle directories with optional
  impact reports on AlmaLinux-compatible hosts.
- Export graph data to Neo4j Cypher, CycloneDX, and EDGP JSON snapshots.
- Render local HTML reports from EDGP graph snapshot, impact, advisory, and npm
  diagnostics JSON.
- Label Maven optional, omitted, and excluded relationship types in graph
  snapshot HTML reports.
- Render filterable, windowed, and sortable graph snapshot edge explorer
  controls for static HTML reports so source/target text and relationship type
  can be narrowed in the browser without showing every matching row at once.
- Render sortable graph snapshot node metadata tables for static HTML reports.
- Generate a self-checking browser smoke HTML page for static graph report
  sorting behavior.
- Generate a self-checking browser smoke report bundle for static index
  navigation behavior.
- Render deterministic static HTML report bundles with an index for multiple
  EDGP JSON reports.
- Emit a machine-readable `manifest.json` for report bundles so future
  workbench and RAG integrations can ingest generated artifacts directly,
  including bundle-level source kind and generating command metadata.
- Document `edgp.report.bundle.v1` with a Draft 2020-12 JSON Schema and
  dependency-free smoke validation against generated bundle manifests.
- Include per-report SHA-256 digests for report bundle source JSON and rendered
  HTML artifacts.
- Include a top-level report bundle fingerprint derived from the canonical
  manifest payload and member artifact digests.
- Verify generated report bundles with a dependency-free `verify-bundle` command
  that checks manifest shape, member digests, and the bundle fingerprint.
- Emit `verify-bundle` results as JSON by default, with a concise text format
  for terminal checks.
- Document `edgp.report.bundle.verification.v1` with a Draft 2020-12 JSON
  Schema and dependency-free smoke validation against generated verifier
  output.
- Generate a deterministic schema index for documented EDGP JSON Schema
  contracts and validate that it stays current in the smoke suite.
- Validate local EDGP JSON report files and report bundle directories with a
  dependency-free `edgp validate` command.
- Provide committed validation failure examples for common malformed report
  payloads.
- Provide committed validation and verification failure examples for tampered
  report bundle manifests and member files.
- Provide committed validation and verification failure examples for missing
  report bundle HTML and source members.
- Provide committed validation and verification failure examples for invalid
  report bundle manifest shape, including missing top-level and report fields.
- Provide committed validation and verification failure examples for unknown
  top-level and report-entry fields in report bundle manifests.
- Provide a normalized machine-readable `verify-bundle` report fixture for
  RAG/workbench ingestion examples and regression checks.
- Render a compact verification summary on static bundle indexes with report
  count, manifest schema, and shortened bundle fingerprint.
- Use a shared graph bundle writer for npm, Maven, DOT, CycloneDX SBOM, and
  installed RPM bundle commands.
- Run deterministic synthetic CSR traversal benchmarks.
- Diff two EDGP JSON snapshots.
- Overlay local advisory JSON onto graph nodes.
- Query dependencies, dependents, reachability, shortest paths, and
  most-depended-upon rankings.
- Diagnose npm package-lock duplicate package names, nested version conflicts,
  and unresolved dependency declarations.
- Generate npm graph and diagnostics bundle directories directly from
  `package-lock.json` inputs.
- Include optional impact and local advisory reports in generated npm bundles.
- Report reverse dependency impact for a selected package.
- Use human-friendly node selectors where a package name resolves to one graph
  node.
- Produce ecosystem-aware Package URLs for npm and RPM components.
- Preserve public RPM metadata including vendor, license, source RPM, install
  time, architecture, and non-zero epoch.
- Preserve public RPM origin/build hints including distribution, packager,
  upstream URL, and build host when present.

## Validation Commands

Local:

```bash
python -B scripts/smoke_validate.py
```

AlmaLinux:

```bash
python3 -B scripts/smoke_validate.py --include-rpm-installed
```

Manual examples:

```bash
python -B -m src.cli lockfile --path tests/fixtures/package-lock.json --format json
python -B -m src.cli npm-diagnostics --path tests/fixtures/package-lock-conflict.json
python -B -m src.cli npm-bundle --path tests/fixtures/package-lock-conflict.json --output-dir /tmp/edgp-npm-bundle
python -B -m src.cli npm-bundle --path tests/fixtures/package-lock.json --impact-node left-pad --advisories tests/fixtures/advisories.json --output-dir /tmp/edgp-npm-advisory-bundle
python -B -m src.cli maven-tree --path tests/fixtures/maven-tree-classifier.txt --format json
python -B -m src.cli maven-tree --path tests/fixtures/maven-tree-packaging.txt --format json
python -B -m src.cli maven-tree --path tests/fixtures/maven-tree-markers.txt --format json
python -B -m src.cli maven-bundle --path tests/fixtures/maven-tree-classifier.txt --impact-node com.example:native-lib:linux-x86_64 --output-dir /tmp/edgp-maven-bundle
python -B -m src.cli dot --path tests/fixtures/repograph.dot --format cyclonedx
python -B -m src.cli dot-bundle --path tests/fixtures/repograph.dot --ecosystem rpm --impact-node glibc --output-dir /tmp/edgp-dot-bundle
python -B -m src.cli sbom --path tests/fixtures/sample-bom.json --format json
python -B -m src.cli sbom-bundle --path tests/fixtures/sample-bom.json --impact-node left-pad --output-dir /tmp/edgp-sbom-bundle
python -B -m src.cli rpm-installed-bundle --limit 5 --max-requirements 10 --impact-node rpm-installed==local --output-dir /tmp/edgp-rpm-installed-bundle
python -B -m src.cli query --source dot --path tests/fixtures/repograph.dot --ecosystem rpm --operation dependents --node glibc
python -B -m src.cli impact --path tests/fixtures/package-lock.json --node left-pad
python -B -m src.cli advisory --path tests/fixtures/package-lock.json --advisories tests/fixtures/advisories.json
python -B -m src.cli diff --left tests/fixtures/snapshot-left.json --right tests/fixtures/snapshot-right.json
python -B -m src.cli report --snapshot tests/fixtures/snapshot-right.json --output /tmp/edgp-report.html
python -B -m src.cli report --input tests/fixtures/impact-report.json --output /tmp/edgp-impact-report.html
python -B -m src.cli report --input tests/fixtures/advisory-report.json --output /tmp/edgp-advisory-report.html
python -B -m src.cli report --input tests/fixtures/npm-diagnostics-report.json --output /tmp/edgp-npm-diagnostics-report.html
python -B -m src.cli report-bundle --input tests/fixtures/snapshot-right.json --input tests/fixtures/npm-diagnostics-report.json --output-dir /tmp/edgp-report-bundle
python -B -m src.cli verify-bundle --path /tmp/edgp-report-bundle
python -B -m src.cli verify-bundle --path /tmp/edgp-report-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/tampered-report-bundle-manifest --format text
python -B -m src.cli verify-bundle --path tests/fixtures/tampered-report-bundle-member --format text
python -B -m src.cli verify-bundle --path tests/fixtures/missing-html-report-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/missing-source-report-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-manifest-missing-report-count-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-missing-title-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-manifest-unknown-field-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-unknown-field-bundle --format text
python -B -m src.cli validate --path tests/fixtures/snapshot-right.json
python -B -m src.cli validate --path tests/fixtures/invalid-snapshot-missing-edge-count.json
python -B -m src.cli validate --path /tmp/edgp-report-bundle --format text
python -B -m src.cli validate --path tests/fixtures/tampered-report-bundle-manifest --format text
python -B -m src.cli validate --path tests/fixtures/tampered-report-bundle-member --format text
python -B -m src.cli validate --path tests/fixtures/missing-html-report-bundle --format text
python -B -m src.cli validate --path tests/fixtures/missing-source-report-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-manifest-missing-report-count-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-missing-title-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-manifest-unknown-field-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-unknown-field-bundle --format text
python -B scripts/browser_smoke_report_sorting.py --output /tmp/edgp-report-sorting-smoke.html
python -B scripts/browser_smoke_report_bundle_navigation.py --output-dir /tmp/edgp-report-bundle-navigation-smoke
python -B scripts/generate_schema_index.py --check
python -B -m src.cli benchmark --nodes 1000 --fanout 3
```

## Next Vertical Options

- Add committed invalid-manifest-shape fixtures for `bundleSourceKindInvalid`
  and `reportDigestInvalid` verification failures.
