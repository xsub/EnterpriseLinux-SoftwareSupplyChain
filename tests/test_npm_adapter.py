"""npm adapter tests for building CSR graphs from package-lock fixtures."""

from pathlib import Path

from src.adapters.npm import NpmAdapter


def test_npm_package_lock_v3_builds_csr_graph() -> None:
    resolved = NpmAdapter().parse_lockfile_graph(Path("tests/fixtures/package-lock.json"))

    assert resolved.root_identifier == "demo-app==1.0.0"
    assert resolved.graph.get_dependencies("demo-app==1.0.0") == [
        "@scope/tool==2.1.0",
        "left-pad==1.3.0",
    ]
    assert resolved.graph.get_dependencies("@scope/tool==2.1.0") == [
        "nested==1.0.1",
        "left-pad==1.3.0",
    ]
    assert resolved.graph.get_dependencies("left-pad==1.3.0") == []
    assert resolved.graph.get_vertex_metadata("@scope/tool==2.1.0") == {
        "ecosystem": "npm",
        "package_path": "node_modules/@scope/tool",
        "resolved": "https://registry.npmjs.org/@scope/tool/-/tool-2.1.0.tgz",
        "integrity": "sha512-demo-tool",
        "license": "MIT",
    }


def test_npm_package_lock_diagnostics_report_nested_conflicts() -> None:
    payload = NpmAdapter().diagnose_lockfile(
        Path("tests/fixtures/package-lock-conflict.json")
    )

    assert payload["schema"] == "edgp.npm.diagnostics.v1"
    assert payload["summary"] == {
        "packages": 4,
        "duplicatePackageNames": 1,
        "nestedResolutionConflicts": 1,
        "unresolvedDependencies": 1,
    }
    assert payload["duplicatePackageNames"] == [
        {
            "package": "shared",
            "versions": [
                {"paths": ["node_modules/shared"], "version": "1.0.0"},
                {
                    "paths": ["node_modules/tool/node_modules/shared"],
                    "version": "2.0.0",
                },
            ],
        }
    ]
    assert payload["nestedResolutionConflicts"][0]["dependency"] == "shared"
    assert payload["nestedResolutionConflicts"][0]["versions"] == ["1.0.0", "2.0.0"]
    assert payload["unresolvedDependencies"][0]["dependency"] == "missing"
