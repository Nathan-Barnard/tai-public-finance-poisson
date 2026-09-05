"""Owner exposure interval, owner portfolio-pricing root, and the exact
government/owner residual decomposition.

Residuals, frozen by CS012 v0.1 "I0 -- identity and portfolio-pricing core":

    D_owner            = sum_j lambda_j * (k_owner[j]      - k_world[j]) * J_j
    D_government       = sum_j lambda_j * (k_government[j] - k_world[j]) * J_j
    D_government_owner = sum_j lambda_j * (k_government[j] - k_owner[j]) * J_j
    D_relative         = sum_j lambda_j * k_owner[j] * (gamma[j] - 1)    * J_j

with the exact identities ``D_government = D_owner + D_government_owner`` and,
whenever every kernel and ratio is finite, ``D_government_owner = D_relative``.
``D_owner`` is never set to zero by construction: it is evaluated at whatever
``owner_exposure`` the fixture declares.

Sign convention when ``D_owner = 0``: ``D_government`` is the government's
normalized marginal value of additional installed equity. Positive means more
equity raises the local Hamiltonian under this payoff orientation; negative means
less equity, or a short position where admissible; an uncertainty interval that
crosses zero is indistinguishable. This is a marginal direction at a named state,
never a position size and never an optimum.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.optimize import brentq

from .kernels import KernelOutcome, MarkKernels
from .statuses import (
    NO_INTERIOR_ROOT_BOUNDARY_LIMIT,
    UNIQUE_INTERIOR_ROOT,
    ZERO_PAYOFF_UNIDENTIFIED,
)

ROOT_XTOL = 1.0e-15
ROOT_RTOL = 8.881784197001252e-16  # 4 * DBL_EPSILON, brentq's documented floor
BRACKET_STEPS = 200
"""Cap on geometric bracket-expansion steps toward an interval endpoint."""


def normalized_error(lhs: float, rhs: float, terms: tuple[float, ...]) -> float:
    """``abs(lhs-rhs) / max(1, sum(abs(term)))`` -- the tolerance policy CS012 v0.1
    fixes for every sum identity in this package."""
    scale = max(1.0, math.fsum(abs(term) for term in terms))
    return abs(lhs - rhs) / scale


@dataclass(frozen=True, slots=True)
class ResidualTerm:
    """One mark's signed contribution to each of the four residual sums."""

    mark_id: str
    owner: float
    government: float
    government_owner: float
    relative: float


@dataclass(frozen=True, slots=True)
class Decomposition:
    """The four residual sums, their term-level contributions, and both identity
    discrepancies. ``relative_identity_applies`` is false only when some kernel or
    ratio is non-finite, in which case the second identity is not asserted."""

    fixture_id: str
    terms: tuple[ResidualTerm, ...]
    d_owner: float
    d_government: float
    d_government_owner: float
    d_relative: float
    decomposition_error: float
    relative_identity_error: float
    relative_identity_applies: bool


def decompose(outcome: KernelOutcome) -> Decomposition:
    """Evaluate the four residuals term by term. Requires the finite branch."""
    marks = outcome.require_finite()
    terms = tuple(
        ResidualTerm(
            mark_id=mark.mark_id,
            owner=mark.lambda_physical * (mark.k_owner - mark.k_world) * mark.payoff_jump,
            government=mark.lambda_physical
            * (mark.k_government - mark.k_world)
            * mark.payoff_jump,
            government_owner=mark.lambda_physical
            * (mark.k_government - mark.k_owner)
            * mark.payoff_jump,
            relative=mark.lambda_physical
            * mark.k_owner
            * (mark.gamma - 1.0)
            * mark.payoff_jump,
        )
        for mark in marks
    )
    d_owner = math.fsum(term.owner for term in terms)
    d_government = math.fsum(term.government for term in terms)
    d_government_owner = math.fsum(term.government_owner for term in terms)
    d_relative = math.fsum(term.relative for term in terms)

    decomposition_terms = tuple(
        value
        for term in terms
        for value in (term.owner, term.government, term.government_owner)
    )
    relative_terms = tuple(
        value for term in terms for value in (term.government_owner, term.relative)
    )
    return Decomposition(
        fixture_id=outcome.fixture_id,
        terms=terms,
        d_owner=d_owner,
        d_government=d_government,
        d_government_owner=d_government_owner,
        d_relative=d_relative,
        decomposition_error=normalized_error(
            d_government, d_owner + d_government_owner, decomposition_terms
        ),
        relative_identity_error=normalized_error(
            d_government_owner, d_relative, relative_terms
        ),
        # Every kernel reaching this point is finite by construction of
        # ``require_finite``; the flag records that the precondition was checked
        # rather than assumed, and stays false for any boundary outcome.
        relative_identity_applies=True,
    )


@dataclass(frozen=True, slots=True)
class ExposureInterval:
    """The open admissible owner-exposure interval, the intersection over marks of
    ``1 + pi*J_j > 0``. Marks with ``J_j = 0`` impose no constraint. Because
    ``-1/J_j`` is negative for ``J_j > 0`` and positive for ``J_j < 0``, ``pi = 0``
    is always strictly inside a correctly constructed interval."""

    lower: float  # -inf when unbounded below
    upper: float  # +inf when unbounded above
    lower_is_finite: bool
    upper_is_finite: bool

    def contains(self, exposure: float) -> bool:
        return self.lower < exposure < self.upper

    def distance_to_boundary(self, exposure: float) -> float:
        """Distance to the nearest *finite* wealth boundary; ``+inf`` if both
        endpoints are unbounded."""
        gaps = []
        if self.lower_is_finite:
            gaps.append(exposure - self.lower)
        if self.upper_is_finite:
            gaps.append(self.upper - exposure)
        return min(gaps) if gaps else math.inf


def exposure_interval(payoff_vector: tuple[float, ...]) -> ExposureInterval:
    """Build the open interval for a nonzero payoff vector.

    Raises for an all-zero vector: that case has no identifying portfolio
    equation and is reported as ``zero_payoff_unidentified``, not as an interval.
    """
    if all(jump == 0.0 for jump in payoff_vector):
        raise ValueError("a zero payoff vector defines no exposure constraint")
    lower = -math.inf
    upper = math.inf
    for jump in payoff_vector:
        if jump > 0.0:
            lower = max(lower, -1.0 / jump)
        elif jump < 0.0:
            upper = min(upper, -1.0 / jump)
    return ExposureInterval(
        lower=lower,
        upper=upper,
        lower_is_finite=math.isfinite(lower),
        upper_is_finite=math.isfinite(upper),
    )


def owner_residual(marks: tuple[MarkKernels, ...], exposure: float) -> float:
    """``D_owner(pi) = sum_j lambda_j * (1/(1+pi*J_j) - k_world[j]) * J_j``.

    Evaluated directly from the exposure, so it is a genuine function of ``pi``
    rather than a re-read of the fixture's own ``owner_exposure``.
    """
    return math.fsum(
        mark.lambda_physical
        * (1.0 / (1.0 + exposure * mark.payoff_jump) - mark.k_world)
        * mark.payoff_jump
        for mark in marks
    )


def owner_residual_derivative(marks: tuple[MarkKernels, ...], exposure: float) -> float:
    """``dD_owner/dpi = -sum_j lambda_j * J_j^2 / (1 + pi*J_j)^2``.

    Strictly negative whenever the payoff vector is nonzero, which is why a
    sign-changing bracket can contain at most one root.
    """
    return -math.fsum(
        mark.lambda_physical
        * mark.payoff_jump**2
        / (1.0 + exposure * mark.payoff_jump) ** 2
        for mark in marks
    )


def owner_residual_limit(marks: tuple[MarkKernels, ...]) -> float:
    """The common limit of ``D_owner`` at an unbounded endpoint.

    As ``pi -> +-inf`` each ``J_j != 0`` term has ``J_j/(1+pi*J_j) -> 0``, leaving
    ``-sum_{j: J_j != 0} lambda_risk_neutral[j] * J_j``. Terms with ``J_j = 0``
    contribute zero at every exposure. This is evaluated analytically so that no
    pole is ever approached numerically.
    """
    return -math.fsum(
        mark.lambda_risk_neutral * mark.payoff_jump
        for mark in marks
        if mark.payoff_jump != 0.0
    )


@dataclass(frozen=True, slots=True)
class OwnerRootResult:
    """Tagged owner portfolio-pricing result.

    ``exposure`` is populated only for ``unique_interior_root``; every other status
    leaves it ``None`` *and* says why in ``status``/``detail``, so no caller can
    mistake an absent root for a root at zero.
    """

    fixture_id: str
    status: str
    detail: str
    interval: ExposureInterval | None = None
    exposure: float | None = None
    residual_at_root: float | None = None
    derivative_at_root: float | None = None
    boundary_margin: float | None = None
    residual_at_zero: float | None = None
    limit_at_unbounded_end: float | None = None

    def require_exposure(self) -> float:
        if self.status != UNIQUE_INTERIOR_ROOT or self.exposure is None:
            raise RuntimeError(f"no interior owner root: {self.status}: {self.detail}")
        return self.exposure


def _approach(start: float, endpoint: float, endpoint_is_finite: bool, step: int) -> float:
    """The ``step``-th probe between ``start`` and an interval endpoint, always
    strictly inside the open interval so that no pole is evaluated."""
    if endpoint_is_finite:
        return endpoint - (endpoint - start) * 0.5**step
    return start + math.copysign(2.0**step, endpoint)


def solve_owner_root(outcome: KernelOutcome) -> OwnerRootResult:
    """Solve ``D_owner(pi) = 0`` on the open admissible exposure interval.

    Uses the repository's pinned SciPy bracketing routine (``scipy.optimize.brentq``)
    on a bracket found by geometric approach to an endpoint; it never divides
    through a selected ``J_j`` and never evaluates a pole.
    """
    marks = outcome.require_finite()
    payoff_vector = tuple(mark.payoff_jump for mark in marks)

    if all(jump == 0.0 for jump in payoff_vector):
        return OwnerRootResult(
            outcome.fixture_id,
            ZERO_PAYOFF_UNIDENTIFIED,
            "every marked payoff component is exactly zero, so the owner pricing "
            "equation holds identically and identifies no exposure; no default "
            "exposure is chosen",
        )

    interval = exposure_interval(payoff_vector)
    at_zero = owner_residual(marks, 0.0)
    limit = owner_residual_limit(marks)

    if at_zero == 0.0:
        return OwnerRootResult(
            outcome.fixture_id,
            UNIQUE_INTERIOR_ROOT,
            "the owner residual vanishes exactly at zero exposure",
            interval=interval,
            exposure=0.0,
            residual_at_root=0.0,
            derivative_at_root=owner_residual_derivative(marks, 0.0),
            boundary_margin=interval.distance_to_boundary(0.0),
            residual_at_zero=at_zero,
            limit_at_unbounded_end=limit,
        )

    # D_owner is strictly decreasing, so a positive value at zero puts the root to
    # the right and a negative value puts it to the left.
    if at_zero > 0.0:
        endpoint, endpoint_is_finite = interval.upper, interval.upper_is_finite
    else:
        endpoint, endpoint_is_finite = interval.lower, interval.lower_is_finite

    probe = 0.0
    value = at_zero
    bracket: tuple[float, float] | None = None
    for step in range(1, BRACKET_STEPS + 1):
        candidate = _approach(0.0, endpoint, endpoint_is_finite, step)
        if not math.isfinite(candidate) or not interval.contains(candidate):
            break
        candidate_value = owner_residual(marks, candidate)
        if not math.isfinite(candidate_value):
            break
        if candidate_value == 0.0:
            bracket = (min(probe, candidate), max(probe, candidate))
            break
        if (candidate_value > 0.0) != (at_zero > 0.0):
            bracket = (min(probe, candidate), max(probe, candidate))
            break
        probe, value = candidate, candidate_value

    if bracket is None:
        return OwnerRootResult(
            outcome.fixture_id,
            NO_INTERIOR_ROOT_BOUNDARY_LIMIT,
            "the owner residual keeps one sign across the whole open admissible "
            f"interval; residual at zero exposure {at_zero!r}, analytic limit at "
            f"the unbounded end {limit!r}. The root is approached only in the "
            "boundary limit, so no finite interior exposure is reported",
            interval=interval,
            residual_at_zero=at_zero,
            limit_at_unbounded_end=limit,
        )

    root = float(
        brentq(
            lambda pi: owner_residual(marks, pi),
            bracket[0],
            bracket[1],
            xtol=ROOT_XTOL,
            rtol=ROOT_RTOL,
            maxiter=200,
        )
    )
    return OwnerRootResult(
        outcome.fixture_id,
        UNIQUE_INTERIOR_ROOT,
        "a finite interior sign change was bracketed inside the open admissible "
        "interval; the residual is strictly decreasing there, so the root is unique",
        interval=interval,
        exposure=root,
        residual_at_root=owner_residual(marks, root),
        derivative_at_root=owner_residual_derivative(marks, root),
        boundary_margin=interval.distance_to_boundary(root),
        residual_at_zero=at_zero,
        limit_at_unbounded_end=limit,
    )


def one_mark_analytic_root(lambda_physical: float, lambda_risk_neutral: float,
                           payoff_jump: float) -> float:
    """``pi = (lambda/lambda_star - 1)/J`` -- the exact one-mark owner exposure
    (R.2 of the single-AK note). Used as an independent benchmark, never as the
    production route."""
    if payoff_jump == 0.0 or lambda_risk_neutral <= 0.0:
        raise ValueError("the analytic one-mark root needs J != 0 and lambda_star > 0")
    return (lambda_physical / lambda_risk_neutral - 1.0) / payoff_jump


__all__ = [
    "BRACKET_STEPS",
    "Decomposition",
    "ExposureInterval",
    "OwnerRootResult",
    "ResidualTerm",
    "decompose",
    "exposure_interval",
    "normalized_error",
    "one_mark_analytic_root",
    "owner_residual",
    "owner_residual_derivative",
    "owner_residual_limit",
    "solve_owner_root",
]
