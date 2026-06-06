# Validation Failure Examples

`edgp validate` returns an `edgp.validation.report.v1` payload for both passing
and failing checks. Failure records use stable `code`, `message`, and `path`
fields so terminal users, future workbench views, and RAG context builders can
triage malformed artifacts without parsing prose.

## Missing Required Field

The fixture
[`tests/fixtures/invalid-snapshot-missing-edge-count.json`](../tests/fixtures/invalid-snapshot-missing-edge-count.json)
is an `edgp.graph.snapshot.v1` payload with `stats.edges` removed.

Run:

```bash
python -B -m src.cli validate --path tests/fixtures/invalid-snapshot-missing-edge-count.json
```

Normalized result:

```json
{
  "contract": "edgp.graph.snapshot.v1",
  "failures": [
    {
      "code": "requiredMissing",
      "message": "Missing required field edges",
      "path": "$.stats.edges"
    }
  ],
  "ok": false,
  "schema": "edgp.validation.report.v1",
  "schemaFile": "edgp.graph.snapshot.v1.schema.json",
  "summary": {
    "failures": 1
  },
  "target": "<target>",
  "targetType": "json-file"
}
```

Text output:

```text
FAIL targetType=json-file failures=1 contract=edgp.graph.snapshot.v1 firstFailure=requiredMissing
```
