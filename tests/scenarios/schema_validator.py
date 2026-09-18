"""Dependency-free validator for the checked-in scenario JSON Schema subset.

The supported keywords are intentionally explicit and fail closed. This keeps
fixture validation reproducible on Python 3.11 without ambient packages.
"""

import json
import re
from typing import Any


class SchemaValidationError(ValueError):
    pass


def _resolve_ref(root_schema: dict[str, Any], reference: str) -> dict[str, Any]:
    if not reference.startswith("#/"):
        raise SchemaValidationError(f"external schema reference is not allowed: {reference}")
    current: Any = root_schema
    for part in reference[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or key not in current:
            raise SchemaValidationError(f"unresolved schema reference: {reference}")
        current = current[key]
    if not isinstance(current, dict):
        raise SchemaValidationError(f"schema reference is not an object: {reference}")
    return current


def _is_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    raise SchemaValidationError(f"unsupported schema type: {expected}")


def _matches(value: Any, schema: dict[str, Any], root: dict[str, Any]) -> bool:
    try:
        _validate(value, schema, root, "$")
    except SchemaValidationError:
        return False
    return True


def _validate(value: Any, schema: dict[str, Any], root: dict[str, Any], path: str) -> None:
    if "$ref" in schema:
        _validate(value, _resolve_ref(root, schema["$ref"]), root, path)
        return

    if "allOf" in schema:
        for index, child in enumerate(schema["allOf"]):
            _validate(value, child, root, f"{path}.allOf[{index}]")

    if "if" in schema and _matches(value, schema["if"], root):
        _validate(value, schema.get("then", {}), root, path)

    expected_types = schema.get("type")
    if expected_types is not None:
        if isinstance(expected_types, str):
            expected_types = [expected_types]
        if not any(_is_type(value, expected) for expected in expected_types):
            raise SchemaValidationError(
                f"{path}: expected type {expected_types}, got {type(value).__name__}"
            )

    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationError(f"{path}: value is not in enum")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise SchemaValidationError(f"{path}: string is too short")
        if "pattern" in schema and re.fullmatch(schema["pattern"], value) is None:
            raise SchemaValidationError(f"{path}: string does not match pattern")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaValidationError(f"{path}: value is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaValidationError(f"{path}: value exceeds maximum")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise SchemaValidationError(f"{path}: array has too few items")
        if schema.get("uniqueItems"):
            canonical = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value]
            if len(canonical) != len(set(canonical)):
                raise SchemaValidationError(f"{path}: array items are not unique")
        if "items" in schema:
            for index, item in enumerate(value):
                _validate(item, schema["items"], root, f"{path}[{index}]")

    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise SchemaValidationError(f"{path}: missing required keys {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extra = set(value) - set(properties)
            if extra:
                raise SchemaValidationError(f"{path}: undeclared keys {sorted(extra)}")
        for key, child_schema in properties.items():
            if key in value:
                _validate(value[key], child_schema, root, f"{path}.{key}")


def validate_instance(instance: Any, schema: dict[str, Any]) -> None:
    """Validate an instance or raise SchemaValidationError."""

    _validate(instance, schema, schema, "$")


def _lookup(document: dict[str, Any], dotted_path: str) -> tuple[bool, Any]:
    current: Any = document
    for segment in dotted_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def evaluate_condition(document: dict[str, Any], condition: dict[str, Any]) -> bool:
    """Evaluate the closed condition DSL without eval or dynamic dispatch."""

    found, actual = _lookup(document, condition["path"])
    operator = condition["operator"]
    expected = condition["expected"]
    if operator == "exists":
        if not isinstance(expected, bool):
            raise SchemaValidationError("exists requires a boolean expected value")
        return found is expected
    if not found:
        return False
    if operator == "eq":
        return actual == expected
    if operator == "not_eq":
        return actual != expected
    if operator in {"gte", "lte"}:
        if (
            not isinstance(actual, (int, float))
            or isinstance(actual, bool)
            or not isinstance(expected, (int, float))
            or isinstance(expected, bool)
        ):
            raise SchemaValidationError(f"{operator} requires numeric values")
        return actual >= expected if operator == "gte" else actual <= expected
    if operator == "unchanged":
        if not isinstance(expected, bool):
            raise SchemaValidationError("unchanged requires a boolean expected value")
        if not isinstance(actual, dict) or set(actual) != {"before", "after"}:
            raise SchemaValidationError(
                "unchanged requires an object with exactly before and after"
            )
        return (actual["before"] == actual["after"]) is expected
    raise SchemaValidationError(f"unsupported condition operator: {operator}")


def validate_scenario(instance: dict[str, Any], schema: dict[str, Any]) -> None:
    """Apply JSON Schema plus cross-field scenario invariants."""

    validate_instance(instance, schema)
    scenario_id = instance["id"]
    evidence = set(instance["evidence"])
    prefix = f"results/{scenario_id}/"
    if any(not path.startswith(prefix) for path in evidence):
        raise SchemaValidationError("evidence must stay within its scenario directory")

    seen_ids = set()
    for group_name, id_kind in (
        ("passCriteria", "pass"),
        ("forbiddenBehavior", "forbid"),
    ):
        for criterion in instance[group_name]:
            criterion_id = criterion["id"]
            if not re.fullmatch(
                rf"{re.escape(scenario_id)}\.{id_kind}\.[0-9]{{2}}", criterion_id
            ):
                raise SchemaValidationError(
                    f"criterion id does not match its scenario/group: {criterion_id}"
                )
            if criterion_id in seen_ids:
                raise SchemaValidationError(f"duplicate criterion id: {criterion_id}")
            seen_ids.add(criterion_id)
            required = set(criterion["evidenceRequired"])
            if not required <= evidence:
                raise SchemaValidationError(
                    f"criterion evidence is not declared at top level: {criterion_id}"
                )
            if any(not path.startswith(prefix) for path in required):
                raise SchemaValidationError(
                    f"criterion evidence leaves scenario directory: {criterion_id}"
                )
