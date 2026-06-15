"""Schema index tests for documented EDGP JSON Schema contracts."""

import json
from pathlib import Path

from scripts.generate_schema_index import build_schema_index


INDEX_PATH = Path("docs/schemas/index.json")


def test_schema_index_matches_generated_schema_contracts() -> None:
    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))

    assert index == build_schema_index()
    assert index["schema"] == "edgp.schema.index.v1"
    assert index["schemaCount"] == len(index["schemas"])
    assert {
        entry["contract"]
        for entry in index["schemas"]
        if "contract" in entry
    } == {
        "edgp.albs.build_diff.v1",
        "edgp.albs.log_intelligence.v1",
        "edgp.albs.release_completeness.v1",
        "edgp.albs.artifact_inventory.v1",
        "edgp.albs.build_timing.v1",
        "edgp.advisory.report.v1",
        "edgp.bundle.catalog.v1",
        "edgp.export.batch.archive.v1",
        "edgp.export.batch.submission_plan.v1",
        "edgp.export.batch.v1",
        "edgp.export.batch.verification.v1",
        "edgp.graph.diff.v1",
        "edgp.graph.snapshot.v1",
        "edgp.impact.report.v1",
        "edgp.libsolv.bridge.v1",
        "edgp.license.report.v1",
        "edgp.npm.diagnostics.v1",
        "edgp.performance.report.v1",
        "edgp.public.advisory_feed.v1",
        "edgp.query.report.v1",
        "edgp.report.bundle.archive.v1",
        "edgp.report.bundle.submission_plan.v1",
        "edgp.report.bundle.v1",
        "edgp.report.bundle.verification.v1",
        "edgp.rpm.albs_provenance.v1",
        "edgp.rpm.repository_diff.v1",
        "edgp.rpm.repository_summary.v1",
        "edgp.schema.index.v1",
        "edgp.submission.plan.index.v1",
        "edgp.triage.summary.v1",
        "edgp.validation.failure.example.filters.v1",
        "edgp.validation.failure.example.index.v1",
    }
