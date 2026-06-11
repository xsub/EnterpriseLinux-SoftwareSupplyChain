"""ALBS build timing report builder for public build metadata."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

ALBS_BUILD_TIMING_SCHEMA = "edgp.albs.build_timing.v1"
_ARCH_PREFERENCE = ("x86_64", "aarch64", "ppc64le", "s390x", "i686", "src", "noarch")


def build_albs_build_timing_report(
    payload: dict[str, Any],
    *,
    root: str | None = None,
) -> dict[str, Any]:
    """Build deterministic task, sign, and artifact timing summaries."""

    build_id = str(payload.get("build_id") or payload.get("id") or "unknown")
    task_timings = sorted(
        [_task_timing(task) for task in _object_list(payload.get("tasks"))],
        key=lambda task: _arch_sort_key(task["arch"]),
    )
    sign_timings = [
        _sign_task_timing(sign_task) for sign_task in _object_list(payload.get("sign_tasks"))
    ]
    task_by_id = {task["taskId"]: task for task in task_timings}
    artifact_timings = sorted(
        [
            _artifact_timing(task, artifact, task_by_id[str(task.get("id"))])
            for task in _object_list(payload.get("tasks"))
            for artifact in _object_list(task.get("artifacts"))
            if str(task.get("id")) in task_by_id
        ],
        key=lambda artifact: (
            _arch_sort_key(artifact["buildArch"]),
            artifact["artifactType"],
            artifact["name"],
        ),
    )
    totals = _totals(task_timings, sign_timings, artifact_timings)
    created_at = _text(payload.get("created_at"))
    finished_at = _text(payload.get("finished_at"))
    return {
        "schema": ALBS_BUILD_TIMING_SCHEMA,
        "ecosystem": "albs",
        "root": root or f"albs-build:{build_id}",
        "buildId": build_id,
        "createdAt": created_at or "",
        "finishedAt": finished_at or "",
        "wallSeconds": _duration_between(created_at, finished_at),
        "summary": {
            "buildTasks": totals["buildTaskCount"],
            "signTasks": totals["signTaskCount"],
            "artifacts": totals["artifactCount"],
            "aggregateBuildTaskWallSeconds": totals["aggregateBuildTaskWallSeconds"],
            "criticalBuildTaskWallSeconds": totals["criticalBuildTaskWallSeconds"],
            "aggregateSignTaskWallSeconds": totals["aggregateSignTaskWallSeconds"],
        },
        "artifactTypes": totals["artifactTypes"],
        "artifactArches": totals["artifactArches"],
        "buildStepTotalsSeconds": totals["buildStepTotalsSeconds"],
        "signStepTotalsSeconds": totals["signStepTotalsSeconds"],
        "taskTimings": task_timings,
        "signTimings": sign_timings,
        "artifactTimings": artifact_timings,
    }


def _task_timing(task: dict[str, Any]) -> dict[str, Any]:
    statistics = [
        stat.get("statistics", {})
        for stat in _object_list(task.get("performance_stats"))
        if isinstance(stat.get("statistics"), dict)
    ]
    steps = sorted(
        [step for stat in statistics for step in _iter_timing_steps(stat)],
        key=lambda step: step["name"],
    )
    test_totals = _test_step_totals(_object_list(task.get("test_tasks")))
    started_at = _text(task.get("started_at"))
    finished_at = _text(task.get("finished_at"))
    return {
        "taskId": str(task.get("id")),
        "arch": str(task.get("arch") or "unknown"),
        "status": str(task.get("status") or ""),
        "startedAt": started_at or "",
        "finishedAt": finished_at or "",
        "wallSeconds": _duration_between(started_at, finished_at),
        "artifactCounts": dict(
            sorted(
                Counter(
                    str(item.get("type") or "unknown")
                    for item in _object_list(task.get("artifacts"))
                ).items()
            )
        ),
        "steps": steps,
        "testTasks": len(_object_list(task.get("test_tasks"))),
        "testStepTotalsSeconds": test_totals,
    }


def _sign_task_timing(sign_task: dict[str, Any]) -> dict[str, Any]:
    stats = sign_task.get("stats") if isinstance(sign_task.get("stats"), dict) else {}
    started_at = _text(sign_task.get("started_at"))
    finished_at = _text(sign_task.get("finished_at"))
    return {
        "signTaskId": str(sign_task.get("id")),
        "status": str(sign_task.get("status") or ""),
        "startedAt": started_at or "",
        "finishedAt": finished_at or "",
        "wallSeconds": _duration_between(started_at, finished_at),
        "statsSeconds": {
            str(key): float(value)
            for key, value in sorted(stats.items())
            if isinstance(value, int | float) and not isinstance(value, bool)
        },
    }


def _artifact_timing(
    task: dict[str, Any],
    artifact: dict[str, Any],
    task_timing: dict[str, Any],
) -> dict[str, Any]:
    name = str(artifact.get("name") or "")
    rpm_metadata = _rpm_metadata_from_filename(name) if name.endswith(".rpm") else {}
    return {
        "artifactId": str(artifact.get("id") or ""),
        "name": name,
        "artifactType": str(artifact.get("type") or "unknown"),
        "buildTaskId": str(task.get("id")),
        "buildArch": str(task.get("arch") or "unknown"),
        "artifactArch": _text(rpm_metadata.get("arch")) or "non-rpm",
        "packageName": _text(rpm_metadata.get("name")) or "",
        "taskWallSeconds": task_timing["wallSeconds"],
        "taskStepSeconds": {
            step["name"]: step["seconds"] for step in task_timing.get("steps", [])
        },
    }


def _iter_timing_steps(data: dict[str, Any], prefix: str = "") -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        step_name = f"{prefix}.{key}" if prefix else str(key)
        if "delta" in value:
            seconds = _delta_seconds(value.get("delta"))
            if seconds is not None:
                steps.append(
                    {
                        "name": step_name,
                        "seconds": seconds,
                        "startedAt": _text(value.get("start_ts")) or "",
                        "finishedAt": _text(value.get("finish_ts") or value.get("end_ts"))
                        or "",
                    }
                )
                continue
        steps.extend(_iter_timing_steps(value, step_name))
    return steps


def _test_step_totals(test_tasks: list[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for test_task in test_tasks:
        for perf in _object_list(test_task.get("performance_stats")):
            statistics = perf.get("statistics") if isinstance(perf.get("statistics"), dict) else {}
            for step in _iter_timing_steps(statistics):
                totals[step["name"]] += step["seconds"]
    return {key: round(value, 6) for key, value in sorted(totals.items())}


def _totals(
    task_timings: list[dict[str, Any]],
    sign_timings: list[dict[str, Any]],
    artifact_timings: list[dict[str, Any]],
) -> dict[str, Any]:
    build_step_totals: dict[str, float] = defaultdict(float)
    for task in task_timings:
        for step in task["steps"]:
            build_step_totals[step["name"]] += step["seconds"]

    sign_step_totals: dict[str, float] = defaultdict(float)
    for sign in sign_timings:
        for name, seconds in sign["statsSeconds"].items():
            sign_step_totals[name] += seconds

    artifact_types = Counter(artifact["artifactType"] for artifact in artifact_timings)
    artifact_arches = Counter(artifact["artifactArch"] for artifact in artifact_timings)
    return {
        "buildTaskCount": len(task_timings),
        "signTaskCount": len(sign_timings),
        "artifactCount": len(artifact_timings),
        "artifactTypes": dict(sorted(artifact_types.items())),
        "artifactArches": {
            arch: artifact_arches[arch]
            for arch in sorted(artifact_arches, key=_arch_sort_key)
        },
        "aggregateBuildTaskWallSeconds": round(
            sum(task["wallSeconds"] or 0 for task in task_timings),
            6,
        ),
        "criticalBuildTaskWallSeconds": round(
            max((task["wallSeconds"] or 0 for task in task_timings), default=0),
            6,
        ),
        "aggregateSignTaskWallSeconds": round(
            sum(sign["wallSeconds"] or 0 for sign in sign_timings),
            6,
        ),
        "buildStepTotalsSeconds": {
            key: round(value, 6) for key, value in sorted(build_step_totals.items())
        },
        "signStepTotalsSeconds": {
            key: round(value, 6) for key, value in sorted(sign_step_totals.items())
        },
    }


def _duration_between(start: Any, finish: Any) -> float | None:
    start_dt = _parse_datetime(start)
    finish_dt = _parse_datetime(finish)
    if not start_dt or not finish_dt:
        return None
    return round((finish_dt - start_dt).total_seconds(), 6)


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace(" ", "T"))
        except ValueError:
            return None


def _delta_seconds(value: Any) -> float | None:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    text = _text(value)
    if not text:
        return None
    parts = text.split(":")
    if len(parts) != 3:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
    except ValueError:
        return None
    return round(hours * 3600 + minutes * 60 + seconds, 6)


def _rpm_metadata_from_filename(filename: str) -> dict[str, str | None]:
    stem = filename.removesuffix(".rpm")
    parts = stem.rsplit(".", 1)
    arch = parts[1] if len(parts) == 2 else None
    nevr = parts[0] if len(parts) == 2 else stem
    metadata: dict[str, str | None] = {"filename": filename, "arch": arch}
    name_version_release = nevr.rsplit("-", 2)
    if len(name_version_release) == 3:
        metadata |= {
            "name": name_version_release[0],
            "version": name_version_release[1],
            "release": name_version_release[2],
        }
    return metadata


def _arch_sort_key(value: str) -> tuple[int, str]:
    try:
        return (_ARCH_PREFERENCE.index(value), value)
    except ValueError:
        return (len(_ARCH_PREFERENCE), value)


def _object_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
