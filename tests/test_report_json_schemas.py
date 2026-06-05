"""Schema contract tests for EDGP report JSON documents."""

import json
from pathlib import Path


SCHEMA_FIXTURES = {
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
    "edgp.npm.diagnostics.v1": (
        Path("docs/schemas/edgp.npm.diagnostics.v1.schema.json"),
        Path("tests/fixtures/npm-diagnostics-report.json"),
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
