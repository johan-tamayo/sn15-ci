"""Validation of agent tool arguments against a tool's parameter schema (the documented subset)."""

from __future__ import annotations


class Invalid(ValueError):
    """The arguments do not satisfy the schema."""


def _is_type(value: object, name: str) -> bool:
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "array":
        return isinstance(value, list)
    return isinstance(value, dict)


def _same(a: object, b: object) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    return a == b


def validate(instance: object, schema: dict, path: str = "$") -> None:
    """Raise Invalid with the first failing path unless `instance` satisfies `schema`."""
    if "type" in schema:
        names = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(instance, n) for n in names):
            raise Invalid(f"{path}: expected {'/'.join(names)}")
    if "const" in schema and not _same(instance, schema["const"]):
        raise Invalid(f"{path}: must equal the constant")
    if "enum" in schema and not any(_same(instance, v) for v in schema["enum"]):
        raise Invalid(f"{path}: not one of the allowed values")
    if isinstance(instance, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in instance:
                raise Invalid(f"{path}: missing required property {name!r}")
        extra = schema.get("additionalProperties", True)
        for name, value in instance.items():
            if name in props:
                validate(value, props[name], f"{path}.{name}")
            elif extra is False:
                raise Invalid(f"{path}: unknown property {name!r}")
            elif isinstance(extra, dict):
                validate(value, extra, f"{path}.{name}")
    if isinstance(instance, list):
        if not schema.get("minItems", 0) <= len(instance) <= schema.get("maxItems", len(instance)):
            raise Invalid(f"{path}: array length out of range")
        for i, item in enumerate(instance):
            if "items" in schema:
                validate(item, schema["items"], f"{path}[{i}]")
    if isinstance(instance, str) and not schema.get("minLength", 0) <= len(instance) <= schema.get("maxLength", len(instance)):
        raise Invalid(f"{path}: string length out of range")
    if _is_type(instance, "number"):
        if "minimum" in schema and instance < schema["minimum"]:
            raise Invalid(f"{path}: below the minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            raise Invalid(f"{path}: above the maximum")
