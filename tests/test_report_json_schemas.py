"""Schema contract tests for EDGP report JSON documents."""

import json
from pathlib import Path


SCHEMA_FIXTURES = {
    "edgp.albs.build_diff.v1": (
        Path("docs/schemas/edgp.albs.build_diff.v1.schema.json"),
        Path("tests/fixtures/albs-build-diff.json"),
    ),
    "edgp.albs.log_intelligence.v1": (
        Path("docs/schemas/edgp.albs.log_intelligence.v1.schema.json"),
        Path("tests/fixtures/albs-log-intelligence.json"),
    ),
    "edgp.albs.release_completeness.v1": (
        Path("docs/schemas/edgp.albs.release_completeness.v1.schema.json"),
        Path("tests/fixtures/albs-release-completeness.json"),
    ),
    "edgp.albs.artifact_inventory.v1": (
        Path("docs/schemas/edgp.albs.artifact_inventory.v1.schema.json"),
        Path("tests/fixtures/albs-artifact-inventory.json"),
    ),
    "edgp.albs.build_timing.v1": (
        Path("docs/schemas/edgp.albs.build_timing.v1.schema.json"),
        Path("tests/fixtures/albs-build-timing.json"),
    ),
    "edgp.graph.diff.v1": (
        Path("docs/schemas/edgp.graph.diff.v1.schema.json"),
        Path("tests/fixtures/graph-diff.json"),
    ),
    "edgp.graph.snapshot.v1": (
        Path("docs/schemas/edgp.graph.snapshot.v1.schema.json"),
        Path("tests/fixtures/snapshot-right.json"),
    ),
    "edgp.impact.report.v1": (
        Path("docs/schemas/edgp.impact.report.v1.schema.json"),
        Path("tests/fixtures/impact-report.json"),
    ),
    "edgp.advisory.report.v1": (
        Path("docs/schemas/edgp.advisory.report.v1.schema.json"),
        Path("tests/fixtures/advisory-report.json"),
    ),
    "edgp.bundle.catalog.v1": (
        Path("docs/schemas/edgp.bundle.catalog.v1.schema.json"),
        Path("tests/fixtures/bundle-catalog.json"),
    ),
    "edgp.export.batch.v1": (
        Path("docs/schemas/edgp.export.batch.v1.schema.json"),
        Path("tests/fixtures/export-batch.json"),
    ),
    "edgp.export.batch.verification.v1": (
        Path("docs/schemas/edgp.export.batch.verification.v1.schema.json"),
        Path("tests/fixtures/export-batch-verification.json"),
    ),
    "edgp.report.bundle.archive.v1": (
        Path("docs/schemas/edgp.report.bundle.archive.v1.schema.json"),
        Path("tests/fixtures/report-bundle-archive.json"),
    ),
    "edgp.npm.diagnostics.v1": (
        Path("docs/schemas/edgp.npm.diagnostics.v1.schema.json"),
        Path("tests/fixtures/npm-diagnostics-report.json"),
    ),
    "edgp.libsolv.bridge.v1": (
        Path("docs/schemas/edgp.libsolv.bridge.v1.schema.json"),
        Path("tests/fixtures/libsolv-bridge.json"),
    ),
    "edgp.license.report.v1": (
        Path("docs/schemas/edgp.license.report.v1.schema.json"),
        Path("tests/fixtures/license-report.json"),
    ),
    "edgp.performance.report.v1": (
        Path("docs/schemas/edgp.performance.report.v1.schema.json"),
        Path("tests/fixtures/performance-report.json"),
    ),
    "edgp.public.advisory_feed.v1": (
        Path("docs/schemas/edgp.public.advisory_feed.v1.schema.json"),
        Path("tests/fixtures/public-advisory-feed.json"),
    ),
    "edgp.query.report.v1": (
        Path("docs/schemas/edgp.query.report.v1.schema.json"),
        Path("tests/fixtures/query-report.json"),
    ),
    "edgp.rpm.albs_provenance.v1": (
        Path("docs/schemas/edgp.rpm.albs_provenance.v1.schema.json"),
        Path("tests/fixtures/rpm-albs-provenance.json"),
    ),
    "edgp.rpm.repository_summary.v1": (
        Path("docs/schemas/edgp.rpm.repository_summary.v1.schema.json"),
        Path("tests/fixtures/rpm-repository-summary.json"),
    ),
    "edgp.rpm.repository_diff.v1": (
        Path("docs/schemas/edgp.rpm.repository_diff.v1.schema.json"),
        Path("tests/fixtures/rpm-repository-diff.json"),
    ),
    "edgp.triage.summary.v1": (
        Path("docs/schemas/edgp.triage.summary.v1.schema.json"),
        Path("tests/fixtures/triage-summary.json"),
    ),
}


def test_report_json_schemas_document_fixture_shapes() -> None:
    for contract, (schema_path, fixture_path) in SCHEMA_FIXTURES.items():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))

        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["properties"]["schema"]["const"] == contract
        assert payload["schema"] == contract
        assert set(schema["required"]) <= set(payload)
        assert set(payload) <= set(schema["properties"])


def test_graph_snapshot_schema_documents_nested_shapes() -> None:
    schema = json.loads(
        Path("docs/schemas/edgp.graph.snapshot.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )

    node_schema = schema["properties"]["nodes"]["items"]
    edge_schema = schema["properties"]["edges"]["items"]
    ranking_schema = schema["properties"]["rankings"]["properties"][
        "mostDependedUpon"
    ]["items"]

    assert set(node_schema["required"]) == {
        "id",
        "name",
        "dependencies",
        "dependents",
        "metadata",
    }
    assert set(edge_schema["required"]) == {
        "source",
        "target",
        "relationshipType",
    }
    assert set(ranking_schema["required"]) == {"package", "dependents"}


def test_impact_and_advisory_schemas_share_impact_summary_shape() -> None:
    impact_schema = json.loads(
        Path("docs/schemas/edgp.impact.report.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    advisory_schema = json.loads(
        Path("docs/schemas/edgp.advisory.report.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )

    impact_summary_required = set(
        impact_schema["properties"]["summary"]["required"]
    )
    embedded_impact_summary_required = set(
        advisory_schema["$defs"]["impactReport"]["properties"]["summary"]["required"]
    )

    assert impact_summary_required == embedded_impact_summary_required
    assert impact_schema["properties"]["schema"]["const"] == "edgp.impact.report.v1"
    assert (
        advisory_schema["$defs"]["impactReport"]["properties"]["schema"]["const"]
        == "edgp.impact.report.v1"
    )


def test_npm_diagnostics_schema_documents_all_diagnostic_lists() -> None:
    schema = json.loads(
        Path("docs/schemas/edgp.npm.diagnostics.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert set(schema["properties"]["summary"]["required"]) == {
        "packages",
        "duplicatePackageNames",
        "nestedResolutionConflicts",
        "unresolvedDependencies",
    }
    assert set(schema["properties"]["duplicatePackageNames"]["items"]["required"]) == {
        "package",
        "versions",
    }
    assert set(
        schema["properties"]["nestedResolutionConflicts"]["items"]["required"]
    ) == {
        "dependency",
        "versions",
        "consumers",
    }
    assert set(schema["properties"]["unresolvedDependencies"]["items"]["required"]) == {
        "dependency",
        "requested",
        "source",
        "sourcePath",
        "searchedPaths",
    }


def test_albs_artifact_inventory_schema_documents_inventory_shapes() -> None:
    schema = json.loads(
        Path("docs/schemas/edgp.albs.artifact_inventory.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert set(schema["properties"]["summary"]["required"]) == {
        "artifacts",
        "buildTasks",
        "binaryRpms",
        "sourceRpms",
        "debugArtifacts",
        "buildLogs",
        "architectures",
        "packages",
    }
    assert set(schema["properties"]["items"]["items"]["required"]) == {
        "artifactNodeId",
        "artifactId",
        "filename",
        "artifactType",
        "artifactKind",
        "packageName",
        "version",
        "release",
        "artifactArch",
        "buildTaskId",
        "buildArch",
        "href",
        "casHash",
    }


def test_albs_build_timing_schema_documents_timing_shapes() -> None:
    schema = json.loads(
        Path("docs/schemas/edgp.albs.build_timing.v1.schema.json").read_text(
            encoding="utf-8"
        )
    )

    assert set(schema["properties"]["summary"]["required"]) == {
        "buildTasks",
        "signTasks",
        "artifacts",
        "aggregateBuildTaskWallSeconds",
        "criticalBuildTaskWallSeconds",
        "aggregateSignTaskWallSeconds",
    }
    assert set(schema["properties"]["taskTimings"]["items"]["required"]) == {
        "taskId",
        "arch",
        "status",
        "startedAt",
        "finishedAt",
        "wallSeconds",
        "artifactCounts",
        "steps",
        "testTasks",
        "testStepTotalsSeconds",
    }
    assert set(schema["properties"]["signTimings"]["items"]["required"]) == {
        "signTaskId",
        "status",
        "startedAt",
        "finishedAt",
        "wallSeconds",
        "statsSeconds",
    }
