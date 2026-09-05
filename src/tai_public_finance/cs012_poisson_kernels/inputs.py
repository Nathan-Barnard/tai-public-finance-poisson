"""Direct I0 inputs: one labelled mark record per automation mark, plus the two
fixture-level scalars.

Field order below is the serialization order CS012 v0.1 fixes for fingerprinting
("I0 identity-core inputs"). Mark identity is carried by ``mark_id`` and by input
order; nothing here ever infers economic identity from a sorted value.

Units, following CS012 v0.1:

* ``lambda_physical``      inverse time, strictly positive
* ``lambda_risk_neutral``  inverse time, nonnegative
* ``payoff_jump``          current-good total gain per unit of installed equity
* ``owner_exposure``       inverse payoff unit (an equity wealth share)
* ``government_*_marginal_value``  utility per current good
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .extended import FINITE, POSITIVE_INFINITY, ExtendedReal
from .statuses import BRANCH_FINITE_MAINTAINED, BRANCH_LITERAL_LAISSEZ_FAIRE, DECLARED_BRANCHES

MARK_FIELD_ORDER = (
    "mark_id",
    "lambda_physical",
    "lambda_risk_neutral",
    "payoff_jump",
    "government_successor_marginal_value",
    "owner_wealth_before",
    "owner_wealth_after",
)
"""Frozen serialization order for the per-mark direct fields."""

FIXTURE_FIELD_ORDER = (
    "fixture_id",
    "declared_branch",
    "owner_exposure",
    "government_current_marginal_value",
    "worker_consumption",
    "marks",
)
"""Frozen serialization order for the fixture-level direct fields."""

FORMULA_CONVENTION = "CS012-I0-v0.1"
"""Names the exact sign and kernel convention this package implements:
``k_world = lambda_star/lambda``, ``k_owner = 1/(1+pi*J)``,
``k_government = V_successor/mu_current``, ``gamma = k_government/k_owner``,
and residuals ``sum_j lambda_j * (k_a[j] - k_b[j]) * J_j``."""


class InputError(ValueError):
    """Structurally malformed input: a missing field, a wrong type, a bad tag.

    This is distinct from an *admissible-domain* violation (a negative intensity,
    say), which is reported as a status, not raised.
    """


def _require_real(payload: Any, field: str) -> float:
    if isinstance(payload, bool) or not isinstance(payload, (int, float)):
        raise InputError(f"{field} must be a JSON number")
    return float(payload)


@dataclass(frozen=True, slots=True)
class MarkInput:
    """One labelled mark's direct fields.

    ``owner_wealth_before``/``owner_wealth_after`` are the optional independent
    wealth-ratio route for the owner kernel. When both routes are present they
    must agree; disagreement is ``invalid_direct_wealth_ratio``, never a silent
    preference for one route.
    """

    mark_id: str
    lambda_physical: float
    lambda_risk_neutral: float
    payoff_jump: float
    government_successor_marginal_value: ExtendedReal
    owner_wealth_before: float | None = None
    owner_wealth_after: float | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mark_id, str) or not self.mark_id:
            raise InputError("mark_id must be a non-empty string")
        if not isinstance(self.government_successor_marginal_value, ExtendedReal):
            raise InputError(
                "government_successor_marginal_value must be a tagged ExtendedReal"
            )
        if (self.owner_wealth_before is None) != (self.owner_wealth_after is None):
            raise InputError(
                "owner_wealth_before and owner_wealth_after must be supplied together"
            )

    def to_json(self) -> dict[str, Any]:
        return {
            "mark_id": self.mark_id,
            "lambda_physical": self.lambda_physical,
            "lambda_risk_neutral": self.lambda_risk_neutral,
            "payoff_jump": self.payoff_jump,
            "government_successor_marginal_value": (
                self.government_successor_marginal_value.to_json()
            ),
            "owner_wealth_before": self.owner_wealth_before,
            "owner_wealth_after": self.owner_wealth_after,
        }

    @staticmethod
    def from_json(payload: Any) -> "MarkInput":
        if not isinstance(payload, dict):
            raise InputError("a mark record must be a JSON object")
        unknown = set(payload) - set(MARK_FIELD_ORDER)
        if unknown:
            raise InputError(f"unknown mark fields: {sorted(unknown)}")
        for required in MARK_FIELD_ORDER[:5]:
            if required not in payload:
                raise InputError(f"mark record is missing {required}")
        before = payload.get("owner_wealth_before")
        after = payload.get("owner_wealth_after")
        return MarkInput(
            mark_id=payload["mark_id"],
            lambda_physical=_require_real(payload["lambda_physical"], "lambda_physical"),
            lambda_risk_neutral=_require_real(
                payload["lambda_risk_neutral"], "lambda_risk_neutral"
            ),
            payoff_jump=_require_real(payload["payoff_jump"], "payoff_jump"),
            government_successor_marginal_value=ExtendedReal.from_json(
                payload["government_successor_marginal_value"]
            ),
            owner_wealth_before=(
                None if before is None else _require_real(before, "owner_wealth_before")
            ),
            owner_wealth_after=(
                None if after is None else _require_real(after, "owner_wealth_after")
            ),
        )


@dataclass(frozen=True, slots=True)
class FixtureInput:
    """One manufactured fixture: an ordered tuple of marks plus fixture scalars.

    ``declared_branch`` is an input, not an inference. A fixture that intends the
    literal laissez-faire boundary must say so; the evaluator then refuses to run
    finite residual arithmetic on it even if some fields happen to be finite.
    """

    fixture_id: str
    declared_branch: str
    owner_exposure: float
    government_current_marginal_value: float
    marks: tuple[MarkInput, ...]
    worker_consumption: float | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.fixture_id, str) or not self.fixture_id:
            raise InputError("fixture_id must be a non-empty string")
        if self.declared_branch not in DECLARED_BRANCHES:
            raise InputError(f"unknown declared_branch: {self.declared_branch!r}")
        if not isinstance(self.marks, tuple) or not self.marks:
            raise InputError("marks must be a non-empty tuple, in input order")
        seen: set[str] = set()
        for mark in self.marks:
            if not isinstance(mark, MarkInput):
                raise InputError("every mark must be a MarkInput")
            if mark.mark_id in seen:
                raise InputError(f"duplicate mark_id: {mark.mark_id!r}")
            seen.add(mark.mark_id)

    @property
    def mark_ids(self) -> tuple[str, ...]:
        return tuple(mark.mark_id for mark in self.marks)

    @property
    def payoff_vector(self) -> tuple[float, ...]:
        return tuple(mark.payoff_jump for mark in self.marks)

    @property
    def is_zero_payoff(self) -> bool:
        """Exactly zero, not "small": a zero payoff vector is a rank change."""
        return all(jump == 0.0 for jump in self.payoff_vector)

    def direct_fields(self) -> dict[str, Any]:
        """The operative direct fields, in the frozen serialization order.

        Excludes paths, prose (``description``), timestamps, and every computed
        residual, per CS012 v0.1's fingerprint rule.
        """
        return {
            "fixture_id": self.fixture_id,
            "declared_branch": self.declared_branch,
            "owner_exposure": self.owner_exposure,
            "government_current_marginal_value": self.government_current_marginal_value,
            "worker_consumption": self.worker_consumption,
            "marks": [mark.to_json() for mark in self.marks],
        }

    def to_json(self) -> dict[str, Any]:
        payload = self.direct_fields()
        payload["description"] = self.description
        return payload

    @staticmethod
    def from_json(payload: Any) -> "FixtureInput":
        if not isinstance(payload, dict):
            raise InputError("a fixture must be a JSON object")
        allowed = set(FIXTURE_FIELD_ORDER) | {"description"}
        unknown = set(payload) - allowed
        if unknown:
            raise InputError(f"unknown fixture fields: {sorted(unknown)}")
        for required in ("fixture_id", "declared_branch", "owner_exposure",
                         "government_current_marginal_value", "marks"):
            if required not in payload:
                raise InputError(f"fixture is missing {required}")
        raw_marks = payload["marks"]
        if not isinstance(raw_marks, list):
            raise InputError("marks must be a JSON array, preserving input order")
        worker_consumption = payload.get("worker_consumption")
        return FixtureInput(
            fixture_id=payload["fixture_id"],
            declared_branch=payload["declared_branch"],
            owner_exposure=_require_real(payload["owner_exposure"], "owner_exposure"),
            government_current_marginal_value=_require_real(
                payload["government_current_marginal_value"],
                "government_current_marginal_value",
            ),
            marks=tuple(MarkInput.from_json(mark) for mark in raw_marks),
            worker_consumption=(
                None
                if worker_consumption is None
                else _require_real(worker_consumption, "worker_consumption")
            ),
            description=str(payload.get("description", "")),
        )


def load_fixtures(path: Any) -> tuple[FixtureInput, ...]:
    """Parse a fixture file into an ordered, immutable tuple of fixtures."""
    import json
    from pathlib import Path

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "fixtures" not in payload:
        raise InputError("fixture file must be an object with a 'fixtures' array")
    raw = payload["fixtures"]
    if not isinstance(raw, list) or not raw:
        raise InputError("'fixtures' must be a non-empty array")
    fixtures = tuple(FixtureInput.from_json(item) for item in raw)
    ids = [fixture.fixture_id for fixture in fixtures]
    if len(set(ids)) != len(ids):
        raise InputError("fixture ids must be unique")
    return fixtures


__all__ = [
    "FIXTURE_FIELD_ORDER",
    "FORMULA_CONVENTION",
    "MARK_FIELD_ORDER",
    "BRANCH_FINITE_MAINTAINED",
    "BRANCH_LITERAL_LAISSEZ_FAIRE",
    "FINITE",
    "POSITIVE_INFINITY",
    "FixtureInput",
    "InputError",
    "MarkInput",
    "load_fixtures",
]
