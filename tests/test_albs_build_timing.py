"""ALBS build timing report tests ported from investigation workbench ideas."""

import json
from pathlib import Path

from src.albs_build_timing import build_albs_build_timing_report


def test_build_albs_build_timing_report_summarizes_tasks_and_signing() -> None:
    payload = json.loads(Path("tests/fixtures/albs-build.json").read_text())

    report = build_albs_build_timing_report(payload, root="albs-build:17812")

    assert report["schema"] == "edgp.albs.build_timing.v1"
    assert report["summary"] == {
        "aggregateBuildTaskWallSeconds": 741.140096,
        "aggregateSignTaskWallSeconds": 255.704401,
        "artifacts": 5,
        "buildTasks": 2,
        "criticalBuildTaskWallSeconds": 371.070048,
        "signTasks": 1,
    }
    assert report["wallSeconds"] == 814.155744
    assert report["artifactTypes"] == {"build_log": 1, "rpm": 4}
    assert report["taskTimings"][0]["arch"] == "x86_64"
    assert report["taskTimings"][0]["artifactCounts"] == {"rpm": 2}
    assert report["taskTimings"][1]["artifactCounts"] == {"build_log": 1, "rpm": 2}
    assert report["signStepTotalsSeconds"] == {
        "sign_packages_time": 22.0,
        "upload_packages_time": 187.0,
    }


def test_build_albs_build_timing_report_collects_nested_steps() -> None:
    payload = {
        "id": 1,
        "tasks": [
            {
                "id": 10,
                "arch": "x86_64",
                "started_at": "2026-01-01T00:00:00",
                "finished_at": "2026-01-01T00:00:03",
                "performance_stats": [
                    {
                        "statistics": {
                            "outer": {
                                "inner": {
                                    "delta": "00:00:02.500000",
                                    "start_ts": "2026-01-01T00:00:00",
                                    "finish_ts": "2026-01-01T00:00:02.500000"
                                }
                            }
                        }
                    }
                ],
            }
        ],
    }

    report = build_albs_build_timing_report(payload)

    assert report["taskTimings"][0]["steps"] == [
        {
            "finishedAt": "2026-01-01T00:00:02.500000",
            "name": "outer.inner",
            "seconds": 2.5,
            "startedAt": "2026-01-01T00:00:00",
        }
    ]
    assert report["buildStepTotalsSeconds"] == {"outer.inner": 2.5}
