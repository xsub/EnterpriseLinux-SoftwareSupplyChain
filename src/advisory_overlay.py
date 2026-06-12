"""Local advisory overlay reports for public vulnerability-style analysis."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.core_graph.sparse_matrix import CSRDependencyGraph
from src.impact_report import build_impact_report


def build_advisory_report_from_file(
    advisory_path: Path,
    graph: CSRDependencyGraph,
    *,
    root: str | None = None,
    ecosystem: str = "generic",
    max_paths: int = 20,
) -> dict[str, object]:
    payload = json.loads(advisory_path.read_text(encoding="utf-8"))
    return build_advisory_report(
        payload,
        graph,
        root=root,
        ecosystem=ecosystem,
        max_paths=max_paths,
    )


def build_advisory_report(
    advisory_payload: object,
    graph: CSRDependencyGraph,
    *,
    root: str | None = None,
    ecosystem: str = "generic",
    max_paths: int = 20,
) -> dict[str, object]:
    advisories = _extract_advisories(advisory_payload)
    findings = []
    affected_dependents: set[str] = set()

    for advisory in sorted(advisories, key=_advisory_sort_key):
        for package_id in sorted(graph.vertex_map):
            metadata = graph.get_vertex_metadata(package_id)
            if not _matches_advisory(advisory, package_id, ecosystem, metadata):
                continue
            impact = build_impact_report(
                graph,
                node=package_id,
                root=root,
                ecosystem=ecosystem,
                max_paths=max_paths,
            )
            for affected in impact["affectedDependents"]:
                affected_dependents.add(str(affected["package"]))
            findings.append(
                {
                    "advisory": advisory,
                    "package": package_id,
                    "metadata": metadata,
                    "impact": impact,
                }
            )

    return {
        "schema": "edgp.advisory.report.v1",
        "ecosystem": ecosystem,
        "root": root,
        "summary": {
            "advisories": len(advisories),
            "findings": len(findings),
            "matchedPackages": len({finding["package"] for finding in findings}),
            "affectedDependents": len(affected_dependents),
        },
        "findings": findings,
    }


def _extract_advisories(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        advisories = payload
    elif isinstance(payload, dict):
        schema = payload.get("schema")
        if schema not in (None, "edgp.advisory.overlay.v1"):
            raise ValueError(f"Unsupported advisory overlay schema: {schema}")
        advisories = payload.get("advisories", [])
    else:
        raise ValueError("Advisory overlay must be an object or list")

    if not isinstance(advisories, list):
        raise ValueError("Advisory overlay must contain an advisories list")

    normalized = []
    for advisory in advisories:
        if not isinstance(advisory, dict):
            raise ValueError("Each advisory must be an object")
        if not _advisory_package(advisory):
            raise ValueError("Each advisory must define package, name, or packageId")
        normalized.append(advisory)
    return normalized


def _matches_advisory(
    advisory: dict[str, Any],
    package_id: str,
    ecosystem: str,
    metadata: dict[str, str],
) -> bool:
    advisory_ecosystem = advisory.get("ecosystem")
    if advisory_ecosystem and str(advisory_ecosystem) != ecosystem:
        return False

    if advisory.get("packageId") == package_id:
        return True

    package_name, _, package_version = package_id.partition("==")
    if str(_advisory_package(advisory)) != package_name:
        return False

    version_candidates = _version_candidates(package_version, ecosystem, metadata)
    versions = _advisory_versions(advisory)
    if versions and versions & version_candidates:
        return True

    ranges = _advisory_ranges(advisory)
    if ranges:
        return any(
            _range_matches(
                range_record,
                version_candidates,
                ecosystem=ecosystem,
            )
            for range_record in ranges
        )

    return not versions


def _version_candidates(
    package_version: str,
    ecosystem: str,
    metadata: dict[str, str],
) -> set[str]:
    candidates = {package_version}
    if ecosystem != "rpm":
        return candidates

    version = metadata.get("version", "")
    release = metadata.get("release", "")
    epoch = metadata.get("epoch", "")
    arch = metadata.get("arch", "")
    if version:
        candidates.add(version)
    if version and release:
        evr = f"{version}-{release}"
        candidates.add(evr)
        if epoch and epoch not in ("0", "(none)"):
            candidates.add(f"{epoch}:{evr}")
    if arch and package_version.endswith(f".{arch}"):
        candidates.add(package_version[: -(len(arch) + 1)])
    return {candidate for candidate in candidates if candidate}


def _advisory_package(advisory: dict[str, Any]) -> object | None:
    return advisory.get("package") or advisory.get("name") or advisory.get("packageId")


def _advisory_versions(advisory: dict[str, Any]) -> set[str]:
    versions = advisory.get("versions")
    if versions is None and advisory.get("version") is not None:
        versions = [advisory["version"]]
    if versions is None:
        return set()
    if isinstance(versions, str):
        return {versions}
    if isinstance(versions, list):
        return {str(version) for version in versions}
    raise ValueError("Advisory versions must be a string or list")


def _advisory_ranges(advisory: dict[str, Any]) -> list[dict[str, str]]:
    ranges = advisory.get("ranges")
    if ranges is None:
        return []
    if not isinstance(ranges, list):
        raise ValueError("Advisory ranges must be a list")
    normalized = []
    for range_record in ranges:
        if not isinstance(range_record, dict):
            raise ValueError("Each advisory range must be an object")
        normalized.append(
            {
                str(key): str(value)
                for key, value in range_record.items()
                if value is not None
            }
        )
    return normalized


def _range_matches(
    range_record: dict[str, str],
    version_candidates: set[str],
    *,
    ecosystem: str,
) -> bool:
    candidates = _range_version_candidates(version_candidates, range_record, ecosystem)
    return any(
        _version_satisfies_range(candidate, range_record, ecosystem=ecosystem)
        for candidate in candidates
    )


def _range_version_candidates(
    version_candidates: set[str],
    range_record: dict[str, str],
    ecosystem: str,
) -> set[str]:
    if ecosystem != "rpm":
        return version_candidates
    bounds = [
        range_record[key]
        for key in ("introduced", "fixed", "lastAffected", "limit")
        if range_record.get(key)
    ]
    if any("-" in bound or ":" in bound for bound in bounds):
        precise = {
            candidate
            for candidate in version_candidates
            if "-" in candidate or ":" in candidate
        }
        if precise:
            return precise
    return version_candidates


def _version_satisfies_range(
    version: str,
    range_record: dict[str, str],
    *,
    ecosystem: str,
) -> bool:
    introduced = range_record.get("introduced")
    if (
        introduced
        and introduced != "0"
        and _compare_versions(version, introduced, ecosystem) < 0
    ):
        return False

    fixed = range_record.get("fixed")
    if fixed and _compare_versions(version, fixed, ecosystem) >= 0:
        return False

    last_affected = range_record.get("lastAffected")
    if last_affected and _compare_versions(version, last_affected, ecosystem) > 0:
        return False

    limit = range_record.get("limit")
    if limit and _compare_versions(version, limit, ecosystem) >= 0:
        return False

    return any(
        range_record.get(key)
        for key in ("introduced", "fixed", "lastAffected", "limit")
    )


def _compare_versions(left: str, right: str, ecosystem: str) -> int:
    left_epoch, left_body = _split_epoch(left if ecosystem == "rpm" else "")
    right_epoch, right_body = _split_epoch(right if ecosystem == "rpm" else "")
    if ecosystem == "rpm" and left_epoch != right_epoch:
        return -1 if left_epoch < right_epoch else 1
    if ecosystem != "rpm":
        left_body = left
        right_body = right
    return _compare_version_body(left_body, right_body)


def _split_epoch(version: str) -> tuple[int, str]:
    epoch, separator, body = version.partition(":")
    if not separator:
        return 0, version
    try:
        return int(epoch), body
    except ValueError:
        return 0, version


_VERSION_TOKEN_RE = re.compile(r"\d+|[A-Za-z]+")


def _compare_version_body(left: str, right: str) -> int:
    if left == right:
        return 0
    left_tokens = _version_tokens(left)
    right_tokens = _version_tokens(right)
    for left_token, right_token in zip(left_tokens, right_tokens):
        if left_token == right_token:
            continue
        left_is_numeric = isinstance(left_token, int)
        right_is_numeric = isinstance(right_token, int)
        if left_is_numeric and right_is_numeric:
            return -1 if left_token < right_token else 1
        if left_is_numeric != right_is_numeric:
            return 1 if left_is_numeric else -1
        return -1 if str(left_token) < str(right_token) else 1
    if len(left_tokens) == len(right_tokens):
        return 0
    return -1 if len(left_tokens) < len(right_tokens) else 1


def _version_tokens(version: str) -> list[int | str]:
    tokens: list[int | str] = []
    for token in _VERSION_TOKEN_RE.findall(version):
        if token.isdigit():
            tokens.append(int(token))
        else:
            tokens.append(token.lower())
    return tokens


def _advisory_sort_key(advisory: dict[str, Any]) -> tuple[str, str]:
    return (str(advisory.get("id", "")), str(_advisory_package(advisory)))
