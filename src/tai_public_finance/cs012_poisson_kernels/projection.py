"""Intensity-weighted marketed projection, orthogonal fiscal gap, and the exact
safe-account payoff rank.

CS012 v0.1, I0: for ``g_j = k_government[j] - k_world[j]``,

    denominator     = sum_j lambda_j * J_j^2
    numerator       = sum_j lambda_j * g_j * J_j
    alpha           = numerator / denominator
    g_parallel[j]   = alpha * J_j
    g_orthogonal[j] = g_j - g_parallel[j]

The market prices the component along ``J``; the unspanned fiscal valuation is
what remains. A zero or numerically unresolved weighted payoff norm is refused --
the payoff vector is never normalized into a direction.

The safe money-market account is the rolled account of the safe-saving note,
section 2: its marked payoff vector is identically zero, so the risky-exposure
matrix ``[[0,...,0],[J_1,...,J_n]]`` has the same rank as ``J`` alone. A long
duration bond is a different instrument and is out of scope here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .kernels import KernelOutcome
from .statuses import (
    PROJECTION_RESOLVED,
    UNRESOLVED_PAYOFF_NORM_REFUSED,
    ZERO_PAYOFF_NORM_REFUSED,
)

NORM_RESOLUTION_FLOOR = 1.0e-12
"""A weighted payoff norm below this fraction of the largest single weighted term
that formed it is treated as numerically unresolved and refused. It guards the
catastrophic-cancellation case, which exact-zero testing alone would miss."""


@dataclass(frozen=True, slots=True)
class ProjectionComponent:
    """One mark's fiscal gap and its marketed/orthogonal split."""

    mark_id: str
    payoff_jump: float
    lambda_physical: float
    gap: float
    parallel: float
    orthogonal: float


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    """Tagged projection result. Numeric fields are populated only when
    ``status == projection_resolved``."""

    fixture_id: str
    status: str
    detail: str
    components: tuple[ProjectionComponent, ...] = ()
    denominator: float | None = None
    numerator: float | None = None
    alpha: float | None = None
    weighted_norm_gap: float | None = None
    weighted_norm_parallel: float | None = None
    weighted_norm_orthogonal: float | None = None
    weighted_inner_product_orthogonal_payoff: float | None = None
    orthogonality_error: float | None = None

    def require_alpha(self) -> float:
        if self.status != PROJECTION_RESOLVED or self.alpha is None:
            raise RuntimeError(f"no projection: {self.status}: {self.detail}")
        return self.alpha


def _weighted_norm(weights: tuple[float, ...], values: tuple[float, ...]) -> float:
    return math.sqrt(
        math.fsum(weight * value**2 for weight, value in zip(weights, values, strict=True))
    )


def project_fiscal_gap(outcome: KernelOutcome) -> ProjectionResult:
    """Project the fiscal gap onto the payoff vector under the physical-intensity
    inner product. Requires the finite branch."""
    marks = outcome.require_finite()
    weights = tuple(mark.lambda_physical for mark in marks)
    payoffs = tuple(mark.payoff_jump for mark in marks)
    gaps = tuple(mark.k_government - mark.k_world for mark in marks)

    weighted_squares = tuple(
        weight * payoff**2 for weight, payoff in zip(weights, payoffs, strict=True)
    )
    denominator = math.fsum(weighted_squares)
    if denominator == 0.0:
        return ProjectionResult(
            outcome.fixture_id,
            ZERO_PAYOFF_NORM_REFUSED,
            "the physical-intensity-weighted payoff norm is exactly zero; there is "
            "no payoff direction to project on and the vector is not normalized",
            denominator=0.0,
        )
    largest = max(weighted_squares)
    if denominator < NORM_RESOLUTION_FLOOR * largest:
        return ProjectionResult(
            outcome.fixture_id,
            UNRESOLVED_PAYOFF_NORM_REFUSED,
            f"the weighted payoff norm {denominator!r} is not resolvable against its "
            f"largest forming term {largest!r}; refused rather than reported",
            denominator=denominator,
        )

    numerator = math.fsum(
        weight * gap * payoff
        for weight, gap, payoff in zip(weights, gaps, payoffs, strict=True)
    )
    alpha = numerator / denominator
    parallel = tuple(alpha * payoff for payoff in payoffs)
    orthogonal = tuple(
        gap - par for gap, par in zip(gaps, parallel, strict=True)
    )
    inner = math.fsum(
        weight * orth * payoff
        for weight, orth, payoff in zip(weights, orthogonal, payoffs, strict=True)
    )
    inner_terms = tuple(
        weight * orth * payoff
        for weight, orth, payoff in zip(weights, orthogonal, payoffs, strict=True)
    )
    return ProjectionResult(
        outcome.fixture_id,
        PROJECTION_RESOLVED,
        "the fiscal gap was split into its marketed projection on the payoff "
        "vector and an orthogonal residual under the physical-intensity inner product",
        components=tuple(
            ProjectionComponent(
                mark_id=mark.mark_id,
                payoff_jump=mark.payoff_jump,
                lambda_physical=mark.lambda_physical,
                gap=gap,
                parallel=par,
                orthogonal=orth,
            )
            for mark, gap, par, orth in zip(marks, gaps, parallel, orthogonal, strict=True)
        ),
        denominator=denominator,
        numerator=numerator,
        alpha=alpha,
        weighted_norm_gap=_weighted_norm(weights, gaps),
        weighted_norm_parallel=_weighted_norm(weights, parallel),
        weighted_norm_orthogonal=_weighted_norm(weights, orthogonal),
        weighted_inner_product_orthogonal_payoff=inner,
        orthogonality_error=abs(inner)
        / max(1.0, math.fsum(abs(term) for term in inner_terms)),
    )


@dataclass(frozen=True, slots=True)
class SafeAccountRank:
    """The exact payoff-rank statement for the rolled safe money-market account.

    Rank is decided by exact zero-testing of the payoff components, not by a
    floating-point rank decomposition: an exact zero jump is a change in rank,
    not poor conditioning.
    """

    fixture_id: str
    safe_payoff_vector: tuple[float, ...]
    risky_payoff_vector: tuple[float, ...]
    rank_risky: int
    rank_with_safe_account: int
    rank_increase: int
    safe_account_has_zero_marked_payoff: bool
    detail: str


def safe_account_rank(outcome: KernelOutcome) -> SafeAccountRank:
    """Report that adding the safe account leaves the risky payoff rank unchanged."""
    if outcome.is_finite_branch:
        marks = outcome.marks
        payoffs = tuple(mark.payoff_jump for mark in marks)
    else:
        payoffs = tuple(mark.payoff_jump for mark in outcome.boundary_marks)
    safe = tuple(0.0 for _ in payoffs)
    rank_risky = 1 if any(jump != 0.0 for jump in payoffs) else 0
    return SafeAccountRank(
        fixture_id=outcome.fixture_id,
        safe_payoff_vector=safe,
        risky_payoff_vector=payoffs,
        rank_risky=rank_risky,
        # The safe row is identically zero, so it adds no independent row.
        rank_with_safe_account=rank_risky,
        rank_increase=0,
        safe_account_has_zero_marked_payoff=True,
        detail="the rolled money-market account has an identically zero marked "
        "payoff vector, so it adds no independent row to the risky-exposure "
        "matrix and cannot increase risky span; it is not sent through the "
        "nonzero-payoff projection routine",
    )


__all__ = [
    "NORM_RESOLUTION_FLOOR",
    "ProjectionComponent",
    "ProjectionResult",
    "SafeAccountRank",
    "project_fiscal_gap",
    "safe_account_rank",
]
