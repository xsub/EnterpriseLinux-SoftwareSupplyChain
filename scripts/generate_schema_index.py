"""Generate a deterministic index for documented EDGP JSON Schemas."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = REPO_ROOT / "docs" / "schemas"
INDEX_PATH = SCHEMA_DIR / "index.json"
INDEX_SCHEMA = "edgp.schema.index.v1"


def build_schema_index(schema_dir: Path = SCHEMA_DIR) -> dict[str, Any]:
    schemas = [
        _schema_entry(path, schema_dir)
        for path in sorted(schema_dir.glob("*.schema.json"))
    ]
    return {
        "schema": INDEX_SCHEMA,
        "generatedBy": "scripts/generate_schema_index.py",
        "schemaCount": len(schemas),
        "schemas": schemas,
    }


def _schema_entry(path: Path, schema_dir: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entry = {
        "file": str(path.relative_to(schema_dir)),
        "id": str(payload.get("$id", "")),
        "jsonSchema": str(payload.get("$schema", "")),
        "title": str(payload.get("title", "")),
        "description": str(payload.get("description", "")),
    }
    contract = _contract_schema(payload)
    if contract:
        entry["contract"] = contract
    return entry


def _contract_schema(payload: dict[str, Any]) -> str:
    properties = payload.get("properties", {})
    if not isinstance(properties, dict):
        return ""
    schema_property = properties.get("schema", {})
    if not isinstance(schema_property, dict):
        return ""
    const = schema_property.get("const")
    return const if isinstance(const, str) else ""


def write_schema_index(output_path: Path = INDEX_PATH) -> Path:
    output_path.write_text(
        json.dumps(build_schema_index(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=INDEX_PATH)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the existing index does not match generated content",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    expected = build_schema_index()
    if args.check:
        actual = json.loads(args.output.read_text(encoding="utf-8"))
        if actual != expected:
            print(f"{args.output} is out of date")
            return 1
        return 0

    args.output.write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
