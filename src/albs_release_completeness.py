"""ALBS release completeness summaries for batches of public build metadata."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.albs_artifact_inventory import _arch_sort_key

ALBS_RELEASE_COMPLETENESS_SCHEMA = "edgp.albs.release_completeness.v1"


def build_albs_release_completeness_report(
    builds: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Summarize release, architecture, sign, test, and artifact coverage."""

    items = [_build_item(payload) for payload in builds]
    missing_arches = sum(len(item["missingBuildArchitectures"]) for item in items)
    failed_tasks = sum(item["failedBuildTasks"] for item in items)
    unsigned = sum(1 for item in items if item["signTasks"] == 0)
    untested = sum(1 for item in items if item["testTasks"] == 0)
    return {
        "schema": ALBS_RELEASE_COMPLETENESS_SCHEMA,
        "ecosystem": "albs",
        "summary": {
            "builds": len(items),
            "releasedBuilds": sum(1 for item in items if item["released"]),
            "buildsWithMissingArchitectures": sum(
                1 for item in items if item["missingBuildArchitectures"]
            ),
            "missingBuildArchitectures": missing_arches,
            "failedBuildTasks": failed_tasks,
            "buildsWithoutSignTasks": unsigned,
            "buildsWithoutTestTasks": untested,
        },
        "builds": items,
    }


def _build_item(payload: Mapping[str, Any]) -> dict[str, Any]:
    build_id = str(payload.get("id") or payload.get("build_id") or "unknown")
    tasks = _object_list(payload.get("tasks"))
    expected = sorted(_expected_arches(tasks), key=_arch_sort_key)
    observed = sorted(
        {str(task.get("arch") or "unknown") for task in tasks},
        key=_arch_sort_key,
    )
    artifacts = [
        artifact
        for task in tasks
        for artifact in _object_list(task.get("artifacts"))
        if artifact.get("type") == "rpm"
    ]
    return {
        "buildId": build_id,
        "released": bool(payload.get("released")),
        "releaseId": str(payload.get("release_id") or ""),
        "expectedBuildArchitectures": expected,
        "observedBuildArchitectures": observed,
        "missingBuildArchitectures": sorted(set(expected) - set(observed), key=_arch_sort_key),
        "failedBuildTasks": sum(1 for task in tasks if not _successful_task(task)),
        "buildTasks": len(tasks),
        "signTasks": len(_object_list(payload.get("sign_tasks"))),
        "testTasks": len(_object_list(payload.get("test_tasks"))),
        "rpmArtifacts": len(artifacts),
    }


def _expected_arches(tasks: list[dict[str, Any]]) -> set[str]:
    arches: set[str] = set()
    for task in tasks:
        platform = task.get("platform") if isinstance(task.get("platform"), dict) else {}
        arch_list = platform.get("arch_list")
        if isinstance(arch_list, list):
            arches.update(str(arch) for arch in arch_list if arch)
    return arches


def _successful_task(task: Mapping[str, Any]) -> bool:
    status = str(task.get("status") or "").lower()
    return status in {"2", "3", "done", "finished", "success", "completed"}


def _object_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
