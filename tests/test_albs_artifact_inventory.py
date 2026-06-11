"""ALBS artifact inventory report tests for build output visibility."""

from pathlib import Path

from src.albs_artifact_inventory import build_albs_artifact_inventory
from src.adapters.albs import AlbsBuildAdapter


def test_build_albs_artifact_inventory_groups_outputs_by_arch() -> None:
    resolved = AlbsBuildAdapter().parse_file(
        path=Path("tests/fixtures/albs-build.json")
    )

    report = build_albs_artifact_inventory(
        resolved.graph,
        root=resolved.root_identifier,
    )

    assert report["schema"] == "edgp.albs.artifact_inventory.v1"
    assert report["summary"] == {
        "architectures": 2,
        "artifacts": 4,
        "binaryRpms": 3,
        "buildLogs": 0,
        "buildTasks": 2,
        "debugArtifacts": 0,
        "packages": 2,
        "sourceRpms": 1,
    }
    assert report["buildArchitectures"] == ["x86_64", "ppc64le"]
    assert report["byBuildArch"][0] == {
        "artifactArches": {"x86_64": 2},
        "buildArch": "x86_64",
        "packages": ["nginx", "nginx-core"],
        "totalArtifacts": 2,
    }
    assert report["items"][0]["filename"] == "nginx-1.20.1-16.el9_4.1.x86_64.rpm"
    assert report["items"][-1]["artifactKind"] == "srpm"


def test_build_albs_artifact_inventory_can_include_logs() -> None:
    resolved = AlbsBuildAdapter().parse_file(
        path=Path("tests/fixtures/albs-build.json"),
        include_logs=True,
    )

    report = build_albs_artifact_inventory(
        resolved.graph,
        root=resolved.root_identifier,
    )

    assert report["summary"]["buildLogs"] == 1
    assert any(item["artifactKind"] == "build-log" for item in report["items"])
