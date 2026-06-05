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
- Disambiguate Maven classifier-bearing and non-jar artifacts in graph node
  identifiers while preserving full Maven coordinates in node metadata.
- Generate Maven dependency-tree graph bundle directories with optional impact
  reports.
- Generate DOT/RPM graph bundle directories with optional impact reports.
- Generate CycloneDX SBOM graph bundle directories with optional impact reports.
- Generate bounded installed RPM database bundle directories with optional
  impact reports on AlmaLinux-compatible hosts.
- Export graph data to Neo4j Cypher, CycloneDX, and EDGP JSON snapshots.
- Render local HTML reports from EDGP graph snapshot, impact, advisory, and npm
  diagnostics JSON.
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
python -B -m src.cli benchmark --nodes 1000 --fanout 3
```

## Next Vertical Options

- Add Maven optional/excluded dependency markers if dependency-tree output
  exposes them in public fixtures.
- Add a machine-readable verification report fixture for RAG/workbench ingestion
  and golden-output regression tests.
