"""License inventory and deny-list reporting for public graph metadata."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from typing import Any

from src.core_graph.sparse_matrix import CSRDependencyGraph

LICENSE_REPORT_SCHEMA = "edgp.license.report.v1"


def build_license_report(
    graph: CSRDependencyGraph,
    *,
    root: str | None = None,
    ecosystem: str = "generic",
    denied_licenses: Sequence[str] = (),
) -> dict[str, Any]:
    """Summarize component licenses and flag packages matching a deny-list."""

    denied = _normalize_denied_licenses(denied_licenses)
    license_counts: Counter[str] = Counter()
    findings: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    package_count = 0

    for package_id in sorted(graph.vertex_map):
        metadata = graph.get_vertex_metadata(package_id)
        if _skip_node(package_id, metadata):
            continue
        package_count += 1
        license_text = _license_text(metadata)
        if not license_text:
            missing.append({"package": package_id, "metadata": metadata})
            continue
        license_counts[license_text] += 1
        matched = _matching_denied_licenses(license_text, denied)
        if matched:
            findings.append(
                {
                    "package": package_id,
                    "license": license_text,
                    "matchedDeniedLicenses": matched,
                    "metadata": metadata,
                }
            )

    licenses = [
        {"license": license_text, "packages": count}
        for license_text, count in sorted(
            license_counts.items(),
            key=lambda item: (-item[1], item[0].lower()),
        )
    ]
    return {
        "schema": LICENSE_REPORT_SCHEMA,
        "ecosystem": ecosystem,
        "root": root,
        "policy": {"deniedLicenses": [item["display"] for item in denied]},
        "summary": {
            "packages": package_count,
            "licensedPackages": sum(license_counts.values()),
            "missingLicenses": len(missing),
            "distinctLicenses": len(license_counts),
            "deniedFindings": len(findings),
        },
        "licenses": licenses,
        "findings": findings,
        "missingLicenses": missing,
    }


def _skip_node(package_id: str, metadata: dict[str, str]) -> bool:
    node_type = metadata.get("node_type", "")
    return node_type in {"root", "unresolved_requirement"} or package_id.startswith(
        "rpm-capability:"
    )


def _license_text(metadata: dict[str, str]) -> str:
    for key in ("license", "license_expression", "licenseExpression"):
        value = metadata.get(key)
        if value:
            return str(value).strip()
    return ""


def _normalize_denied_licenses(
    denied_licenses: Sequence[str],
) -> list[dict[str, str]]:
    normalized: dict[str, str] = {}
    for license_text in denied_licenses:
        display = str(license_text).strip()
        if not display:
            continue
        normalized[_normalize_license(display)] = display
    return [
        {"normalized": key, "display": value}
        for key, value in sorted(normalized.items(), key=lambda item: item[1].lower())
    ]


def _matching_denied_licenses(
    license_text: str,
    denied: Sequence[dict[str, str]],
) -> list[str]:
    normalized_license = _normalize_license(license_text)
    tokens = _license_tokens(license_text)
    matches = [
        item["display"]
        for item in denied
        if item["normalized"] == normalized_license or item["normalized"] in tokens
    ]
    return sorted(matches, key=str.lower)


def _normalize_license(license_text: str) -> str:
    return license_text.strip().casefold()


_LICENSE_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+-]*")
_LICENSE_OPERATORS = {"and", "or", "with"}


def _license_tokens(license_text: str) -> set[str]:
    return {
        token.casefold()
        for token in _LICENSE_TOKEN_RE.findall(license_text)
        if token.casefold() not in _LICENSE_OPERATORS
    }
