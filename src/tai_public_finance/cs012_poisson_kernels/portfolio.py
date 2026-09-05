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
import sys
from dataclasses import dataclass

from scipy.optimize import brentq

from .kernels import KernelOutcome, MarkKernels
from .statuses import (
    FINITE_ROOT_NOT_REPRESENTABLE,
    NO_INTERIOR_ROOT_BOUNDARY_LIMIT,
    UNIQUE_INTERIOR_ROOT,
    ZERO_PAYOFF_UNIDENTIFIED,
)

ROOT_XTOL = 1.0e-15
ROOT_RTOL = 8.881784197001252e-16  # 4 * DBL_EPSILON, brentq's documented floor

FINITE_APPROACH_STEPS = 1200
"""Halvings of the gap to a *finite* interval endpoint. Each step halves the gap, so
after about 1080 steps the probe has reached the endpoint in FP64 and the loop is
exhausted rather than truncated; the cap only bounds the loop.

This is not an existence criterion. At a finite endpoint some ``1 + pi*J_j`` tends to
zero from above and the residual diverges, so a sign change is always found long
before exhaustion whenever the analytic test says a root exists."""

DOUBLING_STEPS = 1024
"""Doublings from unit magnitude toward an *unbounded* interval endpoint: 2**0 up to
2**1023, then one final probe at the largest finite double. That enumerates every
binade FP64 has, so exhausting it proves the root is unrepresentable rather than
absent -- which is the distinction the original 200-doubling cap could not make."""


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


def finite_root_exists(
    marks: tuple[MarkKernels, ...], interval: ExposureInterval
) -> tuple[bool, float, float]:
    """Decide analytically whether a finite interior owner root exists.

    Returns ``(exists, residual_at_zero, limit)``. No search is involved, so the
    answer cannot depend on how many probes some loop happens to take.

    ``D_owner`` is strictly decreasing on the open admissible interval, and
    ``pi = 0`` is always interior, so the sign of ``D_owner(0)`` fixes the side the
    root must lie on. Two cases then settle existence exactly:

    * The endpoint on that side is **finite**. Some ``1 + pi*J_j`` then tends to zero
      from above, the corresponding term ``lambda_j*J_j/(1+pi*J_j)`` diverges with the
      sign of ``J_j``, and ``D_owner`` runs to ``-inf`` at a finite upper endpoint or
      ``+inf`` at a finite lower endpoint. A root always exists.
    * The endpoint on that side is **unbounded**. Every ``J_j != 0`` term satisfies
      ``J_j/(1+pi*J_j) -> 0``, so ``D_owner`` tends to the finite analytic limit
      ``L = -sum_{j: J_j != 0} lambda_risk_neutral[j]*J_j``. A strictly decreasing
      function crosses zero on that side exactly when ``L`` lies strictly beyond zero
      in the direction of travel: ``L < 0`` going right, ``L > 0`` going left.

    An interval is unbounded on at most one side, because an unbounded side requires
    every nonzero payoff component to share a sign, which makes the other side finite.
    ``L == 0`` -- the ``lambda_risk_neutral = 0`` limiting fixture -- is correctly a
    boundary-only case: the residual decreases toward zero and never reaches it.
    """
    at_zero = owner_residual(marks, 0.0)
    limit = owner_residual_limit(marks)
    if at_zero == 0.0:
        return True, at_zero, limit
    if at_zero > 0.0:
        if interval.upper_is_finite:
            return True, at_zero, limit
        return limit < 0.0, at_zero, limit
    if interval.lower_is_finite:
        return True, at_zero, limit
    return limit > 0.0, at_zero, limit


def _probe_toward_finite_endpoint(endpoint: float, step: int) -> float:
    """Halve the gap from zero exposure to a finite endpoint ``step`` times."""
    return endpoint - endpoint * 0.5**step


def _probe_toward_unbounded_endpoint(sign: float, step: int) -> float:
    """Walk out the FP64 binades toward an unbounded endpoint.

    ``step`` in ``0..1022`` gives ``+-2**step``; the final step gives the largest
    finite double, so the sequence covers every representable magnitude.
    """
    if step >= DOUBLING_STEPS - 1:
        return math.copysign(sys.float_info.max, sign)
    return math.copysign(2.0**step, sign)


def solve_owner_root(outcome: KernelOutcome) -> OwnerRootResult:
    """Solve ``D_owner(pi) = 0`` on the open admissible exposure interval.

    Existence is decided analytically by ``finite_root_exists`` before any search
    runs, so a root that merely lies far out is never mistaken for a root that does
    not exist. Only once existence is established does the routine bracket, using
    the repository's pinned SciPy bracketing routine (``scipy.optimize.brentq``) on
    a bracket found by walking strictly inside the interval. It never divides
    through a selected ``J_j`` and never evaluates a pole.

    If existence holds but the whole representable FP64 range is exhausted without a
    sign change, the root is beyond ``sys.float_info.max`` and the result is
    ``finite_root_not_representable`` -- explicitly a statement about the arithmetic,
    never ``no_interior_root_boundary_limit``.
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
    exists, at_zero, limit = finite_root_exists(marks, interval)

    if not exists:
        return OwnerRootResult(
            outcome.fixture_id,
            NO_INTERIOR_ROOT_BOUNDARY_LIMIT,
            "the owner residual is strictly decreasing and its analytic limit at the "
            f"unbounded end, {limit!r}, does not lie beyond zero in the direction of "
            f"travel from the residual at zero exposure, {at_zero!r}. The residual "
            "therefore keeps one sign on the whole open admissible interval and "
            "approaches its limit only at the boundary; no finite interior exposure "
            "exists. This is an analytic conclusion, not a failed search",
            interval=interval,
            residual_at_zero=at_zero,
            limit_at_unbounded_end=limit,
        )

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

    # Strictly decreasing: a positive residual at zero puts the root to the right,
    # a negative one puts it to the left.
    going_right = at_zero > 0.0
    if going_right:
        endpoint, endpoint_is_finite = interval.upper, interval.upper_is_finite
    else:
        endpoint, endpoint_is_finite = interval.lower, interval.lower_is_finite

    if endpoint_is_finite:
        steps = FINITE_APPROACH_STEPS
        def probe(step: int) -> float:
            return _probe_toward_finite_endpoint(endpoint, step)
    else:
        sign = 1.0 if going_right else -1.0
        steps = DOUBLING_STEPS
        def probe(step: int) -> float:
            return _probe_toward_unbounded_endpoint(sign, step)

    near = 0.0
    bracket: tuple[float, float] | None = None
    for step in range(steps):
        candidate = probe(step)
        if not math.isfinite(candidate) or not interval.contains(candidate):
            break
        candidate_value = owner_residual(marks, candidate)
        if not math.isfinite(candidate_value):
            break
        if candidate_value == 0.0 or (candidate_value > 0.0) != going_right:
            bracket = (min(near, candidate), max(near, candidate))
            break
        near = candidate

    if bracket is None:
        return OwnerRootResult(
            outcome.fixture_id,
            FINITE_ROOT_NOT_REPRESENTABLE,
            "strict monotonicity and the analytic limit "
            f"{limit!r} prove that a finite interior root exists beyond a residual of "
            f"{at_zero!r} at zero exposure, but every representable FP64 magnitude in "
            "that direction was exhausted without a sign change, so the root lies "
            "outside double precision and no bracket can be formed. This is a "
            "numerical refusal, not an absence of a root",
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
    "DOUBLING_STEPS",
    "FINITE_APPROACH_STEPS",
    "Decomposition",
    "ExposureInterval",
    "OwnerRootResult",
    "ResidualTerm",
    "decompose",
    "exposure_interval",
    "finite_root_exists",
    "normalized_error",
    "one_mark_analytic_root",
    "owner_residual",
    "owner_residual_derivative",
    "owner_residual_limit",
    "solve_owner_root",
]
