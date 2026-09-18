"""Dependency-free validator for the checked-in scenario JSON Schema subset.

The supported keywords are intentionally explicit and fail closed. This keeps
fixture validation reproducible on Python 3.11 without ambient packages.
"""

import json
import re
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any


class SchemaValidationError(ValueError):
    pass


_SUPPORTED_SCHEMA_KEYWORDS = {
    "$schema",
    "$id",
    "$defs",
    "$ref",
    "title",
    "description",
    "type",
    "required",
    "properties",
    "additionalProperties",
    "enum",
    "pattern",
    "minLength",
    "minimum",
    "maximum",
    "minItems",
    "minProperties",
    "uniqueItems",
    "items",
    "allOf",
    "if",
    "then",
}
_JSON_TYPES = {"object", "array", "string", "boolean", "integer", "number", "null"}


def _validate_schema_node(schema: Any, path: str = "$") -> None:
    if not isinstance(schema, dict):
        raise SchemaValidationError(f"{path}: schema node must be an object")
    unsupported = set(schema) - _SUPPORTED_SCHEMA_KEYWORDS
    if unsupported:
        raise SchemaValidationError(
            f"{path}: unsupported schema keyword(s): {sorted(unsupported)}"
        )

    declared_types = schema.get("type", [])
    declared_types = [declared_types] if isinstance(declared_types, str) else declared_types
    if not isinstance(declared_types, list) or any(
        item not in _JSON_TYPES for item in declared_types
    ):
        raise SchemaValidationError(f"{path}: invalid schema type declaration")

    for list_keyword in ("required", "enum"):
        if list_keyword in schema and not isinstance(schema[list_keyword], list):
            raise SchemaValidationError(f"{path}.{list_keyword}: must be an array")
    for string_keyword in ("$schema", "$id", "$ref", "title", "description", "pattern"):
        if string_keyword in schema and not isinstance(schema[string_keyword], str):
            raise SchemaValidationError(f"{path}.{string_keyword}: must be a string")
    for integer_keyword in ("minLength", "minItems", "minProperties"):
        value = schema.get(integer_keyword, 0)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SchemaValidationError(
                f"{path}.{integer_keyword}: must be a non-negative integer"
            )
    if "uniqueItems" in schema and not isinstance(schema["uniqueItems"], bool):
        raise SchemaValidationError(f"{path}.uniqueItems: must be boolean")
    if "additionalProperties" in schema and not isinstance(
        schema["additionalProperties"], bool
    ):
        raise SchemaValidationError(f"{path}.additionalProperties: must be boolean")

    for map_keyword in ("properties", "$defs"):
        children = schema.get(map_keyword, {})
        if not isinstance(children, dict):
            raise SchemaValidationError(f"{path}.{map_keyword}: must be an object")
        for name, child in children.items():
            _validate_schema_node(child, f"{path}.{map_keyword}.{name}")
    if "items" in schema:
        _validate_schema_node(schema["items"], f"{path}.items")
    for list_keyword in ("allOf",):
        children = schema.get(list_keyword, [])
        if not isinstance(children, list):
            raise SchemaValidationError(f"{path}.{list_keyword}: must be an array")
        for index, child in enumerate(children):
            _validate_schema_node(child, f"{path}.{list_keyword}[{index}]")
    for child_keyword in ("if", "then"):
        if child_keyword in schema:
            _validate_schema_node(schema[child_keyword], f"{path}.{child_keyword}")


def validate_schema(schema: dict[str, Any]) -> None:
    """Reject schemas outside the deliberately supported keyword subset."""

    _validate_schema_node(schema)


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

    if "enum" in schema and not any(_json_equal(value, item) for item in schema["enum"]):
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
        if len(value) < schema.get("minProperties", 0):
            raise SchemaValidationError(f"{path}: object has too few properties")
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

    validate_schema(schema)
    _validate(instance, schema, schema, "$")


_ISO_8601_TIMESTAMP = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?"
    r"(?:Z|[+-][0-9]{2}:[0-9]{2})$"
)


def validate_result(instance: dict[str, Any], schema: dict[str, Any]) -> None:
    """Validate a result document plus its cross-field and timestamp rules."""

    validate_instance(instance, schema)
    scenario_id = instance["scenarioId"]
    prefix = f"results/{scenario_id}/"
    if any(not path.startswith(prefix) for path in instance["sourceEvidence"]):
        raise SchemaValidationError(
            "result sourceEvidence must stay within its exact scenario directory"
        )

    recorded_at = instance["recordedAt"]
    if _ISO_8601_TIMESTAMP.fullmatch(recorded_at) is None:
        raise SchemaValidationError("recordedAt must be an ISO-8601 timestamp with timezone")
    offset = re.search(r"[+-]([0-9]{2}):([0-9]{2})$", recorded_at)
    if offset and (int(offset.group(1)) > 23 or int(offset.group(2)) > 59):
        raise SchemaValidationError("recordedAt has an out-of-range timezone offset")
    try:
        parsed = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    except ValueError as error:
        raise SchemaValidationError("recordedAt is not a valid ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SchemaValidationError("recordedAt must include UTC Z or an explicit offset")


def _json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            _json_equal(left[key], right[key]) for key in left
        )
    return left == right


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
        return _json_equal(actual, expected)
    if operator == "not_eq":
        return not _json_equal(actual, expected)
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
        return _json_equal(actual["before"], actual["after"]) is expected
    raise SchemaValidationError(f"unsupported condition operator: {operator}")


def _load_contract_schema(filename: str) -> dict[str, Any]:
    path = Path(__file__).with_name(filename)
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_result_path(result_path: str | Path) -> str:
    raw = result_path.as_posix() if isinstance(result_path, Path) else str(result_path)
    if (
        not raw
        or "\\" in raw
        or raw.startswith("/")
        or raw.startswith("//")
        or re.match(r"^[A-Za-z]:", raw)
    ):
        raise SchemaValidationError("result_path must be a POSIX-relative path")
    parts = raw.split("/")
    if any(not part or re.fullmatch(r"\.+", part) for part in parts):
        raise SchemaValidationError("result_path contains an unsafe path component")
    normalized = PurePosixPath(raw).as_posix()
    if normalized != raw:
        raise SchemaValidationError("result_path is not normalized")
    return normalized


def evaluate_scenario_result(
    scenario: dict[str, Any], result: dict[str, Any], result_path: str | Path
) -> dict[str, Any]:
    """Validate and evaluate one scenario result without trusting self-attestation."""

    scenario_schema = _load_contract_schema("scenario-contract.schema.json")
    result_schema = _load_contract_schema("result-contract.schema.json")
    validate_scenario(scenario, scenario_schema)
    validate_result(result, result_schema)

    scenario_id = scenario["id"]
    if result["scenarioId"] != scenario_id:
        raise SchemaValidationError("result scenarioId does not match scenario id")
    expected_path = f"results/{scenario_id}/result.json"
    if expected_path not in scenario["evidence"]:
        raise SchemaValidationError("scenario does not declare its canonical result path")
    if _normalized_result_path(result_path) != expected_path:
        raise SchemaValidationError("loaded result_path is not the canonical scenario result")

    details = []
    for group_name in ("passCriteria", "forbiddenBehavior"):
        for criterion in scenario[group_name]:
            satisfied = evaluate_condition(result, criterion["condition"])
            details.append(
                {
                    "id": criterion["id"],
                    "group": group_name,
                    "oracle": criterion["oracle"],
                    "condition": criterion["condition"],
                    "evidenceRequired": criterion["evidenceRequired"],
                    "satisfied": satisfied,
                }
            )

    criteria_passed = all(item["satisfied"] for item in details)
    result_status = result["status"]
    if result_status in {"blocked", "incomplete"}:
        outcome = result_status
        passed = False
    else:
        outcome = "passed" if criteria_passed else "failed"
        passed = criteria_passed
    return {
        "scenarioId": scenario_id,
        "resultPath": expected_path,
        "resultStatus": result_status,
        "outcome": outcome,
        "passed": passed,
        "criteria": details,
        "failedCriteria": [item["id"] for item in details if not item["satisfied"]],
    }


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
