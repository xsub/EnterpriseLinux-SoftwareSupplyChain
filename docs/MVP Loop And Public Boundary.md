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
- CycloneDX JSON SBOMs;
- directed DOT graphs, including `dnf repograph`-style block edges;
- installed RPM database inspection on AlmaLinux via the public `rpm` command;
- local graph traversal and JSON/Cypher/CycloneDX export.

## Current Capabilities

- Build CSR dependency graphs from mock registries, npm lockfiles, DOT graphs,
  CycloneDX SBOMs, and installed RPM metadata.
- Export graph data to Neo4j Cypher, CycloneDX, and EDGP JSON snapshots.
- Query dependencies, dependents, reachability, shortest paths, and
  most-depended-upon rankings.
- Use human-friendly node selectors where a package name resolves to one graph
  node.
- Produce ecosystem-aware Package URLs for npm and RPM components.

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
python -B -m src.cli dot --path tests/fixtures/repograph.dot --format cyclonedx
python -B -m src.cli sbom --path tests/fixtures/sample-bom.json --format json
python -B -m src.cli query --source dot --path tests/fixtures/repograph.dot --ecosystem rpm --operation dependents --node glibc
```

## Next Vertical Options

- Add a graph diff command for comparing two EDGP JSON snapshots.
- Add advisory/vulnerability overlay ingestion from a small public JSON format.
- Add reverse reachability reports for vulnerable or high-impact packages.
- Add a local HTML report for JSON snapshots.
- Add richer RPM metadata extraction, including vendor, epoch, and repository
  hints when available from public RPM query output.
- Add Poetry lockfile graph ingestion.
