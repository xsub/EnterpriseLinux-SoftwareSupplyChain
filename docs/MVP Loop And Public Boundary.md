# MVP Loop And Public Boundary

This project is developed in vertical slices:

1. Pick the next public, AlmaLinux-compatible capability.
2. Implement the smallest useful path end to end.
3. Validate locally with smoke checks from the installed project environment.
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
- public RPM repository `primary.xml`, `primary.xml.gz`, `repomd.xml`, or
  repository base URLs;
- public ALBS build metadata and build-log metadata embedded in ALBS payloads;
- public OSV-like advisory JSON payloads from local files or URLs, including
  explicit vulnerable versions, simple introduced/fixed ranges, and Package
  URL component locators;
- libsolv command discovery and saved transaction transcripts;
- local graph traversal, impact reporting, diffing, and JSON/Cypher/CycloneDX
  export;
- license metadata exposed by public SBOM, lockfile, RPM repository, and
  installed RPM inputs.

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
- Include local advisory overlays and normalized public advisory feed reports
  inside installed RPM database bundles.
- Include graph-matched libsolv-style transaction reports inside generated
  installed RPM database bundles on AlmaLinux-compatible hosts.
- Include installed RPM to public ALBS artifact provenance reports inside
  generated installed RPM database bundles.
- Render installed RPM to public ALBS artifact provenance joins as static,
  verifiable bundles.
- Render public ALBS build comparisons as static, verifiable bundles.
- Render public ALBS build-log intelligence reports as static, verifiable
  bundles.
- Render public ALBS release completeness reports as static, verifiable
  bundles.
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
  smoke validation against generated bundle manifests.
- Include per-report SHA-256 digests for report bundle source JSON and rendered
  HTML artifacts.
- Include a top-level report bundle fingerprint derived from the canonical
  manifest payload and member artifact digests.
- Verify generated report bundles with a local `verify-bundle` command that
  checks manifest shape, member digests, and the bundle fingerprint.
- Emit `verify-bundle` results as JSON by default, with a concise text format
  for terminal checks.
- Document `edgp.report.bundle.verification.v1` with a Draft 2020-12 JSON
  Schema and smoke validation against generated verifier output.
- Generate a deterministic schema index for documented EDGP JSON Schema
  contracts and validate that it stays current in the smoke suite.
- Smoke-test report schema documentation local links against committed files.
- Unit-test report schema documentation local links against committed files.
- Remove pasted source-span artifacts from the architecture research document.
- Smoke-test architecture documentation local links against committed files.
- Unit-test architecture documentation local links against committed files.
- Normalize architecture research headings for Markdown anchor generation.
- Smoke-test architecture documentation headings against expected anchors.
- Unit-test architecture documentation headings against expected anchors.
- Add quick links to the architecture research document.
- Smoke-test architecture research quick links against architecture headings.
- Unit-test architecture research quick links against architecture headings.
- Clean object-replacement extraction artifacts from the architecture research
  document.
- Smoke-test architecture research document for pasted extraction artifacts.
- Unit-test architecture research document for pasted extraction artifacts.
- Normalize architecture research bullet lists to Markdown syntax.
- Smoke-test architecture research Markdown list syntax.
- Unit-test architecture research Markdown list syntax.
- Link architecture research from the README.
- Smoke-test README architecture research link against the committed document.
- Unit-test README architecture research link against the committed document.
- Link README architecture research references to key section anchors.
- Smoke-test README architecture research anchors against architecture headings.
- Unit-test README architecture research anchors against architecture headings.
- Validate local EDGP JSON report files and report bundle directories with an
  installed `edgp validate` command.
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
- Provide committed validation and verification failure examples for unsupported
  bundle source kinds and invalid report digest fields.
- Provide committed validation and verification failure examples for invalid
  bundle metadata and bundle-local index paths.
- Provide committed validation and verification failure examples for manifest
  schema mismatches and invalid bundle fingerprint fields.
- Provide committed validation and verification failure examples for empty
  report lists and non-object report entries.
- Provide committed validation and verification failure examples for invalid
  report title fields and non-object report summaries.
- Provide committed validation and verification failure examples for mismatched
  report counts and bundle-escaping report hrefs.
- Provide committed validation and verification failure examples for missing
  bundle index files and mismatched source digests.
- Provide committed validation and verification failure examples for missing
  bundle manifests and invalid manifest JSON.
- Provide committed validation and verification failure examples for non-object
  bundle manifests, with smoke coverage for every stable verifier failure code.
- Generate a machine-readable validation failure example index for workbench
  and RAG ingestion.
- Generate a machine-readable validation failure example filter listing for
  workbench and RAG ingestion.
- Emit the validation failure example index through the `failure-examples` CLI
  command.
- Emit a compact text summary for validation failure examples.
- Document `edgp.validation.failure.example.index.v1` with a Draft 2020-12 JSON
  Schema and smoke validation against the committed index.
- Document `edgp.validation.failure.example.filters.v1` with a Draft 2020-12
  JSON Schema and smoke validation against generated filter output.
- Filter validation failure examples by validation or verifier failure code from
  the CLI.
- Filter validation failure examples by documented schema contract from the
  CLI.
- Filter validation failure examples by target artifact type from the CLI.
- Filter validation failure examples by stable example id from the CLI.
- List available validation failure example ids, target types, validation
  codes, and verifier codes from the CLI.
- Mention documented contracts in `failure-examples --list-codes` CLI help.
- Smoke-test `failure-examples --help` filter discoverability.
- Include verifier failure codes in compact validation failure example text
  output.
- Document combined validation failure example filter workflows in the README.
- Smoke-test combined validation failure example filter workflows.
- Unit-test combined validation failure example filter workflows.
- Add quick links for `failure-examples` workflows and representative fixtures
  in the validation examples guide.
- Smoke-test validation examples guide quick links against existing headings.
- Unit-test validation examples guide quick links against existing headings.
- Smoke-test validation examples guide local links against committed files.
- Unit-test validation examples guide local links against committed files.
- Link README validation failure example references directly to guide anchors.
- Smoke-test README validation guide anchors against existing headings.
- Unit-test README validation guide anchors against existing headings.
- Smoke-test README validation failure fixture links against committed files.
- Unit-test README validation failure fixture links against committed files.
- Smoke-test local README documentation links against committed files.
- Unit-test local README documentation links against committed files.
- Share reusable Markdown heading and anchor extraction helpers for
  documentation checks.
- Share reusable Markdown link target and path extraction helpers for
  documentation checks.
- Document filtered validation failure example workflows in the dedicated
  validation examples guide.
- Document validation failure example filter switches in the README.
- Link validation failure example index workflows from the README.
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
- Render reverse dependency impact reports as static, verifiable report
  bundles.
- Use human-friendly node selectors where a package name resolves to one graph
  node.
- Produce ecosystem-aware Package URLs for npm and RPM components.
- Preserve public RPM metadata including vendor, license, source RPM, install
  time, architecture, and non-zero epoch.
- Preserve public RPM origin/build hints including distribution, packager,
  upstream URL, and build host when present.
- Build public ALBS provenance graphs from build metadata.
- Generate ALBS artifact inventory, build timing, build diff, log intelligence,
  and release completeness reports.
- Join installed RPM database nodes to artifacts from public ALBS build
  metadata.
- Parse public RPM repository primary metadata into package/provider/requirement
  graphs.
- Discover primary metadata from public RPM `repomd.xml` files and repository
  base URLs.
- Generate RPM repository summary reports and static graph/summary bundles.
- Include local advisory overlays in generated RPM repository graph bundles.
- Compare two public RPM repository snapshots and report added, removed, and
  changed package EVR/source-RPM records.
- Render RPM repository snapshot diff reports as static, verifiable HTML
  bundles.
- Query public RPM repository graphs and run impact/advisory overlays over
  repository metadata through the shared graph analysis commands.
- Run advisory analysis directly from public OSV-like feeds without first
  writing a normalized overlay file.
- Render advisory analysis reports as static, verifiable report bundles.
- Return a CI-friendly non-zero advisory exit status when matched findings
  exist, while still emitting the JSON report.
- Apply a minimum severity threshold to advisory CI gates without filtering the
  emitted report.
- Interpret numeric CVSS-style advisory severity scores for CI gate decisions.
- Match SBOM components to public advisories by Package URL before falling back
  to package-name and version matching.
- Generate license inventory reports and fail CI-style checks when public graph
  metadata matches a denied license.
- Render license inventory reports as static, verifiable report bundles.
- Include license inventory and deny-list reports in generated npm, CycloneDX,
  public RPM repository, and installed RPM graph bundles.
- Return CI-friendly non-zero bundle exit status for denied license findings
  after writing the static report artifacts.
- Generate aggregate triage summaries from report lists or existing static
  report bundles for CI/workbench consumption.
- Return CI-friendly non-zero triage-summary exit status when aggregate bundle
  status reaches a selected warn/fail threshold.
- Embed generated triage summary JSON and HTML artifacts into static report
  bundles with manifest-recorded digests.
- Embed the same generated triage summary artifacts into graph bundle commands
  for npm, Maven, DOT, CycloneDX SBOM, public RPM repository, installed RPM,
  RPM repository diff, and ALBS build inputs.
- Return CI-friendly non-zero bundle exit status when generated triage summary
  status reaches a selected warn/fail threshold.
- Return CI-friendly non-zero validation exit status when an existing bundle
  triage summary reaches a selected warn/fail threshold.
- Match RPM advisory versions against full node versions, `version-release`
  EVR values, and non-zero `epoch:version-release` values.
- Report libsolv command availability and parse saved libsolv-style
  transaction transcripts.
- Normalize saved libsolv-style transaction package names into RPM metadata,
  EDGP graph node identifiers, and Package URLs.
- Match normalized libsolv-style transaction actions against an existing EDGP
  graph snapshot and report exact, candidate, and unmatched graph actions.
- Emit a flat libsolv transaction impact rollup sorted by affected dependents
  for browser, CI, workbench, and RAG consumers.
- Render saved libsolv-style transaction bridge reports as static, verifiable
  HTML bundles for browser review.
- Include graph-matched libsolv-style transaction reports inside generated
  public RPM repository bundles.
- Normalize OSV-like public advisory feeds from files or URLs into EDGP
  advisory overlays.
- Render normalized public advisory feeds as static, verifiable report bundles.
- Match normalized public advisory range intervals against RPM repository EVR
  metadata for impact reporting.
- Include normalized public advisory feeds and graph-matched advisory reports in
  generated RPM repository graph bundles.
- Generate performance reports for deterministic NumPy-backed CSR benchmark
  scenarios.
- Render deterministic performance reports as static, verifiable report
  bundles.

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
python -B -m src.cli rpm-installed-bundle --limit 5 --max-requirements 10 --impact-node rpm-installed==local --advisories tests/fixtures/rpm-advisories.json --public-advisory-feed tests/fixtures/public-osv.json --albs-build-path tests/fixtures/albs-build.json --libsolv-transaction tests/fixtures/libsolv-transaction.txt --output-dir /tmp/edgp-rpm-installed-bundle
python -B -m src.cli rpm-repo --source tests/fixtures/repodata/repomd.xml --format json
python -B -m src.cli rpm-repo-summary --source tests/fixtures/repodata/repomd.xml
python -B -m src.cli rpm-repo-bundle --source tests/fixtures/repodata/repomd.xml --impact-node nginx-core --advisories tests/fixtures/rpm-repo-advisories.json --public-advisory-feed tests/fixtures/public-osv-ranges.json --libsolv-transaction tests/fixtures/libsolv-transaction.txt --output-dir /tmp/edgp-rpm-repo-bundle
python -B -m src.cli rpm-albs-provenance-bundle --path tests/fixtures/albs-build.json --rpm-limit 5 --max-requirements 10 --output-dir /tmp/edgp-rpm-albs-provenance-bundle
python -B -m src.cli albs-build-diff-bundle --left-path tests/fixtures/albs-build.json --right-path tests/fixtures/albs-build-updated.json --output-dir /tmp/edgp-albs-build-diff-bundle
python -B -m src.cli albs-log-intelligence-bundle --path tests/fixtures/albs-build-updated.json --output-dir /tmp/edgp-albs-log-intelligence-bundle
python -B -m src.cli albs-release-completeness-bundle --path tests/fixtures/albs-build.json --path tests/fixtures/albs-build-updated.json --output-dir /tmp/edgp-albs-release-completeness-bundle
python -B -m src.cli query --source rpm-repo --path tests/fixtures/repodata/repomd.xml --operation dependencies --node nginx
python -B -m src.cli impact --source rpm-repo --path tests/fixtures/repodata/repomd.xml --node nginx-core
python -B -m src.cli advisory --source rpm-repo --path tests/fixtures/repodata/repomd.xml --advisories tests/fixtures/rpm-repo-advisories.json --ecosystem rpm
python -B -m src.cli advisory --source rpm-repo --path tests/fixtures/repodata/repomd.xml --public-advisory-feed tests/fixtures/public-osv-ranges.json --ecosystem rpm
python -B -m src.cli advisory --source rpm-repo --path tests/fixtures/repodata/repomd.xml --public-advisory-feed tests/fixtures/public-osv-ranges.json --ecosystem rpm --fail-on-findings --fail-min-severity high
python -B -m src.cli advisory-bundle --source rpm-repo --path tests/fixtures/repodata/repomd.xml --public-advisory-feed tests/fixtures/public-osv-ranges.json --ecosystem rpm --output-dir /tmp/edgp-advisory-bundle
python -B -m src.cli license-report-bundle --source sbom --path tests/fixtures/sample-bom.json --deny-license WTFPL --output-dir /tmp/edgp-license-report-bundle
python -B -m src.cli albs-build --path tests/fixtures/albs-build.json --format json
python -B -m src.cli albs-build-diff --left-path tests/fixtures/albs-build.json --right-path tests/fixtures/albs-build-updated.json
python -B -m src.cli albs-log-intelligence --path tests/fixtures/albs-build-updated.json
python -B -m src.cli albs-release-completeness --path tests/fixtures/albs-build.json --path tests/fixtures/albs-build-updated.json
python -B -m src.cli libsolv-bridge --transaction tests/fixtures/libsolv-transaction.txt
python -B -m src.cli libsolv-bridge --transaction tests/fixtures/libsolv-transaction.txt --graph-snapshot /tmp/edgp-rpm-repo.json
python -B -m src.cli libsolv-bundle --transaction tests/fixtures/libsolv-transaction.txt --graph-snapshot /tmp/edgp-rpm-repo.json --output-dir /tmp/edgp-libsolv-bundle
python -B -m src.cli public-advisory-feed --path tests/fixtures/public-osv.json --ecosystem rpm
python -B -m src.cli public-advisory-feed --path tests/fixtures/public-osv-ranges.json --ecosystem rpm
python -B -m src.cli public-advisory-feed --url file://$PWD/tests/fixtures/public-osv.json --ecosystem rpm
python -B -m src.cli public-advisory-feed-bundle --path tests/fixtures/public-osv.json --ecosystem rpm --output-dir /tmp/edgp-public-advisory-feed-bundle
python -B -m src.cli performance-report --scenario 1000:3 --scenario 10000:5
python -B -m src.cli performance-report-bundle --scenario 1000:3 --scenario 10000:5 --output-dir /tmp/edgp-performance-report-bundle
python -B -m src.cli query --source dot --path tests/fixtures/repograph.dot --ecosystem rpm --operation dependents --node glibc
python -B -m src.cli impact --path tests/fixtures/package-lock.json --node left-pad
python -B -m src.cli impact-bundle --path tests/fixtures/package-lock.json --node left-pad --output-dir /tmp/edgp-impact-bundle
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
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-bundle-source-kind-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-digest-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-bundle-metadata-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-index-path-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-manifest-schema-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-bundle-digest-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-reports-list-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-entry-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-field-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-summary-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-count-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-href-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/missing-index-report-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/source-digest-mismatch-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/missing-manifest-report-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-json-manifest-bundle --format text
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-manifest-type-bundle --format text
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
python -B -m src.cli validate --path tests/fixtures/invalid-bundle-source-kind-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-digest-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-bundle-metadata-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-index-path-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-manifest-schema-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-bundle-digest-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-reports-list-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-entry-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-field-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-summary-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-count-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-href-bundle --format text
python -B -m src.cli validate --path tests/fixtures/missing-index-report-bundle --format text
python -B -m src.cli validate --path tests/fixtures/source-digest-mismatch-bundle --format text
python -B -m src.cli validate --path tests/fixtures/missing-manifest-report-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-json-manifest-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-manifest-type-bundle --format text
python -B -m src.cli validate --path docs/validation-failure-example-index.json
python -B -m src.cli failure-examples
python -B -m src.cli failure-examples --format text
python -B -m src.cli failure-examples --list-codes
python -B -m src.cli failure-examples --id manifest-invalid
python -B -m src.cli failure-examples --code bundle.manifestInvalid
python -B -m src.cli failure-examples --target-type report-bundle --code manifestInvalid
python -B scripts/browser_smoke_report_sorting.py --output /tmp/edgp-report-sorting-smoke.html
python -B scripts/browser_smoke_report_bundle_navigation.py --output-dir /tmp/edgp-report-bundle-navigation-smoke
python -B scripts/generate_schema_index.py --check
python -B scripts/generate_failure_example_index.py --check
python -B -m src.cli benchmark --nodes 1000 --fanout 3
```
