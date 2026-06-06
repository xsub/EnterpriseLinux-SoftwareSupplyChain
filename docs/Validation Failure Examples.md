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

## Missing Report Bundle HTML Member

The fixture
[`tests/fixtures/missing-html-report-bundle`](../tests/fixtures/missing-html-report-bundle)
keeps a valid manifest fingerprint and source JSON reference but omits the
rendered member HTML named by `reports[1].href`. The normalized verifier and
validator results are committed as
[`report-bundle-verification-missing-html.json`](../tests/fixtures/report-bundle-verification-missing-html.json)
and
[`validation-failure-missing-bundle-html.json`](../tests/fixtures/validation-failure-missing-bundle-html.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/missing-html-report-bundle --format text
python -B -m src.cli validate --path tests/fixtures/missing-html-report-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=8f1cf84bdcac95148e666c23eac63f8297a5ab15df480e05feb8447dc298408e firstFailure=htmlMissing
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.htmlMissing
```

## Missing Report Bundle Source Member

The fixture
[`tests/fixtures/missing-source-report-bundle`](../tests/fixtures/missing-source-report-bundle)
keeps a valid manifest fingerprint and rendered HTML member but points
`reports[1].source` at a missing source JSON file. The normalized verifier and
validator results are committed as
[`report-bundle-verification-missing-source.json`](../tests/fixtures/report-bundle-verification-missing-source.json)
and
[`validation-failure-missing-bundle-source.json`](../tests/fixtures/validation-failure-missing-bundle-source.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/missing-source-report-bundle --format text
python -B -m src.cli validate --path tests/fixtures/missing-source-report-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=11fadb0fcc32bbd367550ea94d0f4daf0e71a8fa603c092bbf16f1e77ca5d47a firstFailure=sourceMissing
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.sourceMissing
```

## Missing Report Bundle Manifest Field

The fixture
[`tests/fixtures/invalid-manifest-missing-report-count-bundle`](../tests/fixtures/invalid-manifest-missing-report-count-bundle)
keeps a self-consistent manifest fingerprint but omits the required top-level
`reportCount` field. Verification reports both the missing required field and
the resulting count mismatch. The normalized verifier and validator results are
committed as
[`report-bundle-verification-invalid-manifest-missing-report-count.json`](../tests/fixtures/report-bundle-verification-invalid-manifest-missing-report-count.json)
and
[`validation-failure-invalid-manifest-missing-report-count.json`](../tests/fixtures/validation-failure-invalid-manifest-missing-report-count.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-manifest-missing-report-count-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-manifest-missing-report-count-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=2 bundleSha256=117f112bd2b6c4811db4e33251dcdba053e06967a7d4426d5ebc9e80ff0da150 firstFailure=manifestMissingField
FAIL targetType=report-bundle failures=2 contract=edgp.report.bundle.v1 firstFailure=bundle.manifestMissingField
```

## Missing Report Entry Field

The fixture
[`tests/fixtures/invalid-report-missing-title-bundle`](../tests/fixtures/invalid-report-missing-title-bundle)
keeps a self-consistent manifest fingerprint but omits the required
`reports[1].title` field. Verification reports the missing report field and the
resulting empty-title validation failure. The normalized verifier and validator
results are committed as
[`report-bundle-verification-invalid-report-missing-title.json`](../tests/fixtures/report-bundle-verification-invalid-report-missing-title.json)
and
[`validation-failure-invalid-report-missing-title.json`](../tests/fixtures/validation-failure-invalid-report-missing-title.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-missing-title-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-missing-title-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=2 bundleSha256=3c27816b9d793850f90d2c682b25827b4284e4d235973982da6502a47e581b6d firstFailure=reportMissingField
FAIL targetType=report-bundle failures=2 contract=edgp.report.bundle.v1 firstFailure=bundle.reportMissingField
```

## Unknown Report Bundle Manifest Field

The fixture
[`tests/fixtures/invalid-manifest-unknown-field-bundle`](../tests/fixtures/invalid-manifest-unknown-field-bundle)
keeps a self-consistent manifest fingerprint but adds an unsupported top-level
`unexpected` field. The normalized verifier and validator results are committed
as
[`report-bundle-verification-invalid-manifest-unknown-field.json`](../tests/fixtures/report-bundle-verification-invalid-manifest-unknown-field.json)
and
[`validation-failure-invalid-manifest-unknown-field.json`](../tests/fixtures/validation-failure-invalid-manifest-unknown-field.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-manifest-unknown-field-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-manifest-unknown-field-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=1efe6d2599447c473dd6c4f29d2c1283491f6d103504d61e4cc76855cc9bbb48 firstFailure=manifestUnknownField
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.manifestUnknownField
```

## Unknown Report Entry Field

The fixture
[`tests/fixtures/invalid-report-unknown-field-bundle`](../tests/fixtures/invalid-report-unknown-field-bundle)
keeps a self-consistent manifest fingerprint but adds an unsupported
`reports[1].unexpected` field. The normalized verifier and validator results
are committed as
[`report-bundle-verification-invalid-report-unknown-field.json`](../tests/fixtures/report-bundle-verification-invalid-report-unknown-field.json)
and
[`validation-failure-invalid-report-unknown-field.json`](../tests/fixtures/validation-failure-invalid-report-unknown-field.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-unknown-field-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-unknown-field-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=83d5e2941a20bafa81172a97e7fa3597a44c928b008b03af2b27565f0bab0306 firstFailure=reportUnknownField
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.reportUnknownField
```

## Unsupported Bundle Source Kind

The fixture
[`tests/fixtures/invalid-bundle-source-kind-bundle`](../tests/fixtures/invalid-bundle-source-kind-bundle)
keeps a self-consistent manifest fingerprint but sets `bundle.sourceKind` to an
unsupported public-boundary value. The normalized verifier and validator
results are committed as
[`report-bundle-verification-invalid-bundle-source-kind.json`](../tests/fixtures/report-bundle-verification-invalid-bundle-source-kind.json)
and
[`validation-failure-invalid-bundle-source-kind.json`](../tests/fixtures/validation-failure-invalid-bundle-source-kind.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-bundle-source-kind-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-bundle-source-kind-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=bebfd2865ded2310cd42348c392f4cbbd58d5e690ee7221874ffb9d7c3d1f697 firstFailure=bundleSourceKindInvalid
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.bundleSourceKindInvalid
```

## Invalid Report Digest Field

The fixture
[`tests/fixtures/invalid-report-digest-bundle`](../tests/fixtures/invalid-report-digest-bundle)
keeps a self-consistent manifest fingerprint but sets `reports[1].htmlSha256`
to a non-SHA-256 value. The normalized verifier and validator results are
committed as
[`report-bundle-verification-invalid-report-digest.json`](../tests/fixtures/report-bundle-verification-invalid-report-digest.json)
and
[`validation-failure-invalid-report-digest.json`](../tests/fixtures/validation-failure-invalid-report-digest.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-digest-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-digest-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=12500a13d5e0a3434417387f5e769830695cbe81498023f1fd70608c904a08bf firstFailure=reportDigestInvalid
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.reportDigestInvalid
```

## Invalid Bundle Metadata Field

The fixture
[`tests/fixtures/invalid-bundle-metadata-bundle`](../tests/fixtures/invalid-bundle-metadata-bundle)
keeps a self-consistent manifest fingerprint but sets the optional `bundle`
metadata field to a string instead of an object. The normalized verifier and
validator results are committed as
[`report-bundle-verification-invalid-bundle-metadata.json`](../tests/fixtures/report-bundle-verification-invalid-bundle-metadata.json)
and
[`validation-failure-invalid-bundle-metadata.json`](../tests/fixtures/validation-failure-invalid-bundle-metadata.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-bundle-metadata-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-bundle-metadata-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=39f1ed21e8e86005406b9ea5e20cc15cdf275c5fbb7fce63f9e5542b20294011 firstFailure=bundleInvalid
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.bundleInvalid
```

## Invalid Bundle Index Path

The fixture
[`tests/fixtures/invalid-index-path-bundle`](../tests/fixtures/invalid-index-path-bundle)
keeps a self-consistent manifest fingerprint but sets `index` to a path outside
the bundle directory. The normalized verifier and validator results are
committed as
[`report-bundle-verification-invalid-index-path.json`](../tests/fixtures/report-bundle-verification-invalid-index-path.json)
and
[`validation-failure-invalid-index-path.json`](../tests/fixtures/validation-failure-invalid-index-path.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-index-path-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-index-path-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=bfce2379da03171688e7810e8a2515704237e75c1322ef96f892f83efefb494b firstFailure=indexInvalid
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.indexInvalid
```
