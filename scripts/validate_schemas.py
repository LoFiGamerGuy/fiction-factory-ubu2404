"""Validates all *.schema.json files in schemas/ against JSON Schema Draft 2020-12."""

import json
import sys
from pathlib import Path

import jsonschema


def validate_schemas() -> int:
    schema_root = Path(__file__).parent.parent / "schemas"
    schema_files = sorted(schema_root.rglob("*.schema.json"))

    if not schema_files:
        print("No schema files found in schemas/.")
        return 1

    errors: list[str] = []
    for path in schema_files:
        rel = path.relative_to(schema_root.parent)
        try:
            with path.open() as f:
                schema = json.load(f)
            jsonschema.Draft202012Validator.check_schema(schema)
            print(f"  ✓  {rel}")
        except (json.JSONDecodeError, jsonschema.SchemaError) as exc:
            msg = f"  ✗  {rel}: {exc}"
            errors.append(msg)
            print(msg)

    total = len(schema_files)
    passed = total - len(errors)
    print(f"\n{passed}/{total} schemas valid.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(validate_schemas())
