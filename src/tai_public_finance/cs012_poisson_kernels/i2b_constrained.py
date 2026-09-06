"""CS012 I2b: the transfer-constrained absorbing successor.

The maintained reference is the zero-tax, zero-equity laissez-faire continuation:
``tau = 0``, ``Theta = 0``, the selected zero-tax productive path retained, workers
consuming wages plus nonnegative transfers, and the government optimizing only the
*timing* of transfers and safe saving subject to ``T(t) >= 0``. It is not the
unconstrained comprehensive-wealth relaxation and not an unrestricted Ramsey successor.

Following the canonical derivation (equations 12.2-12.10 and 16.8-16.15 of
``research-notes/revealed-no-partial-full-automation-analytic-derivations.md``):

    X_j       = F + H_j(K_0) - q_j(K_0) K_0
    C_t       = max{ W_j(K_t), A e^{(r_j - rho) t} }                       (16.15)
    T_t       = C_t - W_j(K_t) >= 0
    F         = int_0^inf e^{-r_j t} T_t dt                                 budget
    V_{j,e}   = 1/A                                    where differentiable

The unrestricted annuity ``C = rho X`` and ``V = 1/(rho X)`` is valid only when the
transfer-slack threshold (12.6)-(12.7) is met globally:

    underline_X = sup_{t>=0} e^{-(r_j - rho) t} W_j(K_t) / rho              (12.6)

which by (16.8) is finite **iff** ``r_j >= rho``, and at ``r_j = rho`` equals
``max{W_j(K_0), W_j(Kbar_j)}/rho``                                          (16.9).

Below that threshold the unrestricted value is an *upper relaxation only* and must not
be reported as the constrained successor value. That is precisely the defect in the
historical I2a partial rows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from .extended import POSITIVE_INFINITE, ExtendedReal

GLOBALLY_INTERIOR = "globally_transfer_interior"
BOUNDARY_ACTIVE = "transfer_boundary_active"
WAGE_ONLY = "transfer_identically_zero"
UNSUPPORTED_GEOMETRY = "unsupported_active_set_geometry"

ACTIVE_SET_STATUSES = (GLOBALLY_INTERIOR, BOUNDARY_ACTIVE, WAGE_ONLY, UNSUPPORTED_GEOMETRY)

IVP_RTOL = 1.0e-13
IVP_ATOL = 1.0e-15
ROOT_XTOL = 1.0e-14
ROOT_RTOL = 8.881784197001252e-16
TAIL_RELATIVE_FLOOR = 1.0e-16
"""A certified analytic tail is appended beyond the integrated horizon; the horizon is
chosen so that the tail is below this fraction of the present value, never by seeing
whether a larger horizon 'looks converged'."""


class ConstrainedSuccessorError(RuntimeError):
    """A structural, feasibility, or active-set condition failed."""


# --- the selected zero-tax productive path ---------------------------------------------


@dataclass(frozen=True, slots=True)
class ProductivePath:
    """The selected zero-tax capital path and its present-value wage accumulator.

    ``K_t`` solves ``Kdot = g(q_j^0(K)) K`` on the certified successor manifold, and
    ``PV_t = int_0^t e^{-r t'} W(K_t') dt'`` is integrated alongside it so that partial
    present values are available without re-quadrature.
    """

    rate: float
    rest_capital: float
    rest_wage: float
    initial_capital: float
    initial_wage: float
    horizon: float
    tail_bound: float
    _K: Callable[[float], float]
    _PV: Callable[[float], float]
    _W: Callable[[float], float]
    total_pv_wage: float

    def capital(self, t: float) -> float:
        if t < 0.0:
            raise ConstrainedSuccessorError("the successor path starts at t = 0")
        return self._K(min(t, self.horizon))

    def wage(self, t: float) -> float:
        return self._W(self.capital(t))

    def pv_wage(self, t: float) -> float:
        """``int_0^t e^{-r s} W(K_s) ds``, with the certified analytic tail beyond the
        integration horizon."""
        if t >= self.horizon:
            return self.total_pv_wage - self._tail_from(t) if math.isfinite(t) else self.total_pv_wage
        return self._PV(t)

    def _tail_from(self, t: float) -> float:
        if not math.isfinite(t):
            return 0.0
        return self.rest_wage * math.exp(-self.rate * t) / self.rate


def build_productive_path(
    *,
    rate: float,
    initial_capital: float,
    rest_capital: float,
    price: Callable[[float], float],
    growth: Callable[[float], float],
    wage: Callable[[float], float],
    horizon: float | None = None,
) -> ProductivePath:
    """Integrate the selected productive path once and certify its tail analytically.

    The horizon is set from the analytic tail bound ``W(Kbar) e^{-r T}/r``, not by
    extending until the answer stops moving.
    """
    if rate <= 0.0:
        raise ConstrainedSuccessorError("the successor safe rate must be strictly positive")
    rest_wage = wage(rest_capital)
    initial_wage = wage(initial_capital)
    scale = max(rest_wage, initial_wage) / rate
    if horizon is None:
        horizon = math.log(max(rest_wage, initial_wage) / (rate * scale * TAIL_RELATIVE_FLOOR)) / rate
        horizon = max(horizon, 50.0)

    def rhs(t: float, y: np.ndarray) -> list[float]:
        K = float(y[0])
        return [growth(price(K)) * K, math.exp(-rate * t) * wage(K)]

    solution = solve_ivp(
        rhs, [0.0, horizon], [initial_capital, 0.0],
        rtol=IVP_RTOL, atol=IVP_ATOL, dense_output=True, max_step=1.0,
    )
    if not solution.success:
        raise ConstrainedSuccessorError(f"the productive path did not integrate: {solution.message}")

    tail_bound = rest_wage * math.exp(-rate * horizon) / rate
    total = float(solution.sol(horizon)[1]) + tail_bound

    return ProductivePath(
        rate=rate,
        rest_capital=rest_capital,
        rest_wage=rest_wage,
        initial_capital=initial_capital,
        initial_wage=initial_wage,
        horizon=horizon,
        tail_bound=tail_bound,
        _K=lambda t: float(solution.sol(t)[0]),
        _PV=lambda t: float(solution.sol(t)[1]),
        _W=wage,
        total_pv_wage=total,
    )


# --- transfer-slack threshold (12.6)-(12.7), (16.8)-(16.13) -----------------------------


@dataclass(frozen=True, slots=True)
class TransferSlackCertificate:
    """Whether the unrestricted annuity is globally transfer-feasible."""

    threshold_is_finite: bool
    underline_X: ExtendedReal
    comprehensive_wealth: float
    globally_slack: bool
    minimum_transfer_margin: float | None
    rule: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "threshold_is_finite": self.threshold_is_finite,
            "underline_X": self.underline_X.to_json(),
            "comprehensive_wealth_X": self.comprehensive_wealth,
            "globally_transfer_slack": self.globally_slack,
            "minimum_transfer_margin": self.minimum_transfer_margin,
            "rule": self.rule,
        }


def transfer_slack_certificate(
    path: ProductivePath, rho: float, comprehensive_wealth: float
) -> TransferSlackCertificate:
    """Evaluate (12.6)/(12.7) using the (16.8)-(16.9) classification.

    ``r < rho``: the discounted wage floor diverges, so no finite wealth is globally
    slack and the threshold is ``+inf``. ``r = rho``: the threshold is
    ``max{W(K_0), W(Kbar)}/rho``. ``r > rho`` is not reached by the maintained packets
    and is refused rather than guessed.
    """
    rate = path.rate
    if rate < rho:
        return TransferSlackCertificate(
            threshold_is_finite=False,
            underline_X=POSITIVE_INFINITE,
            comprehensive_wealth=comprehensive_wealth,
            globally_slack=False,
            minimum_transfer_margin=None,
            rule="(16.8): r < rho, so e^{-(r-rho)t} W(K_t) diverges and no finite "
                 "wealth level keeps transfers slack forever",
        )
    if rate == rho:
        floor = max(path.initial_wage, path.rest_wage)
        underline = floor / rho
        slack = comprehensive_wealth >= underline
        annuity = rho * comprehensive_wealth
        return TransferSlackCertificate(
            threshold_is_finite=True,
            underline_X=ExtendedReal.of(underline),
            comprehensive_wealth=comprehensive_wealth,
            globally_slack=slack,
            minimum_transfer_margin=(annuity - floor) if slack else None,
            rule="(16.9): r = rho, so underline_X = max{W(K_0), W(Kbar)}/rho",
        )
    raise ConstrainedSuccessorError(
        "r > rho is outside the maintained packets for this block; (16.10)-(16.13) "
        "would apply and are not implemented rather than guessed"
    )


# --- the constrained solution -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConstrainedSuccessor:
    """The transfer-constrained successor at one positive prefunding level."""

    mark_id: str
    prefunding_level: float
    active_set: str
    annuity_coefficient: float
    successor_marginal_value: float
    switch_time: ExtendedReal
    comprehensive_wealth: float
    budget_residual: float
    minimum_transfer_margin: float | None
    pv_wage_route_gap: float
    initial_consumption: float
    initial_transfer: float
    pv_transfer: float
    certificate: TransferSlackCertificate

    def as_dict(self) -> dict[str, Any]:
        return {
            "mark_id": self.mark_id,
            "prefunding_level_F": self.prefunding_level,
            "active_set": self.active_set,
            "annuity_coefficient_A": self.annuity_coefficient,
            "successor_marginal_value_V_e": self.successor_marginal_value,
            "switch_time_years": self.switch_time.to_json(),
            "comprehensive_wealth_X": self.comprehensive_wealth,
            "pv_transfer_budget_residual": self.budget_residual,
            "pv_wage_route_gap": self.pv_wage_route_gap,
            "minimum_transfer_margin": self.minimum_transfer_margin,
            "initial_consumption_C_0": self.initial_consumption,
            "initial_transfer_T_0": self.initial_transfer,
            "pv_transfer": self.pv_transfer,
            "transfer_slack_certificate": self.certificate.as_dict(),
        }


def _budget_at_switch(path: ProductivePath, rho: float, switch: float) -> tuple[float, float]:
    """``(F, A)`` implied by a candidate switching time.

    ``A`` is pinned by continuity at the switch, ``A e^{(r-rho)t*} = W(K_{t*})``, and the
    budget integrates the transfer wedge on ``[0, t*]`` only, since transfers vanish
    afterwards.
    """
    rate = path.rate
    A = path.wage(switch) * math.exp((rho - rate) * switch)
    annuity_pv = A * (1.0 - math.exp(-rho * switch)) / rho
    return annuity_pv - path.pv_wage(switch), A


def solve_constrained_successor(
    mark_id: str,
    F: float,
    rho: float,
    path: ProductivePath,
    residual_wealth: float,
) -> ConstrainedSuccessor:
    """Solve ``C_t = max{W(K_t), A e^{(r-rho)t}}`` for the unique budget-exhausting ``A``.

    Two active-set geometries are supported and are *classified*, never assumed:
    globally interior (transfers positive for all ``t``, no finite switch) and a single
    transfer-to-zero switch. Any other geometry is refused.
    """
    if not math.isfinite(F) or F <= 0.0:
        raise ConstrainedSuccessorError(
            f"mark {mark_id}: the finite branch takes strictly positive F only; F = 0 is "
            "the literal boundary and is classified one-sidedly"
        )
    X = F + residual_wealth
    if X <= 0.0:
        raise ConstrainedSuccessorError(
            f"mark {mark_id}: comprehensive wealth X = {X!r} is not strictly positive"
        )
    certificate = transfer_slack_certificate(path, rho, X)

    if certificate.globally_slack:
        # The unrestricted annuity is feasible everywhere: transfers never touch zero,
        # so C = rho X and V = 1/(rho X) are the *constrained* solution too.
        A = rho * X
        margin = certificate.minimum_transfer_margin
        if margin is None or margin < 0.0:
            raise ConstrainedSuccessorError(
                f"mark {mark_id}: the slack certificate is inconsistent with its own margin"
            )
        # With r = rho the annuity is constant, so its present value is exactly A/r.
        # The budget is checked inside ONE resource measure: using the same
        # H_P-derived residual wealth that defined X, A/rho - residual - F vanishes
        # identically. The disagreement between that measure and the independently
        # integrated present-value wage is a *route* gap, reported separately and
        # held to its own looser bound, never folded into the budget residual.
        pv_transfer = A / path.rate - residual_wealth
        budget_residual = pv_transfer - F
        return ConstrainedSuccessor(
            mark_id=mark_id,
            prefunding_level=F,
            active_set=GLOBALLY_INTERIOR,
            annuity_coefficient=A,
            successor_marginal_value=1.0 / A,
            switch_time=ExtendedReal("undefined"),
            comprehensive_wealth=X,
            budget_residual=budget_residual,
            minimum_transfer_margin=margin,
            pv_wage_route_gap=abs(residual_wealth - path.total_pv_wage),
            initial_consumption=A,
            initial_transfer=A - path.initial_wage,
            pv_transfer=pv_transfer,
            certificate=certificate,
        )

    # Boundary-active: find the unique transfer-to-zero switch.
    lower, upper = 1.0e-12, path.horizon
    f_lower = _budget_at_switch(path, rho, lower)[0] - F
    f_upper = _budget_at_switch(path, rho, upper)[0] - F
    if f_lower > 0.0:
        raise ConstrainedSuccessorError(
            f"mark {mark_id}: even an immediate switch over-funds F = {F!r}; the wage "
            "floor already exceeds the annuity at date zero"
        )
    if f_upper < 0.0:
        raise ConstrainedSuccessorError(
            f"mark {mark_id}: no switch inside the certified horizon exhausts F = {F!r}; "
            f"the geometry is {UNSUPPORTED_GEOMETRY} rather than a single switch"
        )
    switch = brentq(
        lambda t: _budget_at_switch(path, rho, t)[0] - F,
        lower, upper, xtol=ROOT_XTOL, rtol=ROOT_RTOL, maxiter=200,
    )
    achieved, A = _budget_at_switch(path, rho, switch)
    C0 = max(path.initial_wage, A)
    return ConstrainedSuccessor(
        mark_id=mark_id,
        prefunding_level=F,
        active_set=BOUNDARY_ACTIVE,
        annuity_coefficient=A,
        successor_marginal_value=1.0 / A,
        switch_time=ExtendedReal.of(switch),
        comprehensive_wealth=X,
        budget_residual=achieved - F,
        minimum_transfer_margin=None,
        pv_wage_route_gap=abs(residual_wealth - path.total_pv_wage),
        initial_consumption=C0,
        initial_transfer=C0 - path.initial_wage,
        pv_transfer=achieved,
        certificate=certificate,
    )


def boundary_marginal_value(path: ProductivePath) -> ExtendedReal:
    """The one-sided ``F -> 0+`` limit of ``V_{P,e}``.

    As the buffer vanishes the switch time collapses to zero and ``A -> W(K_0)``, so the
    limit is ``1/W(K_0)`` whenever the initial wage is strictly positive. With a zero
    wage floor -- the full-AK case -- the limit is instead ``+inf``.
    """
    if path.initial_wage > 0.0:
        return ExtendedReal.of(1.0 / path.initial_wage)
    return POSITIVE_INFINITE


__all__ = [
    "ACTIVE_SET_STATUSES",
    "BOUNDARY_ACTIVE",
    "GLOBALLY_INTERIOR",
    "UNSUPPORTED_GEOMETRY",
    "WAGE_ONLY",
    "ConstrainedSuccessor",
    "ConstrainedSuccessorError",
    "ProductivePath",
    "TransferSlackCertificate",
    "boundary_marginal_value",
    "build_productive_path",
    "solve_constrained_successor",
    "transfer_slack_certificate",
]
