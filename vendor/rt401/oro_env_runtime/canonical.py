"""Canonical JSON: UTF-8, sorted keys, no whitespace, i64 integers, finite floats, str keys, bounded nesting."""

from __future__ import annotations

import hashlib
import json
import math

I64_MIN, I64_MAX = -(2**63), 2**63 - 1
MAX_DEPTH = 256  # arrays and objects nested in each other


class NotCanonical(ValueError):
    """A value outside the canonical JSON value set."""


def is_text(value: object) -> bool:
    """Whether `value` is a str that encodes as UTF-8 (no lone surrogates)."""
    if not isinstance(value, str):
        return False
    try:
        value.encode()
    except UnicodeEncodeError:
        return False
    return True


def check(value: object, depth: int = MAX_DEPTH) -> object:
    """Return `value` if it is canonical JSON nested at most `depth` deep, else raise NotCanonical."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        if not is_text(value):
            raise NotCanonical("string is not valid UTF-8")
        return value
    if isinstance(value, int):
        if not I64_MIN <= value <= I64_MAX:
            raise NotCanonical("integer outside the i64 range")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise NotCanonical("non-finite number")
    elif isinstance(value, (list, dict)):
        if depth < 1:
            raise NotCanonical("nested too deeply")
        if isinstance(value, dict) and not all(is_text(key) for key in value):
            raise NotCanonical("non-string or non-UTF-8 key")
        for item in value.values() if isinstance(value, dict) else value:
            check(item, depth - 1)
    else:
        raise NotCanonical(f"unsupported type {type(value).__name__}")
    return value


def dumps(value: object) -> bytes:
    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value: object) -> str:
    return sha256_hex(dumps(value))
