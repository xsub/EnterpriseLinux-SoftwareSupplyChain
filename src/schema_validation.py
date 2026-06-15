"""Dependency-free validation for documented EDGP JSON contracts."""

from __future__ import annotations

import json
import re
import tarfile
from pathlib import Path
from typing import Any, Mapping

from src.output.report_bundle import (
    verify_report_bundle,
    verify_report_bundle_archive,
)

VALIDATION_SCHEMA = "edgp.validation.report.v1"
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "docs" / "schemas"
SCHEMA_INDEX_PATH = SCHEMA_DIR / "index.json"


def validate_target(path: Path, *, manifest_name: str = "manifest.json") -> dict[str, Any]:
    if path.is_dir():
        return _validate_bundle(path, manifest_name=manifest_name)
    if _is_report_bundle_archive(path):
        return _validate_bundle_archive(path, manifest_name=manifest_name)
    return _validate_json_file(path)


def _is_report_bundle_archive(path: Path) -> bool:
    suffixes = path.suffixes
    return path.suffix == ".tgz" or suffixes[-2:] == [".tar", ".gz"]


def _validate_bundle(path: Path, *, manifest_name: str) -> dict[str, Any]:
    bundle_report = verify_report_bundle(path, manifest_name=manifest_name)
    failures = [
        {
            "code": f"bundle.{failure.get('code', 'unknown')}",
            "message": str(failure.get("message", "")),
            "path": str(failure.get("path", path)),
        }
        for failure in bundle_report.get("failures", [])
        if isinstance(failure, dict)
    ]
    report: dict[str, Any] = {
        "schema": VALIDATION_SCHEMA,
        "target": str(path.resolve()),
        "targetType": "report-bundle",
        "contract": "edgp.report.bundle.v1",
        "ok": not failures,
        "summary": {"failures": len(failures)},
        "failures": failures,
        "bundleVerification": bundle_report,
    }
    triage_summary = _load_bundle_triage_summary(path, manifest_name=manifest_name)
    if triage_summary is not None:
        report["triageSummary"] = triage_summary
    return report


def _validate_bundle_archive(path: Path, *, manifest_name: str) -> dict[str, Any]:
    archive_report = verify_report_bundle_archive(path, manifest_name=manifest_name)
    verification = archive_report.get("verification", {})
    verification_failures = (
        verification.get("failures", []) if isinstance(verification, dict) else []
    )
    failures = [
        {
            "code": f"bundleArchive.{failure.get('code', 'unknown')}",
            "message": str(failure.get("message", "")),
            "path": str(failure.get("path", path)),
        }
        for failure in verification_failures
        if isinstance(failure, dict)
    ]
    report: dict[str, Any] = {
        "schema": VALIDATION_SCHEMA,
        "target": str(path.resolve()),
        "targetType": "report-bundle-archive",
        "contract": "edgp.report.bundle.archive.v1",
        "ok": not failures,
        "summary": {"failures": len(failures)},
        "failures": failures,
        "bundleArchiveVerification": archive_report,
    }
    if not failures:
        triage_summary = _load_bundle_archive_triage_summary(
            path,
            manifest_name=manifest_name,
        )
        if triage_summary is not None:
            report["triageSummary"] = triage_summary
    return report


def _load_bundle_triage_summary(
    bundle_dir: Path,
    *,
    manifest_name: str,
) -> dict[str, Any] | None:
    try:
        manifest = json.loads((bundle_dir / manifest_name).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(manifest, dict):
        return None
    triage_entry = manifest.get("triageSummary")
    if not isinstance(triage_entry, dict):
        return None
    source = triage_entry.get("source")
    if not isinstance(source, str) or not source:
        return None
    source_path = _bundle_member_path(bundle_dir, source)
    if source_path is None:
        return None
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return _triage_summary_summary(source, payload)


def _load_bundle_archive_triage_summary(
    archive_path: Path,
    *,
    manifest_name: str,
) -> dict[str, Any] | None:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            manifest = _load_archive_json_member(archive, manifest_name)
            if manifest is None:
                return None
            triage_entry = manifest.get("triageSummary")
            if not isinstance(triage_entry, dict):
                return None
            source = triage_entry.get("source")
            if not isinstance(source, str) or not source:
                return None
            payload = _load_archive_json_member(archive, source)
            if payload is None:
                return None
    except (FileNotFoundError, OSError, tarfile.TarError):
        return None
    return _triage_summary_summary(source, payload)


def _load_archive_json_member(
    archive: tarfile.TarFile,
    member_name: str,
) -> dict[str, Any] | None:
    if not _is_bundle_member_label(member_name):
        return None
    try:
        member = archive.getmember(member_name)
    except KeyError:
        return None
    if not member.isfile():
        return None
    source = archive.extractfile(member)
    if source is None:
        return None
    try:
        payload = json.loads(source.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _triage_summary_summary(source: str, payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    return {
        "schema": payload.get("schema"),
        "source": source,
        "status": payload.get("status"),
        "summary": summary if isinstance(summary, dict) else {},
    }


def _bundle_member_path(bundle_dir: Path, label: str) -> Path | None:
    if not _is_bundle_member_label(label):
        return None
    return bundle_dir / Path(label)


def _is_bundle_member_label(label: str) -> bool:
    member_path = Path(label)
    return bool(label) and not member_path.is_absolute() and ".." not in member_path.parts


def _validate_json_file(path: Path) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    payload: Any = None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        _add_failure(failures, "fileMissing", "JSON file is missing", str(path))
    except json.JSONDecodeError as error:
        _add_failure(failures, "jsonInvalid", str(error), str(path))

    contract = ""
    schema_file = ""
    if not failures:
        if not isinstance(payload, dict):
            _add_failure(failures, "documentInvalid", "Document must be a JSON object", "$")
        else:
            schema_id = payload.get("schema")
            if not isinstance(schema_id, str) or not schema_id:
                _add_failure(
                    failures,
                    "schemaMissing",
                    "Document must include a non-empty schema field",
                    "$.schema",
                )
            else:
                contract = schema_id
                schema_path = _schema_path_for_contract(schema_id)
                if schema_path is None:
                    _add_failure(
                        failures,
                        "schemaUnsupported",
                        f"No documented schema for {schema_id}",
                        "$.schema",
                    )
                else:
                    schema_file = str(schema_path.relative_to(SCHEMA_DIR))
                    schema = json.loads(schema_path.read_text(encoding="utf-8"))
                    _validate_value(payload, schema, "$", schema, failures)

    return {
        "schema": VALIDATION_SCHEMA,
        "target": str(path.resolve()),
        "targetType": "json-file",
        "contract": contract,
        "schemaFile": schema_file,
        "ok": not failures,
        "summary": {"failures": len(failures)},
        "failures": failures,
    }


def _schema_path_for_contract(contract: str) -> Path | None:
    try:
        index = json.loads(SCHEMA_INDEX_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    schemas = index.get("schemas", [])
    if not isinstance(schemas, list):
        return None
    for entry in schemas:
        if not isinstance(entry, dict) or entry.get("contract") != contract:
            continue
        file_name = entry.get("file")
        if isinstance(file_name, str):
            return SCHEMA_DIR / file_name
    return None


def _validate_value(
    value: Any,
    schema: Mapping[str, Any],
    path: str,
    root_schema: Mapping[str, Any],
    failures: list[dict[str, str]],
) -> None:
    if "$ref" in schema:
        target = _resolve_ref(str(schema["$ref"]), root_schema)
        if target is None:
            _add_failure(failures, "refInvalid", f"Unsupported ref {schema['$ref']}", path)
            return
        _validate_value(value, target, path, root_schema, failures)
        return

    if "anyOf" in schema:
        options = schema.get("anyOf")
        if not isinstance(options, list):
            _add_failure(failures, "anyOfInvalid", "anyOf must be an array", path)
            return
        matches = 0
        for option in options:
            option_failures: list[dict[str, str]] = []
            if isinstance(option, dict):
                _validate_value(value, option, path, root_schema, option_failures)
            else:
                option_failures.append(
                    {"code": "schemaInvalid", "message": "Invalid anyOf option", "path": path}
                )
            if not option_failures:
                matches += 1
        if matches < 1:
            _add_failure(failures, "anyOfMismatch", "Value must match at least one schema", path)

    if "oneOf" in schema:
        options = schema.get("oneOf")
        if not isinstance(options, list):
            _add_failure(failures, "oneOfInvalid", "oneOf must be an array", path)
            return
        matches = 0
        for option in options:
            option_failures: list[dict[str, str]] = []
            if isinstance(option, dict):
                _validate_value(value, option, path, root_schema, option_failures)
            else:
                option_failures.append(
                    {"code": "schemaInvalid", "message": "Invalid oneOf option", "path": path}
                )
            if not option_failures:
                matches += 1
        if matches != 1:
            _add_failure(failures, "oneOfMismatch", "Value must match exactly one schema", path)
        return

    if "const" in schema and value != schema["const"]:
        _add_failure(failures, "constMismatch", f"Expected {schema['const']!r}", path)

    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        _add_failure(failures, "enumMismatch", "Value is not in the allowed set", path)

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        _add_failure(
            failures,
            "typeMismatch",
            f"Expected type {_type_label(expected_type)}",
            path,
        )
        return

    if isinstance(value, str):
        if isinstance(schema.get("minLength"), int) and len(value) < schema["minLength"]:
            _add_failure(failures, "minLengthViolation", "String is too short", path)
        pattern = schema.get("pattern")
        if isinstance(pattern, str) and re.fullmatch(pattern, value) is None:
            _add_failure(failures, "patternMismatch", "String does not match pattern", path)

    if isinstance(value, int) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, int | float) and value < minimum:
            _add_failure(failures, "minimumViolation", "Number is below minimum", path)

    if isinstance(value, list):
        min_items = schema.get("minItems")
        if isinstance(min_items, int) and len(value) < min_items:
            _add_failure(failures, "minItemsViolation", "Array is too short", path)
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_value(item, item_schema, f"{path}[{index}]", root_schema, failures)

    if isinstance(value, dict):
        properties = schema.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        required = schema.get("required")
        if isinstance(required, list):
            for key in required:
                if isinstance(key, str) and key not in value:
                    _add_failure(
                        failures,
                        "requiredMissing",
                        f"Missing required field {key}",
                        _child_path(path, key),
                    )
        additional_properties = schema.get("additionalProperties")
        if additional_properties is False:
            for key in value:
                if key not in properties:
                    _add_failure(
                        failures,
                        "fieldUnknown",
                        f"Unsupported field {key}",
                        _child_path(path, key),
                    )
        elif isinstance(additional_properties, dict):
            for key, item in value.items():
                if key not in properties:
                    _validate_value(
                        item,
                        additional_properties,
                        _child_path(path, str(key)),
                        root_schema,
                        failures,
                    )
        for key, property_schema in properties.items():
            if key in value and isinstance(property_schema, dict):
                _validate_value(
                    value[key],
                    property_schema,
                    _child_path(path, str(key)),
                    root_schema,
                    failures,
                )


def _resolve_ref(ref: str, root_schema: Mapping[str, Any]) -> Mapping[str, Any] | None:
    if not ref.startswith("#/$defs/"):
        return None
    defs = root_schema.get("$defs")
    if not isinstance(defs, dict):
        return None
    target = defs.get(ref.removeprefix("#/$defs/"))
    return target if isinstance(target, dict) else None


def _matches_type(value: Any, expected_type: Any) -> bool:
    if isinstance(expected_type, list):
        return any(_matches_type(value, item) for item in expected_type)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "null":
        return value is None
    return True


def _type_label(expected_type: Any) -> str:
    if isinstance(expected_type, list):
        return " or ".join(str(item) for item in expected_type)
    return str(expected_type)


def _child_path(path: str, key: str) -> str:
    return f"{path}.{key}" if path != "$" else f"$.{key}"


def _add_failure(
    failures: list[dict[str, str]],
    code: str,
    message: str,
    path: str,
) -> None:
    failures.append({"code": code, "message": message, "path": path})
