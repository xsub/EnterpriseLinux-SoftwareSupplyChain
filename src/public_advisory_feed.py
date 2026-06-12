"""Public advisory feed normalization into EDGP advisory overlay records."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import unquote

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
            advisory = {
                "id": advisory_id,
                "ecosystem": ecosystem,
                "package": package["name"],
                "versions": package["versions"],
                "severity": severity,
                "summary": summary,
                "references": references,
            }
            if package["purl"]:
                advisory["purl"] = package["purl"]
            if package["ranges"]:
                advisory["ranges"] = package["ranges"]
            advisories.append(advisory)
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
            purl = str(package.get("purl") or "")
            name = str(
                package.get("name")
                or item.get("name")
                or _package_name_from_purl(purl)
                or ""
            )
            packages.append(
                {
                    "name": name,
                    "purl": purl,
                    "versions": [
                        str(version)
                        for version in item.get("versions", [])
                        if isinstance(version, str)
                    ],
                    "ranges": _osv_ranges(item.get("ranges")),
                }
            )
        return [package for package in packages if package["name"]]
    purl = str(record.get("purl") or record.get("packageUrl") or "")
    package = record.get("package") or record.get("name") or _package_name_from_purl(purl)
    if package:
        versions = record.get("versions")
        return [
            {
                "name": str(package),
                "purl": purl,
                "versions": (
                    [str(version) for version in versions]
                    if isinstance(versions, list)
                    else []
                ),
                "ranges": _osv_ranges(record.get("ranges")),
            }
        ]
    return []


def _package_name_from_purl(purl: str) -> str:
    if not purl.startswith("pkg:"):
        return ""
    path = purl.removeprefix("pkg:").split("?", 1)[0].rsplit("@", 1)[0]
    _, separator, package_path = path.partition("/")
    if not separator:
        return ""
    segments = [unquote(segment) for segment in package_path.split("/") if segment]
    if not segments:
        return ""
    if len(segments) >= 2 and segments[0].startswith("@"):
        return "/".join(segments[-2:])
    return segments[-1]


def _osv_ranges(ranges: object) -> list[dict[str, str]]:
    if not isinstance(ranges, list):
        return []
    intervals: list[dict[str, str]] = []
    for range_record in ranges:
        if not isinstance(range_record, dict):
            continue
        range_type = str(range_record.get("type") or "")
        intervals.extend(_osv_range_intervals(range_record.get("events"), range_type))
    return intervals


def _osv_range_intervals(events: object, range_type: str) -> list[dict[str, str]]:
    if not isinstance(events, list):
        return []
    intervals: list[dict[str, str]] = []
    current: dict[str, str] = {"type": range_type} if range_type else {}
    for event in events:
        if not isinstance(event, dict):
            continue
        if "introduced" in event:
            if _range_has_bound(current):
                intervals.append(current)
            current = {"type": range_type} if range_type else {}
            current["introduced"] = str(event["introduced"])
            continue
        for source_key, target_key in (
            ("fixed", "fixed"),
            ("last_affected", "lastAffected"),
            ("lastAffected", "lastAffected"),
            ("limit", "limit"),
        ):
            if source_key not in event:
                continue
            if not current:
                current = {"type": range_type} if range_type else {}
            current[target_key] = str(event[source_key])
            intervals.append(current)
            current = {"type": range_type} if range_type else {}
            break
    if _range_has_bound(current):
        intervals.append(current)
    return intervals


def _range_has_bound(range_record: Mapping[str, str]) -> bool:
    return any(
        key in range_record
        for key in ("introduced", "fixed", "lastAffected", "limit")
    )
