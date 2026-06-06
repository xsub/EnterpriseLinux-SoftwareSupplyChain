# Validation Failure Examples

`edgp validate` returns an `edgp.validation.report.v1` payload for both passing
and failing checks. Failure records use stable `code`, `message`, and `path`
fields so terminal users, future workbench views, and RAG context builders can
triage malformed artifacts without parsing prose.

A machine-readable index of committed examples is available at
[`docs/validation-failure-example-index.json`](validation-failure-example-index.json).
Its schema is documented at
[`docs/schemas/edgp.validation.failure.example.index.v1.schema.json`](schemas/edgp.validation.failure.example.index.v1.schema.json).
Regenerate or check it with
`python -B scripts/generate_failure_example_index.py --check`.

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

## Manifest Schema Mismatch

The fixture
[`tests/fixtures/invalid-manifest-schema-bundle`](../tests/fixtures/invalid-manifest-schema-bundle)
keeps a self-consistent manifest fingerprint but declares an unsupported
top-level manifest schema. The normalized verifier and validator results are
committed as
[`report-bundle-verification-invalid-manifest-schema.json`](../tests/fixtures/report-bundle-verification-invalid-manifest-schema.json)
and
[`validation-failure-invalid-manifest-schema.json`](../tests/fixtures/validation-failure-invalid-manifest-schema.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-manifest-schema-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-manifest-schema-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=6b6ec81304832919a624529e48f58d7dbefe9e9092a7345554c42443a3149447 firstFailure=manifestSchemaMismatch
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.manifestSchemaMismatch
```

## Invalid Bundle Fingerprint Field

The fixture
[`tests/fixtures/invalid-bundle-digest-bundle`](../tests/fixtures/invalid-bundle-digest-bundle)
sets the top-level `bundleSha256` field to a non-SHA-256 value. The verifier
normalizes this field to `null` in JSON output and omits `bundleSha256=` from
text output because the manifest did not provide a valid fingerprint. The
normalized verifier and validator results are committed as
[`report-bundle-verification-invalid-bundle-digest.json`](../tests/fixtures/report-bundle-verification-invalid-bundle-digest.json)
and
[`validation-failure-invalid-bundle-digest.json`](../tests/fixtures/validation-failure-invalid-bundle-digest.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-bundle-digest-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-bundle-digest-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 firstFailure=bundleDigestInvalid
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.bundleDigestInvalid
```

## Invalid Reports List

The fixture
[`tests/fixtures/invalid-reports-list-bundle`](../tests/fixtures/invalid-reports-list-bundle)
keeps a self-consistent manifest fingerprint but sets `reports` to an empty
list. The verifier treats report bundles as ingestible only when at least one
report entry is present. The normalized verifier and validator results are
committed as
[`report-bundle-verification-invalid-reports-list.json`](../tests/fixtures/report-bundle-verification-invalid-reports-list.json)
and
[`validation-failure-invalid-reports-list.json`](../tests/fixtures/validation-failure-invalid-reports-list.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-reports-list-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-reports-list-bundle --format text
```

Text output:

```text
FAIL reports=0 failures=1 bundleSha256=f13f0b8a771476fec2a7c13dae3fe3c5ce723b00814272e4849a3aa5c81f89ab firstFailure=reportsInvalid
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.reportsInvalid
```

## Invalid Report Entry

The fixture
[`tests/fixtures/invalid-report-entry-bundle`](../tests/fixtures/invalid-report-entry-bundle)
keeps a self-consistent manifest fingerprint but puts a scalar value inside the
`reports` list instead of a report object. The normalized verifier and
validator results are committed as
[`report-bundle-verification-invalid-report-entry.json`](../tests/fixtures/report-bundle-verification-invalid-report-entry.json)
and
[`validation-failure-invalid-report-entry.json`](../tests/fixtures/validation-failure-invalid-report-entry.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-entry-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-entry-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=c1bce2d00332c228e50e12ffa57c95b11bfd0c392b8e304f024060f8cc59053d firstFailure=reportInvalid
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.reportInvalid
```

## Invalid Report Field

The fixture
[`tests/fixtures/invalid-report-field-bundle`](../tests/fixtures/invalid-report-field-bundle)
keeps a self-consistent manifest fingerprint and valid member digests but sets
`reports[1].title` to an empty string. The normalized verifier and validator
results are committed as
[`report-bundle-verification-invalid-report-field.json`](../tests/fixtures/report-bundle-verification-invalid-report-field.json)
and
[`validation-failure-invalid-report-field.json`](../tests/fixtures/validation-failure-invalid-report-field.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-field-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-field-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=debaf87369ed315d2b66a294461184b952890ebf9bf58c58f0269b9c6579a804 firstFailure=reportFieldInvalid
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.reportFieldInvalid
```

## Invalid Report Summary

The fixture
[`tests/fixtures/invalid-report-summary-bundle`](../tests/fixtures/invalid-report-summary-bundle)
keeps a self-consistent manifest fingerprint and valid member digests but sets
`reports[1].summary` to a scalar value. The normalized verifier and validator
results are committed as
[`report-bundle-verification-invalid-report-summary.json`](../tests/fixtures/report-bundle-verification-invalid-report-summary.json)
and
[`validation-failure-invalid-report-summary.json`](../tests/fixtures/validation-failure-invalid-report-summary.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-summary-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-summary-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=0af994b1dadc21653806683048c2ea8a91c007e817084a1f5a60cac4b8cd3119 firstFailure=reportSummaryInvalid
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.reportSummaryInvalid
```

## Invalid Report Count

The fixture
[`tests/fixtures/invalid-report-count-bundle`](../tests/fixtures/invalid-report-count-bundle)
keeps a self-consistent manifest fingerprint and valid member digests but sets
`reportCount` to a value that does not match the number of report entries. The
normalized verifier and validator results are committed as
[`report-bundle-verification-invalid-report-count.json`](../tests/fixtures/report-bundle-verification-invalid-report-count.json)
and
[`validation-failure-invalid-report-count.json`](../tests/fixtures/validation-failure-invalid-report-count.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-count-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-count-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=be15c1acb06a07b5fa2ef87079f7e7caa4b52124fdc8c90321e2916bdc54aeb7 firstFailure=reportCountMismatch
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.reportCountMismatch
```

## Invalid Report Href

The fixture
[`tests/fixtures/invalid-report-href-bundle`](../tests/fixtures/invalid-report-href-bundle)
keeps a self-consistent manifest fingerprint but sets `reports[1].href` to a
path outside the bundle directory. The normalized verifier and validator
results are committed as
[`report-bundle-verification-invalid-report-href.json`](../tests/fixtures/report-bundle-verification-invalid-report-href.json)
and
[`validation-failure-invalid-report-href.json`](../tests/fixtures/validation-failure-invalid-report-href.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-report-href-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-report-href-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=2ab1110c5f27ad6eb179767747b4f1103092a94b24cfd91b56c8bd7b7dfe2940 firstFailure=reportHrefInvalid
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.reportHrefInvalid
```

## Missing Bundle Index

The fixture
[`tests/fixtures/missing-index-report-bundle`](../tests/fixtures/missing-index-report-bundle)
keeps a self-consistent manifest fingerprint and valid report member files but
omits the top-level `index.html` named by the manifest. The normalized verifier
and validator results are committed as
[`report-bundle-verification-missing-index.json`](../tests/fixtures/report-bundle-verification-missing-index.json)
and
[`validation-failure-missing-index.json`](../tests/fixtures/validation-failure-missing-index.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/missing-index-report-bundle --format text
python -B -m src.cli validate --path tests/fixtures/missing-index-report-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=2b3ad3949e47a4304825285e973a8fcf4e27197cf66520638d6615cb731cf092 firstFailure=indexMissing
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.indexMissing
```

## Source Digest Mismatch

The fixture
[`tests/fixtures/source-digest-mismatch-bundle`](../tests/fixtures/source-digest-mismatch-bundle)
keeps a self-consistent manifest fingerprint and valid member HTML, but the
manifest records an incorrect SHA-256 digest for the local `source.json` member.
The normalized verifier and validator results are committed as
[`report-bundle-verification-source-digest-mismatch.json`](../tests/fixtures/report-bundle-verification-source-digest-mismatch.json)
and
[`validation-failure-source-digest-mismatch.json`](../tests/fixtures/validation-failure-source-digest-mismatch.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/source-digest-mismatch-bundle --format text
python -B -m src.cli validate --path tests/fixtures/source-digest-mismatch-bundle --format text
```

Text output:

```text
FAIL reports=1 failures=1 bundleSha256=6031b6425cc8cecfac1d70473d31dfe1aa220e6d8d8c8a0ca8139f4c128845e3 firstFailure=sourceDigestMismatch
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.sourceDigestMismatch
```

## Missing Manifest

The fixture
[`tests/fixtures/missing-manifest-report-bundle`](../tests/fixtures/missing-manifest-report-bundle)
is a directory without `manifest.json`. Because no valid manifest is available,
the verifier reports `bundleSha256` as `null` in JSON output and omits
`bundleSha256=` from text output. The normalized verifier and validator results
are committed as
[`report-bundle-verification-missing-manifest.json`](../tests/fixtures/report-bundle-verification-missing-manifest.json)
and
[`validation-failure-missing-manifest.json`](../tests/fixtures/validation-failure-missing-manifest.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/missing-manifest-report-bundle --format text
python -B -m src.cli validate --path tests/fixtures/missing-manifest-report-bundle --format text
```

Text output:

```text
FAIL reports=0 failures=1 firstFailure=manifestMissing
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.manifestMissing
```

## Invalid Manifest JSON

The fixture
[`tests/fixtures/invalid-json-manifest-bundle`](../tests/fixtures/invalid-json-manifest-bundle)
contains a `manifest.json` file that cannot be parsed as JSON. Because no valid
manifest is available, the verifier reports `bundleSha256` as `null` in JSON
output and omits `bundleSha256=` from text output. The normalized verifier and
validator results are committed as
[`report-bundle-verification-invalid-json-manifest.json`](../tests/fixtures/report-bundle-verification-invalid-json-manifest.json)
and
[`validation-failure-invalid-json-manifest.json`](../tests/fixtures/validation-failure-invalid-json-manifest.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-json-manifest-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-json-manifest-bundle --format text
```

Text output:

```text
FAIL reports=0 failures=1 firstFailure=manifestInvalidJson
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.manifestInvalidJson
```

## Invalid Manifest Type

The fixture
[`tests/fixtures/invalid-manifest-type-bundle`](../tests/fixtures/invalid-manifest-type-bundle)
contains a syntactically valid `manifest.json` whose top-level value is not an
object. Because no valid manifest object is available, the verifier reports
`bundleSha256` as `null` in JSON output and omits `bundleSha256=` from text
output. The normalized verifier and validator results are committed as
[`report-bundle-verification-invalid-manifest-type.json`](../tests/fixtures/report-bundle-verification-invalid-manifest-type.json)
and
[`validation-failure-invalid-manifest-type.json`](../tests/fixtures/validation-failure-invalid-manifest-type.json).

Run:

```bash
python -B -m src.cli verify-bundle --path tests/fixtures/invalid-manifest-type-bundle --format text
python -B -m src.cli validate --path tests/fixtures/invalid-manifest-type-bundle --format text
```

Text output:

```text
FAIL reports=0 failures=1 firstFailure=manifestInvalid
FAIL targetType=report-bundle failures=1 contract=edgp.report.bundle.v1 firstFailure=bundle.manifestInvalid
```
