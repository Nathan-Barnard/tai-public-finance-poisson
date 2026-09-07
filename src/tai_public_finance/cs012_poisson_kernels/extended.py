"""Extended-real values, canonical JSON, and hashing for the CS012 I0 core.

This module carries no model equation and no result semantics. It exists so that
the package never needs to import CS005 code (whose ``primitives`` module holds
the quarantined pre-arrival equation route alongside its generic helpers).

``ExtendedReal`` is the tagged representation the handoff requires: JSON cannot
portably encode infinity, so an extended-real field is serialized as an explicit
``{"kind": ..., "value": ...}`` object, never as a non-standard ``Infinity``
token and never as a large finite sentinel.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

FINITE = "finite"
POSITIVE_INFINITY = "positive_infinity"
NEGATIVE_INFINITY = "negative_infinity"
UNDEFINED = "undefined"
NOT_A_NUMBER = "not_a_number"

EXTENDED_KINDS = (FINITE, POSITIVE_INFINITY, NEGATIVE_INFINITY, UNDEFINED, NOT_A_NUMBER)


class ExtendedRealError(ValueError):
    """Raised when a finite value is demanded from a non-finite extended real."""


@dataclass(frozen=True, slots=True)
class ExtendedReal:
    """A real number, ``+inf``, ``-inf``, NaN, or an explicitly undefined value.

    The ``kind`` tag is authoritative. ``value`` is populated only when
    ``kind == "finite"``; for every other kind it is ``None``, so that no caller
    can silently read a sentinel number out of a boundary object.
    """

    kind: str
    value: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in EXTENDED_KINDS:
            raise ValueError(f"unknown extended-real kind: {self.kind!r}")
        if self.kind == FINITE:
            if self.value is None or not math.isfinite(self.value):
                raise ValueError("finite ExtendedReal needs a finite value")
        elif self.value is not None:
            raise ValueError(f"{self.kind} ExtendedReal must not carry a value")

    @property
    def is_finite(self) -> bool:
        return self.kind == FINITE

    def require_finite(self) -> float:
        if self.kind != FINITE:
            raise ExtendedRealError(
                f"refused: extended-real value is {self.kind}, not a finite number"
            )
        assert self.value is not None  # narrowed by __post_init__
        return self.value

    def as_float(self) -> float:
        """The IEEE-754 image of this value, for diagnostics only.

        ``UNDEFINED`` has no float image and raises; it is not silently NaN.
        """
        if self.kind == FINITE:
            assert self.value is not None
            return self.value
        if self.kind == POSITIVE_INFINITY:
            return math.inf
        if self.kind == NEGATIVE_INFINITY:
            return -math.inf
        if self.kind == NOT_A_NUMBER:
            return math.nan
        raise ExtendedRealError("undefined has no floating-point image")

    def to_json(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value}

    @staticmethod
    def from_json(payload: Any) -> "ExtendedReal":
        if not isinstance(payload, dict):
            raise ValueError("extended-real payload must be a tagged object")
        kind = payload.get("kind")
        if not isinstance(kind, str):
            raise ValueError("extended-real payload needs a string 'kind'")
        value = payload.get("value")
        if value is not None and not isinstance(value, (int, float)):
            raise ValueError("extended-real 'value' must be a number or null")
        if isinstance(value, bool):
            raise ValueError("extended-real 'value' must not be a boolean")
        return ExtendedReal(kind=kind, value=None if value is None else float(value))

    @staticmethod
    def of(number: float) -> "ExtendedReal":
        """Classify an ordinary float, without clipping or regularizing it."""
        if math.isnan(number):
            return ExtendedReal(NOT_A_NUMBER)
        if number == math.inf:
            return ExtendedReal(POSITIVE_INFINITY)
        if number == -math.inf:
            return ExtendedReal(NEGATIVE_INFINITY)
        return ExtendedReal(FINITE, float(number))


POSITIVE_INFINITE = ExtendedReal(POSITIVE_INFINITY)
UNDEFINED_VALUE = ExtendedReal(UNDEFINED)


def canonical_json(value: Any) -> str:
    """Key-sorted, whitespace-free JSON: the fingerprinting normal form."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_of_object(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_of_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
