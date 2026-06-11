"""Public advisory feed normalization into EDGP advisory overlay records."""

from __future__ import annotations

from typing import Any, Mapping

PUBLIC_ADVISORY_FEED_SCHEMA = "edgp.public.advisory_feed.v1"


def build_public_advisory_feed_report(
    payload: object,
    *,
    ecosystem: str = "rpm",
) -> dict[str, Any]:
    """Normalize OSV-like public advisory payloads for EDGP overlays."""

    advisories = _normalize_advisories(payload, ecosystem=ecosystem)
    severities = sorted({advisory.get("severity", "") for advisory in advisories if advisory.get("severity")})
    packages = sorted({advisory.get("package", "") for advisory in advisories if advisory.get("package")})
    return {
        "schema": PUBLIC_ADVISORY_FEED_SCHEMA,
        "ecosystem": ecosystem,
        "summary": {
            "advisories": len(advisories),
            "packages": len(packages),
            "severities": len(severities),
        },
        "packages": packages,
        "severities": severities,
        "advisories": advisories,
        "overlay": {
            "schema": "edgp.advisory.overlay.v1",
            "advisories": advisories,
        },
    }


def _normalize_advisories(payload: object, *, ecosystem: str) -> list[dict[str, Any]]:
    records = _records(payload)
    advisories: list[dict[str, Any]] = []
    for record in records:
        advisory_id = _advisory_id(record)
        summary = str(record.get("summary") or record.get("details") or "")
        severity = _severity(record)
        references = _references(record)
        for package in _affected_packages(record, ecosystem=ecosystem):
            advisories.append(
                {
                    "id": advisory_id,
                    "ecosystem": ecosystem,
                    "package": package["name"],
                    "versions": package["versions"],
                    "severity": severity,
                    "summary": summary,
                    "references": references,
                }
            )
    return sorted(
        advisories,
        key=lambda advisory: (
            str(advisory.get("id", "")),
            str(advisory.get("package", "")),
        ),
    )


def _records(payload: object) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("vulns", "advisories", "items", "CVE_Items"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [payload]


def _advisory_id(record: Mapping[str, Any]) -> str:
    if record.get("id"):
        return str(record["id"])
    cve = record.get("cve")
    if isinstance(cve, dict):
        meta = cve.get("CVE_data_meta")
        if isinstance(meta, dict) and meta.get("ID"):
            return str(meta["ID"])
    return "UNKNOWN"


def _severity(record: Mapping[str, Any]) -> str:
    database_specific = record.get("database_specific")
    if isinstance(database_specific, dict) and database_specific.get("severity"):
        return str(database_specific["severity"])
    severity = record.get("severity")
    if isinstance(severity, list) and severity:
        first = severity[0]
        if isinstance(first, dict):
            return str(first.get("score") or first.get("type") or "")
    if severity:
        return str(severity)
    return ""


def _references(record: Mapping[str, Any]) -> list[str]:
    references = record.get("references")
    if not isinstance(references, list):
        return []
    urls: list[str] = []
    for reference in references:
        if isinstance(reference, dict) and reference.get("url"):
            urls.append(str(reference["url"]))
        elif isinstance(reference, str):
            urls.append(reference)
    return urls


def _affected_packages(record: Mapping[str, Any], *, ecosystem: str) -> list[dict[str, Any]]:
    affected = record.get("affected")
    if isinstance(affected, list):
        packages = []
        for item in affected:
            if not isinstance(item, dict):
                continue
            package = item.get("package") if isinstance(item.get("package"), dict) else {}
            package_ecosystem = str(package.get("ecosystem") or ecosystem)
            if package_ecosystem.lower() != ecosystem.lower():
                continue
            packages.append(
                {
                    "name": str(package.get("name") or item.get("name") or ""),
                    "versions": [str(version) for version in item.get("versions", []) if isinstance(version, str)],
                }
            )
        return [package for package in packages if package["name"]]
    package = record.get("package") or record.get("name")
    if package:
        versions = record.get("versions")
        return [
            {
                "name": str(package),
                "versions": [str(version) for version in versions] if isinstance(versions, list) else [],
            }
        ]
    return []
