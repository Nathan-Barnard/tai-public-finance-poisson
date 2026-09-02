"""The post-mark stable-manifold solver: integrates q_j(k) and H_j(k) on the
declared (u, v) continuation domain and exposes them as callables.

Computes no residuals -- see diagnostics.py for every PM check. This module's
only job is: given MarkParams, produce a PostMarkPath that can evaluate
q_j(k), H_j(k), and q_j'(k) (exactly, by re-evaluating the ODE right-hand
side rather than differentiating an interpolant) anywhere in its certified
domain, and can be asked to (re-)solve on an expanded domain.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scipy.integrate import solve_ivp

from .postmark_equations import MarkParams, continuation_rhs, local_stable_expansion
from .primitives import U_DOMAIN_CAP, U_START_OFFSET

_ODE_RTOL = 1.0e-12
_ODE_ATOL = 1.0e-13
_ODE_METHOD = "DOP853"


@dataclass(frozen=True)
class _SideSolution:
    u_start: float
    u_end: float
    sol: object  # scipy.integrate.OdeSolution (dense output), duck-typed to keep this module light


def _solve_side(mp: MarkParams, u_start: float, u_end: float) -> _SideSolution:
    y0 = local_stable_expansion(u_start, mp)
    result = solve_ivp(
        continuation_rhs,
        (u_start, u_end),
        y0,
        args=(mp,),
        method=_ODE_METHOD,
        dense_output=True,
        rtol=_ODE_RTOL,
        atol=_ODE_ATOL,
        max_step=abs(u_end - u_start) / 50.0,
    )
    if not result.success:
        raise RuntimeError(f"Post-mark continuation ODE failed to integrate for mark {mp.mark} on [{u_start}, {u_end}]: {result.message}")
    return _SideSolution(u_start=u_start, u_end=u_end, sol=result.sol)


@dataclass(frozen=True)
class PostMarkPath:
    """q_j(k) and H_j(k) on u in [u_min, u_max], solved as two one-sided IVPs meeting
    (in the limit) at the anchor u=0, where the (u, v) ODE is singular."""

    mp: MarkParams
    u_min: float
    u_max: float
    negative_side: _SideSolution | None  # None if u_min > -U_START_OFFSET (domain doesn't reach the negative side)
    positive_side: _SideSolution | None

    @property
    def k_min(self) -> float:
        return self.mp.anchor.k_star * math.exp(self.u_min)

    @property
    def k_max(self) -> float:
        return self.mp.anchor.k_star * math.exp(self.u_max)

    def _v_and_H_at_u(self, u: float) -> tuple[float, float]:
        if abs(u) < U_START_OFFSET:
            return local_stable_expansion(u, self.mp)
        if u < 0.0:
            if self.negative_side is None or u < self.negative_side.u_end - 1.0e-9:
                raise ValueError(f"u={u} outside solved domain [{self.u_min}, {self.u_max}] for mark {self.mp.mark}.")
            v, H = self.negative_side.sol(u)
        else:
            if self.positive_side is None or u > self.positive_side.u_end + 1.0e-9:
                raise ValueError(f"u={u} outside solved domain [{self.u_min}, {self.u_max}] for mark {self.mp.mark}.")
            v, H = self.positive_side.sol(u)
        return float(v), float(H)

    def u_of_k(self, k: float) -> float:
        return math.log(k / self.mp.anchor.k_star)

    def q(self, k: float) -> float:
        u = self.u_of_k(k)
        v, _H = self._v_and_H_at_u(u)
        return self.mp.q_star * math.exp(v)

    def H(self, k: float) -> float:
        u = self.u_of_k(k)
        _v, H = self._v_and_H_at_u(u)
        return H

    def q_prime(self, k: float) -> float:
        """Exact q_j'(k), obtained by re-evaluating the continuation ODE's right-hand
        side at the solved (u, v) rather than differentiating the interpolant."""

        u = self.u_of_k(k)
        if abs(u) < U_START_OFFSET:
            return self.mp.anchor.q_prime_star
        v, H = self._v_and_H_at_u(u)
        q = self.mp.q_star * math.exp(v)
        dv_du, _dH_du = continuation_rhs(u, (v, H), self.mp)
        return (q / k) * dv_du

    def contains(self, k: float) -> bool:
        return self.k_min <= k <= self.k_max

    def log_distance_to_edge(self, k: float) -> float:
        u = self.u_of_k(k)
        return min(u - self.u_min, self.u_max - u)


def solve_postmark(mp: MarkParams, u_min: float, u_max: float) -> PostMarkPath:
    negative_side = _solve_side(mp, -U_START_OFFSET, u_min) if u_min < -U_START_OFFSET else None
    positive_side = _solve_side(mp, U_START_OFFSET, u_max) if u_max > U_START_OFFSET else None
    return PostMarkPath(mp=mp, u_min=u_min, u_max=u_max, negative_side=negative_side, positive_side=positive_side)


def ensure_domain(path: PostMarkPath, u_min_needed: float, u_max_needed: float, margin: float = 0.25) -> PostMarkPath:
    """Re-solve on an expanded domain (one log unit at a time, capped at U_DOMAIN_CAP) if
    u_min_needed/u_max_needed lies within `margin` log units of the current edge or outside it.

    Mirrors CS005's "enlarged one log unit at a time, up to |u|=8 ... when the
    pre-arrival search or a candidate lies within 0.25 log units of an edge."
    """

    new_u_min, new_u_max = path.u_min, path.u_max
    while new_u_min > -U_DOMAIN_CAP and u_min_needed < new_u_min + margin:
        new_u_min = max(-U_DOMAIN_CAP, new_u_min - 1.0)
    while new_u_max < U_DOMAIN_CAP and u_max_needed > new_u_max - margin:
        new_u_max = min(U_DOMAIN_CAP, new_u_max + 1.0)
    if new_u_min == path.u_min and new_u_max == path.u_max:
        return path
    return solve_postmark(path.mp, new_u_min, new_u_max)


def simulate_time_domain(mp: MarkParams, k0: float, q0: float, t_span: tuple[float, float]) -> object:
    """Forward-simulate the true-time (k, q) system from (k0, q0). Used only by
    diagnostics.py's independent tail/convergence check -- not by the solver above,
    which never needs true time."""

    from .postmark_equations import time_domain_rhs

    result = solve_ivp(
        time_domain_rhs,
        t_span,
        (k0, q0),
        args=(mp,),
        method=_ODE_METHOD,
        dense_output=True,
        rtol=_ODE_RTOL,
        atol=_ODE_ATOL,
    )
    if not result.success:
        raise RuntimeError(f"Time-domain tail simulation failed for mark {mp.mark}: {result.message}")
    return result
