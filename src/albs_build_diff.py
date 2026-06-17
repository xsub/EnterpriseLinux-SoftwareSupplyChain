"""ALBS build comparison report for public build metadata."""

from __future__ import annotations

from typing import Any, Mapping

from src.albs_artifact_inventory import _arch_sort_key, _parse_rpm_filename
from src.albs_build_timing import build_albs_build_timing_report

ALBS_BUILD_DIFF_SCHEMA = "edgp.albs.build_diff.v1"


def build_albs_build_diff_report(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare two public ALBS build payloads as release/provenance artifacts."""

    left_summary = _build_summary(left)
    right_summary = _build_summary(right)
    left_artifacts = _artifact_index(left)
    right_artifacts = _artifact_index(right)
    left_keys = set(left_artifacts)
    right_keys = set(right_artifacts)

    added = [right_artifacts[key] for key in sorted(right_keys - left_keys)]
    removed = [left_artifacts[key] for key in sorted(left_keys - right_keys)]
    changed = [
        _artifact_change(left_artifacts[key], right_artifacts[key])
        for key in sorted(left_keys & right_keys)
        if _artifact_changed(left_artifacts[key], right_artifacts[key])
    ]
    timing = _timing_delta(left, right)
    missing_arches = {
        "left": sorted(set(right_summary["buildArchitectures"]) - set(left_summary["buildArchitectures"]), key=_arch_sort_key),
        "right": sorted(set(left_summary["buildArchitectures"]) - set(right_summary["buildArchitectures"]), key=_arch_sort_key),
    }

    return {
        "schema": ALBS_BUILD_DIFF_SCHEMA,
        "ecosystem": "albs",
        "left": left_summary,
        "right": right_summary,
        "summary": {
            "addedArtifacts": len(added),
            "removedArtifacts": len(removed),
            "changedArtifacts": len(changed),
            "leftMissingBuildArchitectures": len(missing_arches["left"]),
            "rightMissingBuildArchitectures": len(missing_arches["right"]),
            "gitCommitChanged": left_summary["gitCommits"] != right_summary["gitCommits"],
            "criticalBuildTaskWallSecondsDelta": timing["criticalBuildTaskWallSecondsDelta"],
        },
        "missingBuildArchitectures": missing_arches,
        "addedArtifacts": added,
        "removedArtifacts": removed,
        "changedArtifacts": changed,
        "topFindings": _top_findings(
            added=added,
            removed=removed,
            changed=changed,
            missing_arches=missing_arches,
            timing=timing,
            left_summary=left_summary,
            right_summary=right_summary,
        ),
        "timingDelta": timing,
    }


def _build_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    build_id = str(payload.get("id") or payload.get("build_id") or "unknown")
    tasks = _object_list(payload.get("tasks"))
    build_arches = sorted(
        {str(task.get("arch") or "unknown") for task in tasks},
        key=_arch_sort_key,
    )
    commits = sorted(
        {
            str(commit)
            for task in tasks
            for commit in (
                _task_commit(task),
            )
            if commit
        }
    )
    return {
        "buildId": build_id,
        "released": bool(payload.get("released")),
        "releaseId": str(payload.get("release_id") or ""),
        "package": _package_name(payload),
        "buildArchitectures": build_arches,
        "gitCommits": commits,
        "artifacts": len(_artifact_index(payload)),
    }


def _artifact_index(payload: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    artifacts: dict[str, dict[str, str]] = {}
    for task in _object_list(payload.get("tasks")):
        build_arch = str(task.get("arch") or "unknown")
        task_id = str(task.get("id") or "")
        for artifact in _object_list(task.get("artifacts")):
            if artifact.get("type") != "rpm":
                continue
            filename = str(artifact.get("name") or "")
            rpm = _parse_rpm_filename(filename)
            kind = "srpm" if filename.endswith(".src.rpm") else "rpm"
            key = "|".join([kind, rpm.name, rpm.arch, build_arch])
            artifacts[key] = {
                "key": key,
                "artifactId": str(artifact.get("id") or ""),
                "filename": filename,
                "artifactKind": kind,
                "packageName": rpm.name,
                "version": rpm.version,
                "release": rpm.release,
                "artifactArch": rpm.arch,
                "buildArch": build_arch,
                "buildTaskId": task_id,
                "casHash": str(artifact.get("cas_hash") or ""),
                "href": str(artifact.get("href") or ""),
            }
    return artifacts


def _artifact_changed(left: Mapping[str, str], right: Mapping[str, str]) -> bool:
    return any(
        left.get(field, "") != right.get(field, "")
        for field in ("filename", "version", "release", "casHash", "href")
    )


def _artifact_change(left: dict[str, str], right: dict[str, str]) -> dict[str, Any]:
    changed_fields = [
        field
        for field in ("filename", "version", "release", "casHash", "href")
        if left.get(field, "") != right.get(field, "")
    ]
    return {
        "key": left["key"],
        "packageName": left["packageName"] or right["packageName"],
        "artifactArch": left["artifactArch"] or right["artifactArch"],
        "buildArch": left["buildArch"] or right["buildArch"],
        "changedFields": changed_fields,
        "left": left,
        "right": right,
    }


def _top_findings(
    *,
    added: list[dict[str, str]],
    removed: list[dict[str, str]],
    changed: list[dict[str, Any]],
    missing_arches: dict[str, list[str]],
    timing: dict[str, Any],
    left_summary: dict[str, Any],
    right_summary: dict[str, Any],
    limit: int = 10,
) -> dict[str, list[dict[str, Any]]]:
    return {
        "changedArtifacts": sorted(
            changed,
            key=lambda item: (
                -len(item.get("changedFields", [])),
                str(item.get("packageName", "")),
                str(item.get("artifactArch", "")),
                str(item.get("buildArch", "")),
            ),
        )[:limit],
        "addedArtifacts": _rank_artifacts(added)[:limit],
        "removedArtifacts": _rank_artifacts(removed)[:limit],
        "missingBuildArchitectures": _missing_arch_findings(missing_arches)[:limit],
        "timingDeltas": _timing_findings(timing),
        "gitCommitChanges": _git_commit_findings(left_summary, right_summary),
    }


def _rank_artifacts(artifacts: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        artifacts,
        key=lambda item: (
            str(item.get("packageName", "")),
            str(item.get("artifactArch", "")),
            str(item.get("buildArch", "")),
            str(item.get("filename", "")),
        ),
    )


def _missing_arch_findings(missing_arches: dict[str, list[str]]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for side in ("left", "right"):
        for arch in missing_arches.get(side, []):
            findings.append({"side": side, "arch": arch})
    return findings


def _timing_findings(timing: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for metric, left_key, right_key, delta_key in (
        (
            "wallSeconds",
            "leftWallSeconds",
            "rightWallSeconds",
            "wallSecondsDelta",
        ),
        (
            "criticalBuildTaskWallSeconds",
            "leftCriticalBuildTaskWallSeconds",
            "rightCriticalBuildTaskWallSeconds",
            "criticalBuildTaskWallSecondsDelta",
        ),
    ):
        delta = timing.get(delta_key)
        if not isinstance(delta, int | float) or delta == 0:
            continue
        rows.append(
            {
                "metric": metric,
                "left": timing.get(left_key),
                "right": timing.get(right_key),
                "delta": delta,
            }
        )
    return rows


def _git_commit_findings(
    left_summary: dict[str, Any],
    right_summary: dict[str, Any],
) -> list[dict[str, Any]]:
    left_commits = left_summary.get("gitCommits", [])
    right_commits = right_summary.get("gitCommits", [])
    if left_commits == right_commits:
        return []
    return [{"left": left_commits, "right": right_commits}]


def _timing_delta(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, Any]:
    left_timing = build_albs_build_timing_report(dict(left))
    right_timing = build_albs_build_timing_report(dict(right))
    left_summary = left_timing["summary"]
    right_summary = right_timing["summary"]
    return {
        "leftWallSeconds": left_timing["wallSeconds"],
        "rightWallSeconds": right_timing["wallSeconds"],
        "wallSecondsDelta": _delta(left_timing["wallSeconds"], right_timing["wallSeconds"]),
        "leftCriticalBuildTaskWallSeconds": left_summary["criticalBuildTaskWallSeconds"],
        "rightCriticalBuildTaskWallSeconds": right_summary["criticalBuildTaskWallSeconds"],
        "criticalBuildTaskWallSecondsDelta": _delta(
            left_summary["criticalBuildTaskWallSeconds"],
            right_summary["criticalBuildTaskWallSeconds"],
        ),
    }


def _delta(left: object, right: object) -> float | None:
    if not isinstance(left, int | float) or not isinstance(right, int | float):
        return None
    return round(float(right) - float(left), 6)


def _task_commit(task: Mapping[str, Any]) -> str:
    ref = task.get("ref") if isinstance(task.get("ref"), dict) else {}
    return str(ref.get("git_commit_hash") or task.get("alma_commit_cas_hash") or "")


def _package_name(payload: Mapping[str, Any]) -> str:
    explicit = payload.get("package") or payload.get("source_package")
    if explicit:
        return str(explicit)
    for task in _object_list(payload.get("tasks")):
        ref = task.get("ref") if isinstance(task.get("ref"), dict) else {}
        url = str(ref.get("url") or "")
        stem = url.rstrip("/").rsplit("/", 1)[-1]
        if stem:
            return stem[:-4] if stem.endswith(".git") else stem
    return "unknown"


def _object_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
