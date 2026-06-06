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

## Tampered Report Bundle Manifest

The fixture
[`tests/fixtures/tampered-report-bundle-manifest`](../tests/fixtures/tampered-report-bundle-manifest)
contains a report bundle whose member source and HTML digests still match, but
whose manifest `bundleSha256` has been replaced with a zero digest. The
normalized verifier and validator results are committed as
[`report-bundle-verification-tampered-manifest.json`](../tests/fixtures/report-bundle-verification-tampered-manifest.json)
and
[`validation-failure-tampered-bundle-manifest.json`](../tests/fixtures/validation-failure-tampered-bundle-manifest.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/tampered-report-bundle-manifest --format text
python -B -m src.cli validate --path tests/fixtures/tampered-report-bundle-manifest --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=0000000000000000000000000000000000000000000000000000000000000000 firstFailure=bundleDigestMismatch
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.bundleDigestMismatch
```

## Tampered Report Bundle Member

The fixture
[`tests/fixtures/tampered-report-bundle-member`](../tests/fixtures/tampered-report-bundle-member)
keeps a self-consistent manifest fingerprint but changes the rendered member
HTML after the digest was recorded. The normalized verifier and validator
results are committed as
[`report-bundle-verification-tampered-member.json`](../tests/fixtures/report-bundle-verification-tampered-member.json)
and
[`validation-failure-tampered-bundle-member.json`](../tests/fixtures/validation-failure-tampered-bundle-member.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/tampered-report-bundle-member --format text
python -B -m src.cli validate --path tests/fixtures/tampered-report-bundle-member --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=c7981ee1692879fb130d77d6612cef7f5010824e9e5945bd19408b6d1f068951 firstFailure=htmlDigestMismatch
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.htmlDigestMismatch
```
