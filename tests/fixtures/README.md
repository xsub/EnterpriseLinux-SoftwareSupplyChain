# Test Fixture Provenance

This directory mixes public-derived samples with synthetic edge-case payloads.
Tests must stay deterministic and offline, so public inputs are committed as
small curated excerpts rather than fetched live during every test run.
The same provenance is also available as the machine-readable EDGP report
`fixture-provenance.json`.

## Public-Derived Fixtures

- `rpm-primary.xml` and `rpm-primary-updated.xml` are curated excerpts from
  AlmaLinux 9 AppStream `x86_64` RPM repository `primary.xml.gz` metadata. The
  source repository root is
  `https://repo.almalinux.org/almalinux/9/AppStream/x86_64/os/`. The excerpts
  were refreshed on 2026-06-17 and keep real `nginx`, `nginx-core`, and
  `nginx-filesystem` package metadata, EVRs, provides, requirements, source RPM
  names, and checksums.
- `repodata/repomd.xml` is a local pointer fixture used to exercise primary
  metadata discovery. It resolves to the committed `rpm-primary.xml` excerpt so
  tests do not rely on network access.
- `albs-build.json` is a compact public ALBS build `17812` excerpt from
  `https://build.almalinux.org/api/v1/builds/17812/`. It preserves the real
  build ID, package names, architecture shape, build task layout, and artifact
  naming needed by the ALBS graph, inventory, timing, and provenance tests.
- `albs-build-updated.json` is a deterministic companion snapshot that models a
  later ALBS build state for diff, timing-delta, log-signal, and release
  completeness tests.

## Derived Report Fixtures

These files are generated from the public-derived inputs by EDGP code and are
committed to test schema stability and HTML rendering. The
`tests/test_public_fixture_freshness.py` suite verifies that these reports stay
in sync with their source fixtures and generator functions:

- `rpm-repository-summary.json`
- `rpm-repository-diff.json`
- `albs-artifact-inventory.json`
- `albs-build-timing.json`
- `albs-build-diff.json`
- `albs-log-intelligence.json`
- `albs-release-completeness.json`
- `rpm-albs-provenance.json`
- `libsolv-bridge.json`
- `real-data-coverage.json`

The provenance catalog is generated from the current fixture tree and committed
as `fixture-provenance.json`. The `tests/test_fixture_provenance.py` suite
verifies that it stays in sync with current fixture hashes, public source URLs,
and synthetic fixture groups.

Regenerate all derived public fixtures with:

```bash
python -B scripts/generate_public_fixture_reports.py
```

Check freshness without writing files with:

```bash
python -B scripts/generate_public_fixture_reports.py --check
python -B scripts/generate_fixture_provenance.py --check
```

Render the provenance catalog as static HTML with:

```bash
python -B -m src.cli fixture-provenance --fixture-dir tests/fixtures
python -B -m src.cli fixture-provenance-bundle --fixture-dir tests/fixtures --output-dir /tmp/edgp-fixture-provenance-bundle
python -B -m src.cli report --input tests/fixtures/fixture-provenance.json --output /tmp/edgp-fixture-provenance.html
python -B -m src.cli real-data-coverage --fixture-dir tests/fixtures
python -B -m src.cli real-data-coverage --fixture-dir tests/fixtures --fail-on-priority high
python -B -m src.cli real-data-coverage-bundle --fixture-dir tests/fixtures --output-dir /tmp/edgp-real-data-coverage-bundle
python -B -m src.cli real-data-coverage-bundle --fixture-dir tests/fixtures --output-dir /tmp/edgp-real-data-coverage-bundle --fail-on-priority high --fail-on-status fail
python -B -m src.cli report --input tests/fixtures/real-data-coverage.json --output /tmp/edgp-real-data-coverage.html
```

## Synthetic Fixtures

Some fixtures remain intentionally synthetic because they exercise parser
boundary cases, validation failures, advisory severity behavior, or tiny graph
topologies that are easier to audit by hand. Examples include npm lockfiles,
Maven tree snippets, SBOM snippets, graph snapshots, tampered bundles, and OSV
overlay examples.
