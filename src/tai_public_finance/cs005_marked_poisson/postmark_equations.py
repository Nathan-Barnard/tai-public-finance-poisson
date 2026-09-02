"""Post-mark equation construction: output, rentals, investment technology, and the
saddle-path ODEs in both the (u, v, H) continuation coordinates and true time.

Pure functions only -- nothing here integrates an ODE or reports a residual;
see postmark_solver.py for the solve and diagnostics.py for the independent
residual evaluator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .primitives import DerivedConstants, MarkAnchor, Omega, RawPrimitives


def output(task_share: float, k: float) -> float:
    """y_s(k) = Omega(I_s) k^{I_s}."""

    return Omega(task_share) * k**task_share


def wage(task_share: float, k: float) -> float:
    """w_s(k) = (1-I_s) y_s(k)."""

    return (1.0 - task_share) * output(task_share, k)


def rental(task_share: float, k: float) -> float:
    """R_s(k) = I_s Omega(I_s) k^{I_s-1}."""

    return task_share * Omega(task_share) * k ** (task_share - 1.0)


def investment_growth_rate(q: float, phi: float, delta: float, g: float) -> float:
    """G(q) = log(q)/phi - delta - g, so k-dot = G(q) k."""

    return math.log(q) / phi - delta - g


def investment_rate(q: float, phi: float) -> float:
    """iota(q) = (q-1)/phi, from the investment FOC q = 1 + phi*iota."""

    return (q - 1.0) / phi


@dataclass(frozen=True)
class MarkParams:
    """The subset of primitives/derived constants one post-mark mark's equations need."""

    mark: str
    task_share: float
    rbar: float
    phi: float
    delta: float
    g: float
    q_star: float
    iota_star: float
    anchor: MarkAnchor


def mark_params(p: RawPrimitives, derived: DerivedConstants, mark: str) -> MarkParams:
    anchor = derived.anchors[mark]
    rbar = {"L": p.rbar_L, "H": p.rbar_H}[mark]
    task_share = {"L": p.I_L, "H": p.I_H}[mark]
    return MarkParams(
        mark=mark,
        task_share=task_share,
        rbar=rbar,
        phi=p.phi,
        delta=p.delta,
        g=p.g,
        q_star=derived.q_star,
        iota_star=derived.iota_star,
        anchor=anchor,
    )


def continuation_rhs(u: float, state: tuple[float, float], mp: MarkParams) -> tuple[float, float]:
    """dv/du and dH/du in the (u, v) = (log(k/k*), log(q/q*)) continuation coordinates.

    This is the displayed equation q_j'(k) G(q_j) k = [rbar_j - G(q_j)] q_j - R_j(k) + iota(q_j)
    rewritten as dv/du via the chain rule (dv/du = (k/q) dq/dk), plus dH/du = q k
    from H_j'(k) = q_j(k). Singular at u=0 (G(q_star)=0 identically) -- callers
    must not evaluate this at u=0; integration starts at +/-U_START_OFFSET.
    """

    v, _H = state
    k = mp.anchor.k_star * math.exp(u)
    q = mp.q_star * math.exp(v)
    G_q = investment_growth_rate(q, mp.phi, mp.delta, mp.g)
    R = rental(mp.task_share, k)
    iota = investment_rate(q, mp.phi)
    dv_du = ((mp.rbar - G_q) * q - R + iota) / (q * G_q)
    dH_du = q * k
    return dv_du, dH_du


def local_stable_expansion(u: float, mp: MarkParams) -> tuple[float, float]:
    """First-order stable expansion of (v, H) at small |u|, used as the solve_ivp initial
    condition at u = +/-U_START_OFFSET (CS005: "integration begins at |u|=1e-6 using the
    first-order stable expansion from both sides")."""

    v0 = mp.phi * mp.anchor.nu_minus * u
    H0 = mp.anchor.H_star + mp.q_star * mp.anchor.k_star * u
    return v0, H0


def time_domain_rhs(_t: float, state: tuple[float, float], mp: MarkParams) -> tuple[float, float]:
    """True-time (k-dot, q-dot) system -- the independent tail/convergence check integrates
    this forward from a point on the solved (u, v) graph and confirms convergence to the anchor."""

    k, q = state
    G_q = investment_growth_rate(q, mp.phi, mp.delta, mp.g)
    R = rental(mp.task_share, k)
    iota = investment_rate(q, mp.phi)
    k_dot = G_q * k
    q_dot = (mp.rbar - G_q) * q - R + iota
    return k_dot, q_dot
