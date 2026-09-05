"""An in-package independent reconstruction route for the I0 identities.

This module deliberately does **not** import ``kernels``, ``portfolio``, or
``projection``. It re-derives every kernel, contribution, and sum from the direct
serialized fields by a different arithmetic route:

* the owner kernel is built as the consumption ratio ``C^{K,-}/C^{K,+}``, taking
  the supplied ``owner_wealth_before``/``owner_wealth_after`` pair when present
  and otherwise the wealth multiplier, rather than as a reciprocal;
* the residual sums are formed in expanded rather than differenced shape,
  ``sum_j lambda_j k_a[j] J_j - sum_j lambda_j k_b[j] J_j``; and
* accumulation is plain left-to-right ``sum`` rather than ``math.fsum``.

Agreement between the two routes is therefore informative about the algebra and
about FP conditioning, not tautological. It is a second route, not a substitute
for ``tools/check_cs012_i0_report.py``, which reconstructs the serialized report
from outside the package entirely.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .inputs import FixtureInput
from .statuses import BRANCH_LITERAL_LAISSEZ_FAIRE


@dataclass(frozen=True, slots=True)
class IndependentMark:
    mark_id: str
    k_world: float
    k_owner: float
    k_government: float
    gamma: float
    term_owner: float
    term_government: float
    term_government_owner: float
    term_relative: float


@dataclass(frozen=True, slots=True)
class IndependentReconstruction:
    """Independent kernel/residual/projection values for one finite fixture."""

    fixture_id: str
    marks: tuple[IndependentMark, ...]
    d_owner: float
    d_government: float
    d_government_owner: float
    d_relative: float
    projection_denominator: float | None
    projection_numerator: float | None
    projection_alpha: float | None
    orthogonal: tuple[float, ...]
    weighted_inner_product_orthogonal_payoff: float | None


class NotReconstructible(ValueError):
    """The fixture is a declared boundary or otherwise outside the finite branch."""


def reconstruct(fixture: FixtureInput) -> IndependentReconstruction:
    """Recompute the finite-branch identities by the alternative route."""
    if fixture.declared_branch == BRANCH_LITERAL_LAISSEZ_FAIRE:
        raise NotReconstructible(
            "a literal laissez-faire boundary fixture carries no finite arithmetic"
        )

    exposure = fixture.owner_exposure
    mu_current = fixture.government_current_marginal_value
    marks: list[IndependentMark] = []
    for mark in fixture.marks:
        successor = mark.government_successor_marginal_value
        if not successor.is_finite:
            raise NotReconstructible(
                f"mark {mark.mark_id}: successor marginal value is {successor.kind}"
            )
        if mark.owner_wealth_before is not None and mark.owner_wealth_after is not None:
            consumption_before = mark.owner_wealth_before
            consumption_after = mark.owner_wealth_after
        else:
            consumption_before = 1.0
            consumption_after = 1.0 + exposure * mark.payoff_jump
        if consumption_after <= 0.0 or consumption_before <= 0.0:
            raise NotReconstructible(
                f"mark {mark.mark_id}: non-positive owner consumption ratio"
            )
        k_owner = consumption_before / consumption_after
        k_world = mark.lambda_risk_neutral / mark.lambda_physical
        k_government = successor.require_finite() / mu_current
        gamma = k_government / k_owner
        weight = mark.lambda_physical * mark.payoff_jump
        marks.append(
            IndependentMark(
                mark_id=mark.mark_id,
                k_world=k_world,
                k_owner=k_owner,
                k_government=k_government,
                gamma=gamma,
                term_owner=weight * k_owner - weight * k_world,
                term_government=weight * k_government - weight * k_world,
                term_government_owner=weight * k_government - weight * k_owner,
                term_relative=weight * k_owner * gamma - weight * k_owner,
            )
        )

    frozen = tuple(marks)
    d_owner = sum(mark.term_owner for mark in frozen)
    d_government = sum(mark.term_government for mark in frozen)
    d_government_owner = sum(mark.term_government_owner for mark in frozen)
    d_relative = sum(mark.term_relative for mark in frozen)

    weights = [mark.lambda_physical for mark in fixture.marks]
    payoffs = [mark.payoff_jump for mark in fixture.marks]
    gaps = [mark.k_government - mark.k_world for mark in frozen]
    denominator = sum(w * j * j for w, j in zip(weights, payoffs, strict=True))
    if denominator == 0.0:
        return IndependentReconstruction(
            fixture_id=fixture.fixture_id,
            marks=frozen,
            d_owner=d_owner,
            d_government=d_government,
            d_government_owner=d_government_owner,
            d_relative=d_relative,
            projection_denominator=0.0,
            projection_numerator=None,
            projection_alpha=None,
            orthogonal=(),
            weighted_inner_product_orthogonal_payoff=None,
        )
    numerator = sum(
        w * g * j for w, g, j in zip(weights, gaps, payoffs, strict=True)
    )
    alpha = numerator / denominator
    orthogonal = tuple(g - alpha * j for g, j in zip(gaps, payoffs, strict=True))
    inner = sum(
        w * o * j for w, o, j in zip(weights, orthogonal, payoffs, strict=True)
    )
    return IndependentReconstruction(
        fixture_id=fixture.fixture_id,
        marks=frozen,
        d_owner=d_owner,
        d_government=d_government,
        d_government_owner=d_government_owner,
        d_relative=d_relative,
        projection_denominator=denominator,
        projection_numerator=numerator,
        projection_alpha=alpha,
        orthogonal=orthogonal,
        weighted_inner_product_orthogonal_payoff=inner,
    )


def owner_residual_independent(fixture: FixtureInput, exposure: float) -> float:
    """``D_owner`` at an arbitrary exposure, expanded-form and plain-summed."""
    total = 0.0
    for mark in fixture.marks:
        multiplier = 1.0 + exposure * mark.payoff_jump
        if multiplier <= 0.0 or not math.isfinite(multiplier):
            raise NotReconstructible("exposure outside the admissible interval")
        weight = mark.lambda_physical * mark.payoff_jump
        total += weight / multiplier - weight * (
            mark.lambda_risk_neutral / mark.lambda_physical
        )
    return total


__all__ = [
    "IndependentMark",
    "IndependentReconstruction",
    "NotReconstructible",
    "owner_residual_independent",
    "reconstruct",
]
