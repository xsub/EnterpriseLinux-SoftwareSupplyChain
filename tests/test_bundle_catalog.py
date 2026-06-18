"""Bundle catalog tests for batch report-bundle verification."""

import io
import json
import tarfile
from pathlib import Path

from src.bundle_catalog import build_bundle_catalog_report
from src.output.report_bundle import write_report_bundle, write_report_bundle_archive


def test_build_bundle_catalog_report_summarizes_verified_bundles(tmp_path) -> None:
    graph_bundle = tmp_path / "graph-bundle"
    diagnostics_bundle = tmp_path / "diagnostics-bundle"
    write_report_bundle(
        [Path("tests/fixtures/snapshot-right.json")],
        graph_bundle,
        bundle_metadata={
            "sourceKind": "edgp-json",
            "command": "edgp report-bundle --input snapshot",
        },
    )
    write_report_bundle(
        [Path("tests/fixtures/npm-diagnostics-report.json")],
        diagnostics_bundle,
        bundle_metadata={
            "sourceKind": "npm-diagnostics",
            "command": "edgp npm-diagnostics-bundle --path package-lock.json",
        },
        include_triage_summary=True,
    )

    report = build_bundle_catalog_report([graph_bundle, diagnostics_bundle])

    assert report["schema"] == "edgp.bundle.catalog.v1"
    assert report["status"] == "warn"
    assert report["summary"] == {
        "bundles": 2,
        "okBundles": 2,
        "failedBundles": 0,
        "reports": 2,
        "failures": 0,
        "graphDiffPolicyFailures": 0,
        "diffTreePolicyFailures": 0,
        "realDataCoveragePolicyFailures": 0,
        "realDataCoverageDiffPolicyFailures": 0,
        "realDataReplacementPlanPolicyFailures": 0,
        "realDataReplacementPlanDiffPolicyFailures": 0,
        "triagePass": 0,
        "triageWarn": 1,
        "triageFail": 0,
        "withoutTriage": 1,
    }
    assert report["sourceKinds"] == [
        {
            "sourceKind": "edgp-json",
            "bundles": 1,
            "reports": 1,
            "failures": 0,
            "graphDiffPolicyFailures": 0,
            "diffTreePolicyFailures": 0,
            "realDataCoveragePolicyFailures": 0,
            "realDataCoverageDiffPolicyFailures": 0,
            "realDataReplacementPlanPolicyFailures": 0,
            "realDataReplacementPlanDiffPolicyFailures": 0,
            "triagePass": 0,
            "triageWarn": 0,
            "triageFail": 0,
            "withoutTriage": 1,
        },
        {
            "sourceKind": "npm-diagnostics",
            "bundles": 1,
            "reports": 1,
            "failures": 0,
            "graphDiffPolicyFailures": 0,
            "diffTreePolicyFailures": 0,
            "realDataCoveragePolicyFailures": 0,
            "realDataCoverageDiffPolicyFailures": 0,
            "realDataReplacementPlanPolicyFailures": 0,
            "realDataReplacementPlanDiffPolicyFailures": 0,
            "triagePass": 0,
            "triageWarn": 1,
            "triageFail": 0,
            "withoutTriage": 0,
        },
    ]
    assert report["bundles"][0]["reportSchemas"] == ["edgp.graph.snapshot.v1"]
    assert report["bundles"][0]["inputType"] == "directory"
    assert report["bundles"][0]["graphDiffPolicyFailures"] == 0
    assert report["bundles"][0]["diffTreePolicyFailures"] == 0
    assert report["bundles"][0]["realDataCoveragePolicyFailures"] == 0
    assert report["bundles"][0]["realDataCoverageDiffPolicyFailures"] == 0
    assert report["bundles"][0]["realDataReplacementPlanPolicyFailures"] == 0
    assert report["bundles"][0]["realDataReplacementPlanDiffPolicyFailures"] == 0
    assert report["bundles"][0]["realDataCoverageFailureCodes"] == []
    assert report["bundles"][0]["realDataCoverageDiffFailureCodes"] == []
    assert report["bundles"][0]["realDataReplacementPlanFailureCodes"] == []
    assert report["bundles"][0]["realDataReplacementPlanDiffFailureCodes"] == []
    assert report["bundles"][1]["triageStatus"] == "warn"
    assert report["bundles"][1]["graphDiffPolicyFailures"] == 0
    assert report["bundles"][1]["diffTreePolicyFailures"] == 0
    assert report["bundles"][1]["realDataCoveragePolicyFailures"] == 0
    assert report["bundles"][1]["realDataCoverageDiffPolicyFailures"] == 0
    assert report["bundles"][1]["realDataReplacementPlanPolicyFailures"] == 0
    assert report["bundles"][1]["realDataReplacementPlanDiffPolicyFailures"] == 0
    assert report["bundles"][1]["realDataCoverageFailureCodes"] == []
    assert report["bundles"][1]["realDataCoverageDiffFailureCodes"] == []
    assert report["bundles"][1]["realDataReplacementPlanFailureCodes"] == []
    assert report["bundles"][1]["realDataReplacementPlanDiffFailureCodes"] == []
    assert report["bundles"][1]["bundleSha256"]


def test_build_bundle_catalog_report_marks_clean_catalog_pass(tmp_path) -> None:
    graph_bundle = tmp_path / "graph-bundle"
    write_report_bundle(
        [Path("tests/fixtures/snapshot-right.json")],
        graph_bundle,
        bundle_metadata={
            "sourceKind": "edgp-json",
            "command": "edgp report-bundle --input snapshot",
        },
    )

    report = build_bundle_catalog_report([graph_bundle])

    assert report["status"] == "pass"
    assert report["summary"]["okBundles"] == 1
    assert report["summary"]["withoutTriage"] == 1


def test_build_bundle_catalog_report_accepts_bundle_archives(tmp_path) -> None:
    graph_bundle = tmp_path / "graph-bundle"
    diagnostics_bundle = tmp_path / "diagnostics-bundle"
    diagnostics_archive = tmp_path / "diagnostics-bundle.tar.gz"
    write_report_bundle(
        [Path("tests/fixtures/snapshot-right.json")],
        graph_bundle,
        bundle_metadata={
            "sourceKind": "edgp-json",
            "command": "edgp report-bundle --input snapshot",
        },
    )
    write_report_bundle(
        [Path("tests/fixtures/npm-diagnostics-report.json")],
        diagnostics_bundle,
        bundle_metadata={
            "sourceKind": "npm-diagnostics",
            "command": "edgp npm-diagnostics-bundle --path package-lock.json",
        },
        include_triage_summary=True,
    )
    archive_report = write_report_bundle_archive(diagnostics_bundle, diagnostics_archive)

    report = build_bundle_catalog_report([graph_bundle, diagnostics_archive])

    assert report["status"] == "warn"
    assert report["summary"]["bundles"] == 2
    assert report["summary"]["okBundles"] == 2
    assert report["summary"]["reports"] == 2
    assert report["summary"]["triageWarn"] == 1
    assert report["summary"]["diffTreePolicyFailures"] == 0
    assert report["summary"]["realDataCoveragePolicyFailures"] == 0
    assert report["summary"]["realDataCoverageDiffPolicyFailures"] == 0
    assert report["summary"]["realDataReplacementPlanPolicyFailures"] == 0
    assert report["summary"]["realDataReplacementPlanDiffPolicyFailures"] == 0
    assert report["bundles"][0]["inputType"] == "directory"
    assert report["bundles"][1]["inputType"] == "archive"
    assert report["bundles"][1]["path"] == str(diagnostics_archive.resolve())
    assert report["bundles"][1]["sourceKind"] == "npm-diagnostics"
    assert report["bundles"][1]["reportSchemas"] == ["edgp.npm.diagnostics.v1"]
    assert report["bundles"][1]["triageStatus"] == "warn"
    assert report["bundles"][1]["diffTreePolicyFailures"] == 0
    assert report["bundles"][1]["bundleSha256"] == archive_report["bundleSha256"]


def test_build_bundle_catalog_report_captures_unsafe_archives(tmp_path) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    payload = b"unsafe"
    with tarfile.open(archive_path, "w:gz") as archive:
        info = tarfile.TarInfo("../evil.txt")
        info.size = len(payload)
        info.uid = 0
        info.gid = 0
        info.uname = ""
        info.gname = ""
        info.mtime = 0
        info.mode = 0o644
        archive.addfile(info, io.BytesIO(payload))

    report = build_bundle_catalog_report([archive_path])

    assert report["status"] == "fail"
    assert report["summary"]["failedBundles"] == 1
    assert report["summary"]["failures"] == 1
    assert report["summary"]["diffTreePolicyFailures"] == 0
    assert report["bundles"][0]["inputType"] == "archive"
    assert report["bundles"][0]["ok"] is False
    assert report["bundles"][0]["sourceKind"] == "unknown"
    assert report["bundles"][0]["failureCodes"] == ["archiveMemberPathInvalid"]
    assert report["bundles"][0]["bundleSha256"] is None


def test_build_bundle_catalog_report_captures_tampered_bundle(tmp_path) -> None:
    bundle_dir = tmp_path / "bundle"
    write_report_bundle([Path("tests/fixtures/snapshot-right.json")], bundle_dir)
    (bundle_dir / "001-snapshot-right.html").write_text(
        "<!doctype html><title>changed</title>",
        encoding="utf-8",
    )

    report = build_bundle_catalog_report([bundle_dir])

    assert report["status"] == "fail"
    assert report["summary"]["failedBundles"] == 1
    assert report["summary"]["failures"] == 1
    assert report["summary"]["diffTreePolicyFailures"] == 0
    assert report["bundles"][0]["ok"] is False
    assert report["bundles"][0]["failureCodes"] == ["htmlDigestMismatch"]
    assert report["bundles"][0]["bundleSha256"]


def test_build_bundle_catalog_groups_triage_failures_by_source_kind(tmp_path) -> None:
    diff_tree_report = json.loads(
        Path("tests/fixtures/graph-diff-tree.json").read_text(encoding="utf-8")
    )
    diff_tree_report["policy"] = {
        "exitCode": 2,
        "failOnKind": ["upgrade"],
        "matchedKinds": ["upgrade"],
        "status": "fail",
    }
    diff_tree_path = tmp_path / "graph-diff-tree.json"
    diff_tree_path.write_text(json.dumps(diff_tree_report), encoding="utf-8")
    diff_tree_bundle = tmp_path / "diff-tree-bundle"
    write_report_bundle(
        [diff_tree_path],
        diff_tree_bundle,
        bundle_metadata={
            "sourceKind": "graph-diff-tree",
            "command": "edgp diff-tree-bundle --fail-on-kind upgrade",
        },
        include_triage_summary=True,
    )

    report = build_bundle_catalog_report([diff_tree_bundle])

    assert report["status"] == "fail"
    assert report["summary"]["triageFail"] == 1
    assert report["summary"]["diffTreePolicyFailures"] == 1
    assert report["bundles"][0]["diffTreePolicyFailures"] == 1
    assert report["sourceKinds"] == [
        {
            "sourceKind": "graph-diff-tree",
            "bundles": 1,
            "reports": 1,
            "failures": 0,
            "graphDiffPolicyFailures": 0,
            "diffTreePolicyFailures": 1,
            "realDataCoveragePolicyFailures": 0,
            "realDataCoverageDiffPolicyFailures": 0,
            "realDataReplacementPlanPolicyFailures": 0,
            "realDataReplacementPlanDiffPolicyFailures": 0,
            "triagePass": 0,
            "triageWarn": 0,
            "triageFail": 1,
            "withoutTriage": 0,
        }
    ]


def test_build_bundle_catalog_groups_graph_diff_policy_failures_by_source_kind(
    tmp_path,
) -> None:
    diff_report = json.loads(
        Path("tests/fixtures/graph-diff.json").read_text(encoding="utf-8")
    )
    diff_report["policy"] = {
        "exitCode": 2,
        "failOnChange": ["added-node"],
        "matchedChanges": ["added-node"],
        "status": "fail",
    }
    diff_path = tmp_path / "graph-diff.json"
    diff_path.write_text(json.dumps(diff_report), encoding="utf-8")
    diff_bundle = tmp_path / "diff-bundle"
    write_report_bundle(
        [diff_path],
        diff_bundle,
        bundle_metadata={
            "sourceKind": "graph-diff",
            "command": "edgp diff-bundle --fail-on-change added-node",
        },
        include_triage_summary=True,
    )

    report = build_bundle_catalog_report([diff_bundle])

    assert report["status"] == "fail"
    assert report["summary"]["triageFail"] == 1
    assert report["summary"]["graphDiffPolicyFailures"] == 1
    assert report["summary"]["diffTreePolicyFailures"] == 0
    assert report["summary"]["realDataCoveragePolicyFailures"] == 0
    assert report["summary"]["realDataCoverageDiffPolicyFailures"] == 0
    assert report["summary"]["realDataReplacementPlanPolicyFailures"] == 0
    assert report["summary"]["realDataReplacementPlanDiffPolicyFailures"] == 0
    assert report["bundles"][0]["graphDiffPolicyFailures"] == 1
    assert report["bundles"][0]["graphDiffFailOnChanges"] == ["added-node"]
    assert report["bundles"][0]["graphDiffMatchedChanges"] == ["added-node"]
    assert report["bundles"][0]["graphDiffFailOnKinds"] == []
    assert report["bundles"][0]["graphDiffMatchedKinds"] == []
    assert report["sourceKinds"] == [
        {
            "sourceKind": "graph-diff",
            "bundles": 1,
            "reports": 1,
            "failures": 0,
            "graphDiffPolicyFailures": 1,
            "diffTreePolicyFailures": 0,
            "realDataCoveragePolicyFailures": 0,
            "realDataCoverageDiffPolicyFailures": 0,
            "realDataReplacementPlanPolicyFailures": 0,
            "realDataReplacementPlanDiffPolicyFailures": 0,
            "triagePass": 0,
            "triageWarn": 0,
            "triageFail": 1,
            "withoutTriage": 0,
        }
    ]


def test_build_bundle_catalog_preserves_graph_diff_package_kind_details(
    tmp_path,
) -> None:
    diff_report = json.loads(
        Path("tests/fixtures/graph-diff.json").read_text(encoding="utf-8")
    )
    diff_report["policy"] = {
        "exitCode": 2,
        "failOnKind": ["upgrade"],
        "matchedKinds": ["upgrade"],
        "status": "fail",
    }
    diff_path = tmp_path / "graph-diff.json"
    diff_path.write_text(json.dumps(diff_report), encoding="utf-8")
    diff_bundle = tmp_path / "diff-bundle"
    write_report_bundle(
        [diff_path],
        diff_bundle,
        bundle_metadata={
            "sourceKind": "graph-diff",
            "command": "edgp diff-bundle --fail-on-kind upgrade",
        },
        include_triage_summary=True,
    )

    report = build_bundle_catalog_report([diff_bundle])

    assert report["status"] == "fail"
    assert report["summary"]["graphDiffPolicyFailures"] == 1
    assert report["bundles"][0]["graphDiffFailOnChanges"] == []
    assert report["bundles"][0]["graphDiffMatchedChanges"] == []
    assert report["bundles"][0]["graphDiffFailOnKinds"] == ["upgrade"]
    assert report["bundles"][0]["graphDiffMatchedKinds"] == ["upgrade"]


def test_build_bundle_catalog_counts_archive_diff_tree_policy_failures(
    tmp_path,
) -> None:
    diff_tree_report = json.loads(
        Path("tests/fixtures/graph-diff-tree.json").read_text(encoding="utf-8")
    )
    diff_tree_report["policy"] = {
        "exitCode": 2,
        "failOnKind": ["upgrade"],
        "matchedKinds": ["upgrade"],
        "status": "fail",
    }
    diff_tree_path = tmp_path / "graph-diff-tree.json"
    diff_tree_path.write_text(json.dumps(diff_tree_report), encoding="utf-8")
    diff_tree_bundle = tmp_path / "diff-tree-bundle"
    diff_tree_archive = tmp_path / "diff-tree-bundle.tar.gz"
    write_report_bundle(
        [diff_tree_path],
        diff_tree_bundle,
        bundle_metadata={
            "sourceKind": "graph-diff-tree",
            "command": "edgp diff-tree-bundle --fail-on-kind upgrade",
        },
        include_triage_summary=True,
    )
    write_report_bundle_archive(diff_tree_bundle, diff_tree_archive)

    report = build_bundle_catalog_report([diff_tree_archive])

    assert report["status"] == "fail"
    assert report["summary"]["triageFail"] == 1
    assert report["summary"]["diffTreePolicyFailures"] == 1
    assert report["bundles"][0]["inputType"] == "archive"
    assert report["bundles"][0]["triageStatus"] == "fail"
    assert report["bundles"][0]["diffTreePolicyFailures"] == 1
    assert report["bundles"][0]["diffTreeFailOnKinds"] == ["upgrade"]
    assert report["bundles"][0]["diffTreeMatchedKinds"] == ["upgrade"]
    assert report["sourceKinds"][0]["diffTreePolicyFailures"] == 1


def test_build_bundle_catalog_groups_real_data_policy_failures_by_source_kind(
    tmp_path,
) -> None:
    coverage_report = json.loads(
        Path("tests/fixtures/real-data-coverage.json").read_text(encoding="utf-8")
    )
    coverage_report["status"] = "fail"
    coverage_report["policy"] = {
        "exitCode": 2,
        "failOnPriority": "high",
        "failures": [
            {
                "code": "replacementPriorityMatched",
                "message": "Replacement-plan groups matched the configured gate.",
            }
        ],
        "matchedReplacementGroups": 1,
        "minPublicEvidenceCoveragePercent": None,
        "status": "fail",
    }
    coverage_path = tmp_path / "real-data-coverage.json"
    coverage_path.write_text(json.dumps(coverage_report), encoding="utf-8")
    coverage_bundle = tmp_path / "real-data-coverage-bundle"
    write_report_bundle(
        [coverage_path],
        coverage_bundle,
        bundle_metadata={
            "sourceKind": "real-data-coverage",
            "command": "edgp real-data-coverage-bundle --fail-on-priority high",
        },
        include_triage_summary=True,
    )

    report = build_bundle_catalog_report([coverage_bundle])

    assert report["status"] == "fail"
    assert report["summary"]["triageFail"] == 1
    assert report["summary"]["realDataCoveragePolicyFailures"] == 1
    assert report["summary"]["realDataCoverageDiffPolicyFailures"] == 0
    assert report["summary"]["realDataReplacementPlanPolicyFailures"] == 0
    assert report["summary"]["realDataReplacementPlanDiffPolicyFailures"] == 0
    assert report["bundles"][0]["realDataCoveragePolicyFailures"] == 1
    assert report["bundles"][0]["realDataCoverageDiffPolicyFailures"] == 0
    assert report["bundles"][0]["realDataReplacementPlanPolicyFailures"] == 0
    assert report["bundles"][0]["realDataReplacementPlanDiffPolicyFailures"] == 0
    assert report["bundles"][0]["realDataCoverageFailureCodes"] == [
        "replacementPriorityMatched"
    ]
    assert report["bundles"][0]["realDataCoverageDiffFailureCodes"] == []
    assert report["bundles"][0]["realDataReplacementPlanFailureCodes"] == []
    assert report["bundles"][0]["realDataReplacementPlanDiffFailureCodes"] == []
    assert report["sourceKinds"][0]["sourceKind"] == "real-data-coverage"
    assert report["sourceKinds"][0]["realDataCoveragePolicyFailures"] == 1


def test_build_bundle_catalog_groups_real_data_diff_policy_failures_by_source_kind(
    tmp_path,
) -> None:
    diff_report = json.loads(
        Path("tests/fixtures/real-data-coverage-diff.json").read_text(
            encoding="utf-8"
        )
    )
    diff_report["status"] = "fail"
    diff_report["policy"] = {
        "exitCode": 2,
        "failOnRegression": True,
        "failures": [
            {
                "code": "publicEvidenceCoverageDecreased",
                "message": "Public evidence coverage decreased.",
            },
            {
                "code": "publicEvidenceFilesDecreased",
                "message": "Public evidence file count decreased.",
            }
        ],
        "status": "fail",
    }
    diff_path = tmp_path / "real-data-coverage-diff.json"
    diff_path.write_text(json.dumps(diff_report), encoding="utf-8")
    diff_bundle = tmp_path / "real-data-coverage-diff-bundle"
    write_report_bundle(
        [diff_path],
        diff_bundle,
        bundle_metadata={
            "sourceKind": "real-data-coverage-diff",
            "command": "edgp real-data-coverage-diff-bundle --fail-on-regression",
        },
        include_triage_summary=True,
    )

    report = build_bundle_catalog_report([diff_bundle])

    assert report["status"] == "fail"
    assert report["summary"]["triageFail"] == 1
    assert report["summary"]["realDataCoveragePolicyFailures"] == 0
    assert report["summary"]["realDataCoverageDiffPolicyFailures"] == 1
    assert report["summary"]["realDataReplacementPlanPolicyFailures"] == 0
    assert report["summary"]["realDataReplacementPlanDiffPolicyFailures"] == 0
    assert report["bundles"][0]["realDataCoveragePolicyFailures"] == 0
    assert report["bundles"][0]["realDataCoverageDiffPolicyFailures"] == 1
    assert report["bundles"][0]["realDataReplacementPlanPolicyFailures"] == 0
    assert report["bundles"][0]["realDataReplacementPlanDiffPolicyFailures"] == 0
    assert report["bundles"][0]["realDataCoverageFailureCodes"] == []
    assert report["bundles"][0]["realDataCoverageDiffFailureCodes"] == [
        "publicEvidenceCoverageDecreased",
        "publicEvidenceFilesDecreased",
    ]
    assert report["bundles"][0]["realDataReplacementPlanFailureCodes"] == []
    assert report["bundles"][0]["realDataReplacementPlanDiffFailureCodes"] == []
    assert report["sourceKinds"][0]["sourceKind"] == "real-data-coverage-diff"
    assert report["sourceKinds"][0]["realDataCoverageDiffPolicyFailures"] == 1


def test_build_bundle_catalog_groups_replacement_plan_policy_failures_by_source_kind(
    tmp_path,
) -> None:
    plan_report = json.loads(
        Path("tests/fixtures/real-data-replacement-plan.json").read_text(
            encoding="utf-8"
        )
    )
    plan_report["status"] = "fail"
    plan_report["policy"] = {
        "exitCode": 2,
        "failOnPriority": "high",
        "failures": [
            {
                "code": "replacementPlanPriorityMatched",
                "message": "Replacement-plan candidates matched the configured gate.",
            }
        ],
        "matchedReplacementGroups": 1,
        "status": "fail",
    }
    plan_path = tmp_path / "real-data-replacement-plan.json"
    plan_path.write_text(json.dumps(plan_report), encoding="utf-8")
    plan_bundle = tmp_path / "real-data-replacement-plan-bundle"
    write_report_bundle(
        [plan_path],
        plan_bundle,
        bundle_metadata={
            "sourceKind": "real-data-replacement-plan",
            "command": "edgp real-data-replacement-plan-bundle --fail-on-priority high",
        },
        include_triage_summary=True,
    )

    report = build_bundle_catalog_report([plan_bundle])

    assert report["status"] == "fail"
    assert report["summary"]["triageFail"] == 1
    assert report["summary"]["realDataCoveragePolicyFailures"] == 0
    assert report["summary"]["realDataCoverageDiffPolicyFailures"] == 0
    assert report["summary"]["realDataReplacementPlanPolicyFailures"] == 1
    assert report["summary"]["realDataReplacementPlanDiffPolicyFailures"] == 0
    assert report["bundles"][0]["realDataReplacementPlanPolicyFailures"] == 1
    assert report["bundles"][0]["realDataReplacementPlanDiffPolicyFailures"] == 0
    assert report["bundles"][0]["realDataReplacementPlanFailureCodes"] == [
        "replacementPlanPriorityMatched"
    ]
    assert report["bundles"][0]["realDataReplacementPlanDiffFailureCodes"] == []
    assert report["sourceKinds"][0]["sourceKind"] == "real-data-replacement-plan"
    assert report["sourceKinds"][0]["realDataReplacementPlanPolicyFailures"] == 1
    assert report["sourceKinds"][0]["realDataReplacementPlanDiffPolicyFailures"] == 0


def test_build_bundle_catalog_groups_replacement_plan_diff_policy_failures_by_source_kind(
    tmp_path,
) -> None:
    diff_report = json.loads(
        Path("tests/fixtures/real-data-replacement-plan-diff.json").read_text(
            encoding="utf-8"
        )
    )
    diff_report["status"] = "fail"
    diff_report["policy"] = {
        "exitCode": 2,
        "failOnRegression": True,
        "failures": [
            {
                "code": "replacementCandidatesIncreased",
                "message": "Replacement candidates increased.",
            },
            {
                "code": "candidateFilesIncreased",
                "message": "Candidate file count increased.",
            },
        ],
        "status": "fail",
    }
    diff_path = tmp_path / "real-data-replacement-plan-diff.json"
    diff_path.write_text(json.dumps(diff_report), encoding="utf-8")
    diff_bundle = tmp_path / "real-data-replacement-plan-diff-bundle"
    write_report_bundle(
        [diff_path],
        diff_bundle,
        bundle_metadata={
            "sourceKind": "real-data-replacement-plan-diff",
            "command": "edgp real-data-replacement-plan-diff-bundle --fail-on-regression",
        },
        include_triage_summary=True,
    )

    report = build_bundle_catalog_report([diff_bundle])

    assert report["status"] == "fail"
    assert report["summary"]["triageFail"] == 1
    assert report["summary"]["realDataCoveragePolicyFailures"] == 0
    assert report["summary"]["realDataCoverageDiffPolicyFailures"] == 0
    assert report["summary"]["realDataReplacementPlanPolicyFailures"] == 0
    assert report["summary"]["realDataReplacementPlanDiffPolicyFailures"] == 1
    assert report["bundles"][0]["realDataReplacementPlanPolicyFailures"] == 0
    assert report["bundles"][0]["realDataReplacementPlanDiffPolicyFailures"] == 1
    assert report["bundles"][0]["realDataReplacementPlanFailureCodes"] == []
    assert report["bundles"][0]["realDataReplacementPlanDiffFailureCodes"] == [
        "replacementCandidatesIncreased",
        "candidateFilesIncreased",
    ]
    assert report["sourceKinds"][0]["sourceKind"] == "real-data-replacement-plan-diff"
    assert report["sourceKinds"][0]["realDataReplacementPlanPolicyFailures"] == 0
    assert report["sourceKinds"][0]["realDataReplacementPlanDiffPolicyFailures"] == 1
