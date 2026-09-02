"""W5 strict support-based fiscal viability for the rank-one/two-mark baseline.

CS005's strict-viability continuation frontier for an absorbing mark j and the
measurable price label ell is

    underline_f_j(k, ell) = -C_j(k, ell),
    C_j(k, ell) = sup over admissible deterministic continuations of
                  integral_0^inf exp(-rbar_j u) tau_u R_j(k_u) k_u du,

with transfers zero, the post-mark firm equations, bounded tax, q > 0, full
specialization, branch consistency, transversality, and convergence to a
feasible stationary or zero-tax tail. A candidate is strictly viable only if
its successor public wealth f_j^+ exceeds the branch-specific frontier for
every supported mark.

This module certifies the check CONSERVATIVELY, per CS005's rule that until a
verified upper bound on C_j is within 1e-4*max(1, C_j) of the feasible-path
lower bound, W5 may report only `certified_viable` or `frontier_unresolved`
(plus a certified infeasibility against the coarse compact-domain outer bound)
-- never "infeasible because no path was found":

  - **Certified-inner lower bound** C_j >= C_lower via a feasible witness path.
    The witness family is constant-tax continuations. Key structural fact: with
    a constant tax tau on gross rentals, the post-mark saddle system

        k_dot = G(q) k,   q_dot = (rbar_j - G(q)) q + iota(q) - (1-tau) R_j(k)

    is EXACTLY the zero-tax system under the capital rescaling k -> k/s(tau),
    s(tau) = (1-tau)^(1/(1-I_j)), because (1-tau) R_j(k) = R_j(k/s). So every
    constant-tax stable-manifold continuation lives on the already-certified
    zero-tax manifold q_j(.), rescaled -- the tau-branch-consistent smooth
    selection, inheriting PM01-PM08's certification. Since C_lower <= C_j,
    f_j^+ >= -C_lower implies f_j^+ >= underline_f_j: passing against the
    inner bound CERTIFIES viability (with CS005's 1e-6*H_ref margin). The
    witness PV is integrated in true time and independently re-integrated in
    the u = log(k~/k*) coordinate at four-times-finer tolerance; both must
    agree and every constraint must hold along the sampled path.

  - **Compact-domain outer bound** C_j <= C_upper = max_k R_j(k) k / rbar_j
    over the declared (certified) k-domain, at tau = 1 -- CS005's coarse outer
    bound, valid for the full admissible control set, so f_j^+ < -C_upper
    certifies infeasibility ON THE DECLARED DOMAIN.

  - Anything between the two bounds is `frontier_unresolved`: a certification
    gap, never an infeasibility finding.

The constant-tax family is a RESTRICTED control set (no time-varying tax
front-loading, no collocation over free paths), so C_lower is not claimed to
be the frontier and no `underline_f_j` value is reported as closed; the
stationary capacity point (tau_cap = 1 - I_j when rbar_j = rho) is recovered
by this family exactly and is used as a test anchor, not the whole frontier.
Stationarity of a candidate is never treated as inherited-state admissibility;
the frontier is never replaced by a fixed-mark diagnostic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import minimize_scalar

from .postmark_equations import MarkParams, investment_growth_rate, mark_params, rental
from .postmark_solver import PostMarkPath, ensure_domain
from .prearrival_solver import Candidate
from .primitives import SPECIALIZATION_MARGIN, DerivedConstants, RawPrimitives

W5_METHOD = "constant_tax_rescaled_stable_manifold_witness_lower_bound_with_tau1_compact_domain_outer_bound"
W5_PRICE_LABEL = "smooth_zero_tax_stable_manifold_branch"

CERTIFIED_VIABLE = "certified_viable"
CERTIFIED_INFEASIBLE = "certified_infeasible_on_declared_domain"
FRONTIER_UNRESOLVED = "frontier_unresolved"

W5_MARGIN_FACTOR = 1.0e-6  # * H_ref, CS005: "a frontier margin of at least 1e-6*H_ref"
_U_STOP = 1.0e-9
_WITNESS_RTOL = 1.0e-10
_WITNESS_ATOL = 1.0e-12
_INDEPENDENT_AGREEMENT_TOL = 1.0e-8
_TAU_GRID_POINTS = 25
_OUTER_BOUND_GRID_POINTS = 256


def tax_capital_scale(tau: float, task_share: float) -> float:
    """s(tau) = (1-tau)^(1/(1-I_j)), so that (1-tau) R_j(k) = R_j(k/s(tau))."""

    return (1.0 - tau) ** (1.0 / (1.0 - task_share))


def stationary_capacity_tax(task_share: float) -> float:
    """argmax_tau of the stationary revenue flow tau R_j(k_j(tau)) k_j(tau):
    tau_cap = 1 - I_j (CS005's exact stationary anchor when rbar_j = rho)."""

    return 1.0 - task_share


@dataclass(frozen=True)
class CapacityWitness:
    """One certified feasible constant-tax continuation from k0 and its revenue PV."""

    tau: float
    capital_scale: float  # s(tau)
    k_start_rescaled: float  # k~_0 = k0 / s
    transition_horizon: float  # true time to reach |u| = _U_STOP
    pv_transition: float
    pv_stationary_tail: float
    pv: float
    pv_independent: float  # u-coordinate re-integration at four-times-finer tolerance
    independent_agreement: float  # |pv - pv_independent| / max(1, |pv|)
    min_specialization_margin: float  # min over sampled path of s*k~ - floor*(1+margin)
    min_q: float
    reached_anchor: bool
    constraints_pass: bool


def capacity_witness(mp: MarkParams, path: PostMarkPath, k0: float, tau: float, *, with_independent: bool = True) -> CapacityWitness | None:
    """PV of gross-rental tax revenue along the constant-tau witness from capital k0,
    or None when the witness is domain-limited (rescaled start outside the certified
    manifold domain) or structurally infeasible (stationary point below the
    specialization floor). None is never evidence about the frontier."""

    if not 0.0 <= tau < 1.0:
        return None
    s = tax_capital_scale(tau, mp.task_share)
    k_star = mp.anchor.k_star
    floor_strict = mp.anchor.specialization_floor * (1.0 + SPECIALIZATION_MARGIN)
    if s * k_star <= floor_strict:
        return None  # the tau-stationary point violates full specialization
    kt0 = k0 / s
    if not path.contains(kt0):
        return None  # domain-limited witness; not evidence about C_j

    def flow(kt: float) -> float:
        k_actual = s * kt
        return tau * rental(mp.task_share, k_actual) * k_actual

    def q_clamped(kt: float) -> float:
        return path.q(min(max(kt, path.k_min), path.k_max))

    u0 = math.log(kt0 / k_star)
    flow_star = flow(k_star)

    if abs(u0) <= _U_STOP:
        pv = flow_star / mp.rbar
        margin = s * kt0 - floor_strict
        return CapacityWitness(
            tau=tau,
            capital_scale=s,
            k_start_rescaled=kt0,
            transition_horizon=0.0,
            pv_transition=0.0,
            pv_stationary_tail=pv,
            pv=pv,
            pv_independent=pv,
            independent_agreement=0.0,
            min_specialization_margin=margin,
            min_q=q_clamped(kt0),
            reached_anchor=True,
            constraints_pass=margin >= 0.0,
        )

    sign0 = 1.0 if u0 > 0.0 else -1.0

    def rhs_t(t: float, y: tuple[float, float]) -> tuple[float, float]:
        kt, _P = y
        q = q_clamped(kt)
        G = investment_growth_rate(q, mp.phi, mp.delta, mp.g)
        return G * kt, math.exp(-mp.rbar * t) * flow(kt)

    def hit_anchor(_t: float, y: tuple[float, float]) -> float:
        return math.log(y[0] / k_star) - sign0 * _U_STOP

    hit_anchor.terminal = True
    T_max = 100.0 + 40.0 / abs(mp.anchor.nu_minus)
    sim = solve_ivp(rhs_t, (0.0, T_max), (kt0, 0.0), method="DOP853", rtol=_WITNESS_RTOL, atol=_WITNESS_ATOL, events=hit_anchor)
    if not sim.success:
        return None
    reached = sim.status == 1
    T = float(sim.t[-1])
    pv_transition = float(sim.y[1][-1])
    pv_tail = math.exp(-mp.rbar * T) * flow_star / mp.rbar
    pv = pv_transition + pv_tail

    min_margin = float("inf")
    min_q = float("inf")
    for kt_i in sim.y[0]:
        min_margin = min(min_margin, s * float(kt_i) - floor_strict)
        min_q = min(min_q, q_clamped(float(kt_i)))

    if with_independent:
        # Independent re-integration in the u = log(k~/k*) coordinate (a genuinely
        # different independent variable and step sequence) at four-times-finer
        # tolerance: dt/du = 1/G, dP/du = exp(-rbar t) flow / G.
        def rhs_u(u: float, y: tuple[float, float]) -> tuple[float, float]:
            t, _P = y
            kt = k_star * math.exp(u)
            G = investment_growth_rate(q_clamped(kt), mp.phi, mp.delta, mp.g)
            return 1.0 / G, math.exp(-mp.rbar * t) * flow(kt) / G

        sim_u = solve_ivp(rhs_u, (u0, sign0 * _U_STOP), (0.0, 0.0), method="DOP853", rtol=_WITNESS_RTOL / 4.0, atol=_WITNESS_ATOL / 4.0)
        if not sim_u.success:
            return None
        T_ind = float(sim_u.y[0][-1])
        pv_independent = float(sim_u.y[1][-1]) + math.exp(-mp.rbar * T_ind) * flow_star / mp.rbar
        agreement = abs(pv - pv_independent) / max(1.0, abs(pv))
    else:
        pv_independent = math.nan
        agreement = math.nan

    constraints_pass = reached and min_margin >= 0.0 and min_q > 0.0 and (not with_independent or agreement <= _INDEPENDENT_AGREEMENT_TOL)
    return CapacityWitness(
        tau=tau,
        capital_scale=s,
        k_start_rescaled=kt0,
        transition_horizon=T,
        pv_transition=pv_transition,
        pv_stationary_tail=pv_tail,
        pv=pv,
        pv_independent=pv_independent,
        independent_agreement=agreement,
        min_specialization_margin=min_margin,
        min_q=min_q,
        reached_anchor=reached,
        constraints_pass=constraints_pass,
    )


@dataclass(frozen=True)
class CapacityLowerBound:
    value: float  # certified C_lower <= C_j; >= 0 always (the zero-tax continuation is feasible)
    witness: CapacityWitness | None  # None only when every positive-tax witness was domain-limited
    tau_bounds_searched: tuple[float, float]
    n_grid: int
    n_feasible: int
    domain_limited: bool  # True if any grid tau had to be skipped for domain reasons


def capacity_lower_bound(mp: MarkParams, path: PostMarkPath, k0: float, tau_min: float, tau_max: float, n_grid: int = _TAU_GRID_POINTS) -> CapacityLowerBound:
    """Certified-inner lower bound on C_j(k0, ell): maximize the witness PV over the
    constant-tax family on [tau_min, tau_ub], tau_ub capped so the tau-stationary
    point respects full specialization strictly. The zero-tax continuation (PV = 0)
    is always feasible on the certified manifold, so the bound is never negative."""

    floor_strict = mp.anchor.specialization_floor * (1.0 + 2.0 * SPECIALIZATION_MARGIN)
    tau_specialization_cap = 1.0 - (floor_strict / mp.anchor.k_star) ** (1.0 - mp.task_share)
    tau_ub = min(tau_max, tau_specialization_cap)
    if tau_ub <= tau_min:
        return CapacityLowerBound(value=0.0, witness=None, tau_bounds_searched=(tau_min, tau_min), n_grid=0, n_feasible=0, domain_limited=False)

    taus = np.linspace(tau_min, tau_ub, n_grid)[1:]  # tau = tau_min(=0 typically) contributes PV ~ 0
    best_tau, best_pv = None, 0.0
    n_feasible, domain_limited = 0, False
    for tau in taus:
        w = capacity_witness(mp, path, k0, float(tau), with_independent=False)
        if w is None:
            domain_limited = True
            continue
        if not (w.reached_anchor and w.min_specialization_margin >= 0.0 and w.min_q > 0.0):
            continue
        n_feasible += 1
        if w.pv > best_pv:
            best_tau, best_pv = float(tau), w.pv

    if best_tau is not None:
        spacing = float(taus[1] - taus[0]) if len(taus) > 1 else 0.0
        lo, hi = max(tau_min, best_tau - spacing), min(tau_ub, best_tau + spacing)
        if hi > lo:
            def negative_pv(tau: float) -> float:
                w = capacity_witness(mp, path, k0, float(tau), with_independent=False)
                if w is None or not (w.reached_anchor and w.min_specialization_margin >= 0.0 and w.min_q > 0.0):
                    return 0.0
                return -w.pv

            refined = minimize_scalar(negative_pv, bounds=(lo, hi), method="bounded", options={"xatol": 1.0e-4})
            if refined.success and -refined.fun > best_pv:
                best_tau = float(refined.x)

    final = capacity_witness(mp, path, k0, best_tau, with_independent=True) if best_tau is not None else None
    if final is not None and final.constraints_pass:
        return CapacityLowerBound(value=final.pv, witness=final, tau_bounds_searched=(tau_min, tau_ub), n_grid=len(taus), n_feasible=n_feasible, domain_limited=domain_limited)
    # No certified positive-tax witness: fall back to the zero-tax continuation (PV = 0).
    return CapacityLowerBound(value=0.0, witness=None, tau_bounds_searched=(tau_min, tau_ub), n_grid=len(taus), n_feasible=n_feasible, domain_limited=domain_limited)


def capacity_outer_bound(mp: MarkParams, path: PostMarkPath, n_grid: int = _OUTER_BOUND_GRID_POINTS) -> float:
    """CS005's coarse compact-domain upper bound C_j <= max_k R_j(k) k / rbar_j over the
    declared (certified) domain, at tau = 1 -- valid for the FULL admissible control
    set, so it supports certified infeasibility on the declared domain only."""

    ks = np.exp(np.linspace(math.log(path.k_min), math.log(path.k_max), n_grid))
    max_revenue_flow = max(rental(mp.task_share, float(k)) * float(k) for k in ks)
    return max_revenue_flow / mp.rbar


def classify_mark_viability(f_plus: float, capacity_lower: float, capacity_outer: float, margin_requirement: float) -> tuple[str, float]:
    """(label, margin). margin = f_plus - (-C_lower) = f_plus + C_lower: distance of
    successor public wealth above the certified-inner frontier bound -C_lower, which
    upper-bounds the true frontier underline_f_j = -C_j (since C_j >= C_lower).

      f_plus + C_lower >= margin_requirement  =>  certified_viable
      f_plus + C_outer < 0                    =>  certified infeasible (declared domain)
      otherwise                               =>  frontier_unresolved (a certification
                                                  gap, NEVER an infeasibility finding)
    """

    margin = f_plus + capacity_lower
    if margin >= margin_requirement:
        return CERTIFIED_VIABLE, margin
    if f_plus + capacity_outer < 0.0:
        return CERTIFIED_INFEASIBLE, margin
    return FRONTIER_UNRESOLVED, margin


@dataclass(frozen=True)
class MarkViability:
    mark: str
    price_label: str
    k: float
    f_plus: float
    capacity_lower_bound: float
    capacity_outer_bound: float
    frontier_upper_bound: float  # -C_lower >= underline_f_j (certified-inner threshold)
    frontier_lower_bound: float  # -C_outer <= underline_f_j (compact-domain outer threshold)
    margin: float  # f_plus + C_lower
    margin_requirement: float  # W5_MARGIN_FACTOR * H_ref
    witness: CapacityWitness | None
    tau_bounds_searched: tuple[float, float]
    domain_limited: bool
    label: str


def mark_viability(
    p: RawPrimitives, mp: MarkParams, path: PostMarkPath, k: float, f_plus: float, h_ref_value: float, *, margin_factor: float = W5_MARGIN_FACTOR
) -> MarkViability:
    lower = capacity_lower_bound(mp, path, k, p.tau_min, p.tau_max)
    outer = capacity_outer_bound(mp, path)
    margin_requirement = margin_factor * h_ref_value
    label, margin = classify_mark_viability(f_plus, lower.value, outer, margin_requirement)
    return MarkViability(
        mark=mp.mark,
        price_label=W5_PRICE_LABEL,
        k=k,
        f_plus=f_plus,
        capacity_lower_bound=lower.value,
        capacity_outer_bound=outer,
        frontier_upper_bound=-lower.value,
        frontier_lower_bound=-outer,
        margin=margin,
        margin_requirement=margin_requirement,
        witness=lower.witness,
        tau_bounds_searched=lower.tau_bounds_searched,
        domain_limited=lower.domain_limited,
        label=label,
    )


@dataclass(frozen=True)
class CandidateViability:
    checked: bool
    method: str
    price_label: str
    tau_bounds_profile: tuple[float, float]
    margin_requirement: float
    marks: dict[str, MarkViability]
    label: str  # certified_viable | certified_infeasible_on_declared_domain | frontier_unresolved
    passes: bool  # True iff every supported mark is certified_viable
    min_margin: float  # min over marks of (f_j^+ + C_lower_j)
    failure_reason: str | None


def ensure_witness_domain(p: RawPrimitives, mp: MarkParams, path: PostMarkPath, k0: float) -> PostMarkPath:
    """Expand the certified manifold domain (one log unit at a time, capped at |u|=8)
    so the rescaled witness start k0/s(tau) fits for every tau the search may try."""

    floor_strict = mp.anchor.specialization_floor * (1.0 + 2.0 * SPECIALIZATION_MARGIN)
    tau_ub = min(p.tau_max, 1.0 - (floor_strict / mp.anchor.k_star) ** (1.0 - mp.task_share))
    if tau_ub <= p.tau_min:
        return path
    s_min = tax_capital_scale(tau_ub, mp.task_share)
    u_needed = math.log(k0 / (s_min * mp.anchor.k_star))
    return ensure_domain(path, min(path.u_of_k(k0), u_needed), max(path.u_of_k(k0), u_needed))


def candidate_strict_viability(
    p: RawPrimitives, derived: DerivedConstants, path_L: PostMarkPath, path_H: PostMarkPath, c: Candidate, *, margin_factor: float = W5_MARGIN_FACTOR
) -> CandidateViability:
    """W5 strict state-by-state viability for one candidate: f_j^+ >= underline_f_j(k, ell)
    for every supported mark j in {L, H}, certified via the conservative bounds above.
    This is a viability certification only -- it does not touch the candidate's atlas /
    inherited-state (date-zero) classification."""

    h_ref_value = max(1.0, abs(path_L.H(c.k)), abs(path_H.H(c.k)), derived.q_star * c.k)
    marks: dict[str, MarkViability] = {}
    for mark, path, f_plus in (("L", path_L, c.recovery.f_L_plus), ("H", path_H, c.recovery.f_H_plus)):
        mp = mark_params(p, derived, mark)
        expanded = ensure_witness_domain(p, mp, path, c.k)
        marks[mark] = mark_viability(p, mp, expanded, c.k, f_plus, h_ref_value, margin_factor=margin_factor)

    labels = {m: v.label for m, v in marks.items()}
    infeasible_marks = sorted(m for m, lbl in labels.items() if lbl == CERTIFIED_INFEASIBLE)
    unresolved_marks = sorted(m for m, lbl in labels.items() if lbl == FRONTIER_UNRESOLVED)
    if infeasible_marks:
        label = CERTIFIED_INFEASIBLE
        failure_reason = (
            f"successor public wealth f_j^+ lies below the tau=1 compact-domain outer frontier bound "
            f"-C_upper for mark(s) {', '.join(infeasible_marks)}: certified infeasible on the declared domain"
        )
    elif unresolved_marks:
        label = FRONTIER_UNRESOLVED
        failure_reason = (
            f"the certified-inner capacity lower bound (constant-tax witness family) is insufficient to "
            f"certify f_j^+ >= underline_f_j for mark(s) {', '.join(unresolved_marks)}, and the outer bound "
            f"does not certify infeasibility: frontier unresolved -- a certification gap, not an infeasibility finding"
        )
    else:
        label = CERTIFIED_VIABLE
        failure_reason = None

    return CandidateViability(
        checked=True,
        method=W5_METHOD,
        price_label=W5_PRICE_LABEL,
        tau_bounds_profile=(p.tau_min, p.tau_max),
        margin_requirement=margin_factor * h_ref_value,
        marks=marks,
        label=label,
        passes=label == CERTIFIED_VIABLE,
        min_margin=min(v.margin for v in marks.values()),
        failure_reason=failure_reason,
    )
