"""Validates all *.schema.json files in schemas/ and all *.yaml profile files in profiles/."""

import json
import sys
from pathlib import Path

import jsonschema
import yaml

_PROFILE_TYPE_TO_SCHEMA = {
    "author": "schemas/profiles/author_profile.schema.json",
    "genre": "schemas/profiles/genre_profile.schema.json",
    "audience": "schemas/profiles/audience_profile.schema.json",
    "sensitivity": "schemas/profiles/sensitivity_profile.schema.json",
    "goal": "schemas/profiles/goal_profile.schema.json",
}


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


def validate_profiles() -> int:
    project_root = Path(__file__).parent.parent
    profiles_root = project_root / "profiles"
    yaml_files = sorted(profiles_root.rglob("*.yaml"))

    if not yaml_files:
        print("No profile YAML files found in profiles/.")
        return 0

    errors: list[str] = []
    for path in yaml_files:
        rel = path.relative_to(project_root)
        profile_type = path.parent.name
        schema_rel = _PROFILE_TYPE_TO_SCHEMA.get(profile_type)
        if schema_rel is None:
            print(f"  ?  {rel}: unknown profile type '{profile_type}' — skipped")
            continue
        schema_path = project_root / schema_rel
        try:
            schema = json.loads(schema_path.read_text())
            raw = yaml.safe_load(path.read_text())
            jsonschema.validate(instance=raw, schema=schema)
            print(f"  ✓  {rel}")
        except jsonschema.ValidationError as exc:
            msg = f"  ✗  {rel}: {exc.message}"
            errors.append(msg)
            print(msg)
        except Exception as exc:
            msg = f"  ✗  {rel}: {exc}"
            errors.append(msg)
            print(msg)

    total = len(yaml_files)
    passed = total - len(errors)
    print(f"\n{passed}/{total} profile YAML files valid.")
    return 1 if errors else 0


if __name__ == "__main__":
    print("=== JSON Schema validation ===")
    schema_rc = validate_schemas()
    print("\n=== Profile YAML validation ===")
    profile_rc = validate_profiles()
    sys.exit(max(schema_rc, profile_rc))
