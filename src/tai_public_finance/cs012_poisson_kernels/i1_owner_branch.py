"""The laissez-faire capital-owner branch at one pre-arrival state.

This module assembles the owner-side objects of CS012 block I1 and nothing else:

    J_j        = q_j/q_0 - 1                      marked total-gain jump
    k^w_j      = lambda*_j / lambda_j             world kernel
    X^K_j      = 1 + pi J_j                       owner wealth multiplier
    k^K_j      = 1 / X^K_j                        owner kernel
    a_j^+      = a_0 X^K_j                        owner wealth after mark j
    D_K(pi)    = sum_j lambda_j (k^K_j - k^w_j) J_j

with ``pi`` the root of the unmultiplied ``D_K(pi) = 0`` on the open interval where
``1 + pi J_j > 0`` for every mark.

**No government object is constructed here.** ``k^G``, ``gamma``, ``D_G``, ``D_GK``,
``mu_e`` and every successor marginal value are I2 work and are absent by construction,
not merely unreported. Where the reviewed I0 kernel record requires government fields in
order to reuse its root solver, those fields are set to NaN and are never read, never
serialized, and asserted NaN by test: a government kernel that does not exist must not be
representable as a number here.

The root and residual arithmetic are the reviewed CS012 I0 functions, reused rather than
duplicated. The dependency's own private-portfolio solver is deliberately not used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .kernels import KernelOutcome, MarkKernels
from .portfolio import (
    ExposureInterval,
    OwnerRootResult,
    exposure_interval,
    finite_root_exists,
    normalized_error,
    one_mark_analytic_root,
    owner_residual,
    owner_residual_derivative,
    owner_residual_limit,
    solve_owner_root,
)
from .statuses import FINITE_MAINTAINED_BRANCH, UNIQUE_INTERIOR_ROOT

GOVERNMENT_EXCLUDED = math.nan
"""Sentinel for the government kernel fields of a reused I0 ``MarkKernels``.

NaN rather than a plausible number precisely so that any accidental use is a loud,
propagating failure instead of a silent economic claim. It is never serialized.
"""

MIN_ABS_PAYOFF = 1.0e-3
"""Baseline payoff floor. Below this the owner root is weakly identified, which is a
different regime from the one this packet declares, so the run refuses rather than
reporting a fragile exposure."""


class OwnerBranchError(RuntimeError):
    """A structural or domain condition of the owner branch failed."""


@dataclass(frozen=True, slots=True)
class MarkPayoff:
    """One labelled mark's pre-arrival payoff data. Order is input order, never sorted."""

    mark_id: str
    lambda_physical: float
    lambda_risk_neutral: float
    successor_price: float
    payoff_jump: float
    k_world: float


@dataclass(frozen=True, slots=True)
class OwnerMark:
    """One mark's owner-side result at the solved exposure."""

    mark_id: str
    lambda_physical: float
    lambda_risk_neutral: float
    payoff_jump: float
    k_world: float
    wealth_multiplier: float
    k_owner: float
    owner_wealth_before: float
    owner_wealth_after: float
    d_owner_contribution: float


@dataclass(frozen=True, slots=True)
class OwnerBranch:
    """The complete owner-side result at one pre-arrival capital point."""

    label: str
    capital: float
    q_0: float
    marks: tuple[OwnerMark, ...]
    interval: ExposureInterval
    exposure: float
    residual_at_root: float
    derivative_at_root: float
    residual_at_zero: float
    limit_at_unbounded_end: float
    lower_boundary_distance: float
    upper_boundary_distance: float
    d_owner: float
    root_status: str
    independent_exposure_residual: float
    independent_kernel_max_error: float
    independent_d_owner_error: float
    one_mark_analytic_check: float | None

    @property
    def mark_ids(self) -> tuple[str, ...]:
        return tuple(mark.mark_id for mark in self.marks)


def build_payoffs(
    q_0: float,
    successor_prices: tuple[tuple[str, float], ...],
    intensities: dict[str, tuple[float, float]],
) -> tuple[MarkPayoff, ...]:
    """Build labelled payoffs. ``intensities[label] = (lambda_j, lambda*_j)``."""
    payoffs: list[MarkPayoff] = []
    for label, q_successor in successor_prices:
        lam, lam_star = intensities[label]
        if not math.isfinite(lam) or lam <= 0.0:
            raise OwnerBranchError(f"mark {label}: physical intensity must be finite and positive")
        if not math.isfinite(lam_star) or lam_star < 0.0:
            raise OwnerBranchError(
                f"mark {label}: risk-neutral intensity must be finite and nonnegative"
            )
        jump = q_successor / q_0 - 1.0
        payoffs.append(
            MarkPayoff(
                mark_id=label,
                lambda_physical=lam,
                lambda_risk_neutral=lam_star,
                successor_price=q_successor,
                payoff_jump=jump,
                k_world=lam_star / lam,
            )
        )
    return tuple(payoffs)


def _as_i0_outcome(label: str, payoffs: tuple[MarkPayoff, ...]) -> KernelOutcome:
    """Wrap owner-side payoffs in the reviewed I0 kernel record.

    ``k_owner`` here is the value at *zero* exposure, which is what the I0 root solver
    needs to evaluate ``D_owner`` as a function of ``pi``; it re-derives ``1/(1+pi J)``
    internally at each probe. ``k_government`` and ``gamma`` are NaN by construction.
    """
    return KernelOutcome(
        fixture_id=label,
        status=FINITE_MAINTAINED_BRANCH,
        detail=(
            "owner-side I1 branch: world and owner kernels only; no government "
            "successor value is defined at this block"
        ),
        marks=tuple(
            MarkKernels(
                mark_id=p.mark_id,
                lambda_physical=p.lambda_physical,
                lambda_risk_neutral=p.lambda_risk_neutral,
                payoff_jump=p.payoff_jump,
                owner_wealth_multiplier=1.0,
                k_world=p.k_world,
                k_owner=1.0,
                k_government=GOVERNMENT_EXCLUDED,
                gamma=GOVERNMENT_EXCLUDED,
            )
            for p in payoffs
        ),
    )


def solve_owner_branch(
    label: str,
    capital: float,
    q_0: float,
    payoffs: tuple[MarkPayoff, ...],
    owner_wealth: float,
    *,
    enforce_payoff_floor: bool = True,
) -> OwnerBranch:
    """Solve the owner exposure and assemble every owner-side quantity.

    Raises :class:`OwnerBranchError` on any structural failure -- a weak payoff, a
    non-interior root, a non-positive wealth multiplier, a non-finite quantity. None of
    these is downgraded to a flag on an otherwise-reported row.
    """
    if enforce_payoff_floor:
        for p in payoffs:
            if abs(p.payoff_jump) < MIN_ABS_PAYOFF:
                raise OwnerBranchError(
                    f"mark {p.mark_id}: |J| = {abs(p.payoff_jump)!r} is below the declared "
                    f"{MIN_ABS_PAYOFF!r} floor, so the owner exposure is weakly identified"
                )

    outcome = _as_i0_outcome(label, payoffs)
    marks_i0 = outcome.require_finite()
    root: OwnerRootResult = solve_owner_root(outcome)
    if root.status != UNIQUE_INTERIOR_ROOT:
        raise OwnerBranchError(
            f"{label}: the owner pricing equation did not yield a unique interior root "
            f"({root.status}: {root.detail})"
        )
    pi = root.require_exposure()
    interval = root.interval
    assert interval is not None

    owner_marks: list[OwnerMark] = []
    for p in payoffs:
        multiplier = 1.0 + pi * p.payoff_jump
        if not math.isfinite(multiplier) or multiplier <= 0.0:
            raise OwnerBranchError(
                f"mark {p.mark_id}: owner wealth multiplier {multiplier!r} is not strictly positive"
            )
        k_owner = 1.0 / multiplier
        contribution = p.lambda_physical * (k_owner - p.k_world) * p.payoff_jump
        owner_marks.append(
            OwnerMark(
                mark_id=p.mark_id,
                lambda_physical=p.lambda_physical,
                lambda_risk_neutral=p.lambda_risk_neutral,
                payoff_jump=p.payoff_jump,
                k_world=p.k_world,
                wealth_multiplier=multiplier,
                k_owner=k_owner,
                owner_wealth_before=owner_wealth,
                owner_wealth_after=owner_wealth * multiplier,
                d_owner_contribution=contribution,
            )
        )
    frozen = tuple(owner_marks)
    d_owner = math.fsum(m.d_owner_contribution for m in frozen)

    # --- independent reconstruction from the before/after owner-wealth ratio --------
    # k^K_j = C^{K,-}/C^{K,+}_j = a_0/a_j^+ under log utility, a genuinely different
    # expression from 1/(1+pi J_j), formed from the reported wealth levels.
    kernel_errors = [
        abs(m.k_owner - m.owner_wealth_before / m.owner_wealth_after) for m in frozen
    ]
    independent_terms = [
        m.lambda_physical
        * (m.owner_wealth_before / m.owner_wealth_after - m.k_world)
        * m.payoff_jump
        for m in frozen
    ]
    scale = tuple(m.d_owner_contribution for m in frozen) + tuple(independent_terms)
    independent_d_owner = sum(independent_terms)

    analytic_check: float | None = None
    active = [p for p in payoffs if p.payoff_jump != 0.0]
    if len(active) == 1 and active[0].lambda_risk_neutral > 0.0:
        analytic = one_mark_analytic_root(
            active[0].lambda_physical, active[0].lambda_risk_neutral, active[0].payoff_jump
        )
        analytic_check = abs(pi - analytic) / max(1.0, abs(analytic))

    for name, value in (
        ("exposure", pi),
        ("d_owner", d_owner),
        ("residual", root.residual_at_root),
        ("derivative", root.derivative_at_root),
    ):
        if value is None or not math.isfinite(value):
            raise OwnerBranchError(f"{label}: {name} is not finite on the I1 finite branch")

    return OwnerBranch(
        label=label,
        capital=capital,
        q_0=q_0,
        marks=frozen,
        interval=interval,
        exposure=pi,
        residual_at_root=root.residual_at_root,
        derivative_at_root=root.derivative_at_root,
        residual_at_zero=root.residual_at_zero,
        limit_at_unbounded_end=root.limit_at_unbounded_end,
        lower_boundary_distance=pi - interval.lower,
        upper_boundary_distance=interval.upper - pi,
        d_owner=d_owner,
        root_status=root.status,
        independent_exposure_residual=normalized_error(
            owner_residual(marks_i0, pi), 0.0, scale
        ),
        independent_kernel_max_error=max(kernel_errors, default=0.0),
        independent_d_owner_error=normalized_error(d_owner, independent_d_owner, scale),
        one_mark_analytic_check=analytic_check,
    )


def owner_branch_payload(branch: OwnerBranch) -> dict[str, Any]:
    """Serializable owner-side record. Carries no government field."""
    return {
        "label": branch.label,
        "capital": branch.capital,
        "q_0": branch.q_0,
        "root_status": branch.root_status,
        "exposure": branch.exposure,
        "exposure_interval": {
            "lower": branch.interval.lower if branch.interval.lower_is_finite else None,
            "upper": branch.interval.upper if branch.interval.upper_is_finite else None,
            "lower_is_finite": branch.interval.lower_is_finite,
            "upper_is_finite": branch.interval.upper_is_finite,
            "zero_is_interior": branch.interval.contains(0.0),
        },
        # An unbounded endpoint has no finite distance. JSON cannot carry infinity
        # portably, so it is null plus an explicit flag -- never an ``Infinity`` token
        # and never a large finite sentinel, exactly as the I0 boundary rule requires.
        "lower_boundary_distance": (
            branch.lower_boundary_distance if branch.interval.lower_is_finite else None
        ),
        "lower_boundary_is_unbounded": not branch.interval.lower_is_finite,
        "upper_boundary_distance": (
            branch.upper_boundary_distance if branch.interval.upper_is_finite else None
        ),
        "upper_boundary_is_unbounded": not branch.interval.upper_is_finite,
        "residual_at_root": branch.residual_at_root,
        "derivative_at_root": branch.derivative_at_root,
        "residual_at_zero_exposure": branch.residual_at_zero,
        "limit_at_unbounded_end": branch.limit_at_unbounded_end,
        "d_owner": branch.d_owner,
        "marks": [
            {
                "mark_id": m.mark_id,
                "lambda_physical": m.lambda_physical,
                "lambda_risk_neutral": m.lambda_risk_neutral,
                "payoff_jump": m.payoff_jump,
                "k_world": m.k_world,
                "wealth_multiplier": m.wealth_multiplier,
                "k_owner": m.k_owner,
                "owner_wealth_before": m.owner_wealth_before,
                "owner_wealth_after": m.owner_wealth_after,
                "d_owner_contribution": m.d_owner_contribution,
            }
            for m in branch.marks
        ],
        "independent": {
            "exposure_residual_normalized": branch.independent_exposure_residual,
            "kernel_max_absolute_error": branch.independent_kernel_max_error,
            "d_owner_normalized_error": branch.independent_d_owner_error,
            "one_mark_analytic_relative_error": branch.one_mark_analytic_check,
            "route": "owner kernels rebuilt as a_0/a_j^+ from reported wealth levels",
        },
    }


__all__ = [
    "GOVERNMENT_EXCLUDED",
    "MIN_ABS_PAYOFF",
    "MarkPayoff",
    "OwnerBranch",
    "OwnerBranchError",
    "OwnerMark",
    "build_payoffs",
    "owner_branch_payload",
    "solve_owner_branch",
]
