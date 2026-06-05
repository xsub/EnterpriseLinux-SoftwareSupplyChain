# Report JSON Schemas

EDGP report JSON documents use stable `schema` identifiers so static HTML
reports, bundles, future workbench views, and RAG context builders can ingest
them without guessing the payload shape. Draft 2020-12 JSON Schemas live in
[`docs/schemas`](schemas), and the deterministic catalog is
[`docs/schemas/index.json`](schemas/index.json).

Run this check after editing schema files:

```bash
python -B scripts/generate_schema_index.py --check
```

## Contracts

- `edgp.graph.snapshot.v1`:
  [`edgp.graph.snapshot.v1.schema.json`](schemas/edgp.graph.snapshot.v1.schema.json)
  documents graph nodes, directed edges, size counters, and rankings.
- `edgp.impact.report.v1`:
  [`edgp.impact.report.v1.schema.json`](schemas/edgp.impact.report.v1.schema.json)
  documents reverse dependency impact for one selected node.
- `edgp.advisory.report.v1`:
  [`edgp.advisory.report.v1.schema.json`](schemas/edgp.advisory.report.v1.schema.json)
  documents local advisory findings and their embedded impact reports.
- `edgp.npm.diagnostics.v1`:
  [`edgp.npm.diagnostics.v1.schema.json`](schemas/edgp.npm.diagnostics.v1.schema.json)
  documents duplicate package names, nested version conflicts, and unresolved
  npm dependency declarations.

Report bundle contracts are documented separately:

- [`Report Bundle Manifest Schema.md`](Report%20Bundle%20Manifest%20Schema.md)
- [`Report Bundle Verification Schema.md`](Report%20Bundle%20Verification%20Schema.md)
