"""Pre-arrival candidate enumeration: private portfolio roots, the public
saving/exposure block (debt-interior and debt-boundary KKT branches), and the
scalar capital residual K(k), searched over a grid of trial k with bracketed
refinement.

This is a *reduced-coverage* search relative to CS005's full I2 protocol
(513/1025 Chebyshev nodes, 64 deterministic Sobol starts, iterative box/domain
doubling until two refinements agree). It uses one log-spaced grid per branch
slot, brackets sign changes, and refines with brentq -- multi-start in the
sense of covering every algebraic branch and the full declared k-domain, but
not CS005's exhaustive coverage-certification protocol. Branch "slots" are
identified by sorting each k's roots (by pi, or by e) and indexing by
position; near a bifurcation (a quadratic's discriminant crossing zero) a
slot's identity across adjacent grid points is not rigorously continuation-
tracked, which is exactly the coverage gap CS005's heavier protocol exists to
close. This is reported explicitly rather than papered over.

No residuals are computed here beyond K(k) itself, which is the equation this
module's job is to solve -- see diagnostics.py for the independent evaluator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .postmark_equations import rental
from .postmark_solver import PostMarkPath, ensure_domain
from .prearrival_equations import (
    Recovery,
    capital_residual,
    capital_residual_A_iota,
    compensator,
    compensator_derivative,
    debt_boundary_multiplier,
    debt_boundary_quadratic_coefficients,
    envelope_O,
    jump,
    jump_derivative_iota,
    jump_derivative_k,
    linear_relation_coefficients,
    m_values,
    net_production_0,
    private_portfolio_roots,
    public_interior_roots_via_e,
    public_interior_roots_via_psi,
    recover,
    solve_quadratic,
)
from .primitives import DerivedConstants, RawPrimitives

_LINE_DEGENERACY_RELATIVE_TOL = 1.0e-9
_MAX_K_RESIDUAL_FOR_CANDIDATE = 1.0e-3
"""A bisection that lands on a slot-tracking discontinuity (see module docstring) rather
than a genuine root of K(k)=0 produces |K_residual| many orders of magnitude above this
(empirically 1e8-1e12, versus 1e-12-1e-16 for a converged root) -- generous relative to
CS005's eventual 1e-10 acceptance tolerance, this is purely a "did bisection converge to
anything real" filter, not the tolerance check itself (diagnostics.py applies that)."""


def _robust_bisect(f, x_lo: float, f_lo: float, x_hi: float, f_hi: float, max_iter: int = 80, x_tol_rel: float = 1.0e-12) -> float | None:
    """Bisect f on [x_lo, x_hi] given f_lo, f_hi of opposite sign (or f_lo == 0).

    f may legitimately be undefined (return non-finite, e.g. NaN or +/-inf) at
    isolated points -- a denominator (X_L, X_H, or c_0^W) crossing zero as the
    free variable varies is a pole, not a root, and a coarse grid's detected
    "sign change" can straddle one. If the midpoint is non-finite, this nudges
    to a nearby point; if that still fails, it abandons (returns None) rather
    than accept a pole as a root or propagate an exception.
    """

    if f_lo == 0.0:
        return x_lo
    for _ in range(max_iter):
        if abs(x_hi - x_lo) < x_tol_rel * max(1.0, abs(x_lo)):
            break
        x_mid = 0.5 * (x_lo + x_hi)
        f_mid = f(x_mid)
        if not math.isfinite(f_mid):
            for nudge in (1.0e-6, -1.0e-6, 1.0e-4, -1.0e-4):
                x_try = x_mid + nudge * max(1.0, abs(x_hi - x_lo))
                if not (min(x_lo, x_hi) < x_try < max(x_lo, x_hi)):
                    continue
                f_try = f(x_try)
                if math.isfinite(f_try):
                    x_mid, f_mid = x_try, f_try
                    break
            else:
                return None
        if f_mid == 0.0:
            return x_mid
        if (f_mid < 0.0) == (f_lo < 0.0):
            x_lo, f_lo = x_mid, f_mid
        else:
            x_hi, f_hi = x_mid, f_mid
    return 0.5 * (x_lo + x_hi)


@dataclass(frozen=True)
class PointGeometry:
    """Everything at trial k that depends only on k (not on the candidate branch)."""

    k: float
    J_L: float
    J_H: float
    H_L: float
    H_H: float
    q_L: float
    q_H: float
    Lambda: float
    H_ref: float
    R_0: float


def point_geometry(p: RawPrimitives, derived: DerivedConstants, path_L: PostMarkPath, path_H: PostMarkPath, k: float) -> PointGeometry:
    q_L, q_H = path_L.q(k), path_H.q(k)
    H_L, H_H = path_L.H(k), path_H.H(k)
    J_L, J_H = jump(q_L, derived.q_star), jump(q_H, derived.q_star)
    Lambda = compensator(J_L, J_H, p.lambda_L_star, p.lambda_H_star)
    H_ref = max(1.0, abs(H_L), abs(H_H), derived.q_star * k)
    R_0 = rental(p.I_0, k)
    return PointGeometry(k=k, J_L=J_L, J_H=J_H, H_L=H_L, H_H=H_H, q_L=q_L, q_H=q_H, Lambda=Lambda, H_ref=H_ref, R_0=R_0)


def private_roots_at(p: RawPrimitives, g: PointGeometry) -> list[float]:
    roots = private_portfolio_roots(g.Lambda, g.J_L, g.J_H, p.lambda_intensity, p.lambda_L, p.lambda_H)
    return sorted(r.pi for r in roots if r.interior)


def interior_public_roots_at(p: RawPrimitives, derived: DerivedConstants, g: PointGeometry) -> list[tuple[float, float]]:
    A_e, A_psi, A_H = linear_relation_coefficients(derived.Delta_0, p.lambda_L, p.lambda_H, p.lambda_intensity, g.J_L, g.J_H, g.Lambda, g.H_L, g.H_H)
    d_0 = net_production_0(p.I_0, g.k, derived.iota_star)
    scale = max(abs(A_e), abs(A_H), 1.0)
    if abs(A_psi) > _LINE_DEGENERACY_RELATIVE_TOL * scale:
        roots = public_interior_roots_via_e(A_e, A_psi, A_H, d_0, p.rbar_0, g.Lambda, g.H_L, g.H_H, g.J_L, g.J_H, p.lambda_L, p.lambda_H, p.rho, derived.Delta_0)
    elif abs(A_e) > _LINE_DEGENERACY_RELATIVE_TOL * scale:
        roots = public_interior_roots_via_psi(A_e, A_psi, A_H, d_0, p.rbar_0, g.Lambda, g.H_L, g.H_H, g.J_L, g.J_H, p.lambda_L, p.lambda_H, p.rho, derived.Delta_0)
    else:
        return []
    return sorted((r.e, r.psi) for r in roots)


def boundary_roots_at(p: RawPrimitives, derived: DerivedConstants, g: PointGeometry) -> list[float]:
    """Roots of the nu_B-eliminated boundary equation, solved as the cleared quadratic
    in e (see debt_boundary_quadratic_coefficients) rather than by bracketing the
    rational form, which has spurious sign changes at its X_L=0/X_H=0/c_0^W=0 poles."""

    coeffs = debt_boundary_quadratic_coefficients(
        k=g.k, I_0=p.I_0, iota_star=derived.iota_star, rbar_0=p.rbar_0, Lambda=g.Lambda, H_L=g.H_L, H_H=g.H_H, J_L=g.J_L, J_H=g.J_H, lambda_L=p.lambda_L, lambda_H=p.lambda_H, rho=p.rho, Delta_0=derived.Delta_0
    )
    return sorted(solve_quadratic(coeffs))


@dataclass(frozen=True)
class Candidate:
    k: float
    e: float
    psi: float
    pi: float
    branch: str  # "debt_interior" | "debt_boundary"
    nu_B: float | None
    b: float
    epsilon_B: float
    K_residual: float
    recovery: Recovery
    slot: str  # human-readable provenance, e.g. "pi[0]/interior[1]"


@dataclass(frozen=True)
class _KEvaluation:
    K: float
    c0W: float
    X_L: float
    X_H: float

    @property
    def denominators(self) -> tuple[float, float, float]:
        return self.c0W, self.X_L, self.X_H


def _capital_residual_at(p: RawPrimitives, derived: DerivedConstants, path_L: PostMarkPath, path_H: PostMarkPath, g: PointGeometry, e: float, psi: float, pi: float) -> _KEvaluation:
    c0W = net_production_0(p.I_0, g.k, derived.iota_star) + p.rbar_0 * e - psi * g.Lambda
    X_L = e + g.H_L + psi * g.J_L
    X_H = e + g.H_H + psi * g.J_H
    m0, mL, mH = m_values(derived.eta_W, p.rho, c0W, X_L, X_H)
    J_L_k = jump_derivative_k(path_L.q_prime(g.k), derived.q_star)
    J_H_k = jump_derivative_k(path_H.q_prime(g.k), derived.q_star)
    J_L_iota = jump_derivative_iota(p.phi, derived.q_star, g.J_L)
    J_H_iota = jump_derivative_iota(p.phi, derived.q_star, g.J_H)
    Lambda_k = compensator_derivative(p.lambda_L_star, p.lambda_H_star, J_L_k, J_H_k)
    Lambda_iota = compensator_derivative(p.lambda_L_star, p.lambda_H_star, J_L_iota, J_H_iota)
    O_k = envelope_O(derived.eta_K, p.rho, pi, p.lambda_L, p.lambda_H, g.J_L, g.J_H, J_L_k, J_H_k, Lambda_k)
    O_iota = envelope_O(derived.eta_K, p.rho, pi, p.lambda_L, p.lambda_H, g.J_L, g.J_H, J_L_iota, J_H_iota, Lambda_iota)
    A_iota = capital_residual_A_iota(k=g.k, psi=psi, m0=m0, lambda_L=p.lambda_L, lambda_H=p.lambda_H, mL=mL, mH=mH, Lambda_iota=Lambda_iota, J_L_iota=J_L_iota, J_H_iota=J_H_iota, O_iota=O_iota)
    K = capital_residual(
        k=g.k, psi=psi, pi=pi, m0=m0, mL=mL, mH=mH, rho=p.rho, lambda_intensity=p.lambda_intensity, q_star=derived.q_star, iota_star=derived.iota_star, I_0=p.I_0,
        lambda_L=p.lambda_L, lambda_H=p.lambda_H, J_L=g.J_L, J_H=g.J_H, J_L_k=J_L_k, J_H_k=J_H_k, Lambda_k=Lambda_k, Lambda_iota=Lambda_iota, O_k=O_k, O_iota=O_iota, A_iota=A_iota, q_L_at_k=g.q_L, q_H_at_k=g.q_H,
    )
    return _KEvaluation(K=K, c0W=c0W, X_L=X_L, X_H=X_H)


@dataclass(frozen=True)
class SlotSample:
    k: float
    e: float
    psi: float
    K: float
    denominators: tuple[float, float, float]


def _slot_series(p: RawPrimitives, derived: DerivedConstants, path_L: PostMarkPath, path_H: PostMarkPath, k_grid: np.ndarray, pi_index: int, eps_kind: str, eps_index: int) -> list[SlotSample | None]:
    samples: list[SlotSample | None] = []
    for k in k_grid:
        g = point_geometry(p, derived, path_L, path_H, float(k))
        pis = private_roots_at(p, g)
        if pi_index >= len(pis):
            samples.append(None)
            continue
        pi = pis[pi_index]
        if eps_kind == "interior":
            roots = interior_public_roots_at(p, derived, g)
            if eps_index >= len(roots):
                samples.append(None)
                continue
            e, psi = roots[eps_index]
        else:
            roots = boundary_roots_at(p, derived, g)
            if eps_index >= len(roots):
                samples.append(None)
                continue
            e = roots[eps_index]
            psi = e
        evaluation = _capital_residual_at(p, derived, path_L, path_H, g, e, psi, pi)
        samples.append(SlotSample(k=float(k), e=e, psi=psi, K=evaluation.K, denominators=evaluation.denominators))
    return samples


def _evaluate_slot(p: RawPrimitives, derived: DerivedConstants, path_L: PostMarkPath, path_H: PostMarkPath, pi_index: int, eps_kind: str, eps_index: int, k: float) -> tuple[float, float, float, float] | None:
    """(e, psi, pi, K) at this k for this slot, or None if the slot does not exist here
    (a root pair has merged/vanished) or K is non-finite (a denominator hit zero)."""

    g = point_geometry(p, derived, path_L, path_H, k)
    pis = private_roots_at(p, g)
    if pi_index >= len(pis):
        return None
    pi = pis[pi_index]
    if eps_kind == "interior":
        roots = interior_public_roots_at(p, derived, g)
        if eps_index >= len(roots):
            return None
        e, psi = roots[eps_index]
    else:
        roots = boundary_roots_at(p, derived, g)
        if eps_index >= len(roots):
            return None
        e = roots[eps_index]
        psi = e
    evaluation = _capital_residual_at(p, derived, path_L, path_H, g, e, psi, pi)
    if not np.isfinite(evaluation.K):
        return None
    return e, psi, pi, evaluation.K


def _refine_root(
    p: RawPrimitives, derived: DerivedConstants, path_L: PostMarkPath, path_H: PostMarkPath, pi_index: int, eps_kind: str, eps_index: int, k_lo: float, K_lo: float, k_hi: float, K_hi: float
) -> tuple[float, float, float, float] | None:
    """Refine a k-bracket via _robust_bisect (a slot's validity domain, like a pole's,
    can be discontinuous within (k_lo, k_hi) -- e.g. a root pair from a *different*
    branch momentarily coincides in sort order), then re-evaluate the full
    (e, psi, pi) tuple at the refined k."""

    def f(k: float) -> float:
        result = _evaluate_slot(p, derived, path_L, path_H, pi_index, eps_kind, eps_index, k)
        return result[3] if result is not None else math.nan

    k_root = _robust_bisect(f, k_lo, K_lo, k_hi, K_hi)
    if k_root is None:
        return None
    final = _evaluate_slot(p, derived, path_L, path_H, pi_index, eps_kind, eps_index, k_root)
    if final is None:
        return None
    e, psi, pi, _ = final
    return k_root, e, psi, pi


@dataclass(frozen=True)
class EnumerationResult:
    candidates: list[Candidate]
    k_domain: tuple[float, float]
    max_log_distance_to_edge_used: float  # min over accepted candidates' distance to their mark's domain edge
    discarded_nonconvergent_brackets: int = 0


def _denominators_consistent(a: SlotSample, b: SlotSample) -> bool:
    """False if c_0^W, X_L, or X_H changes sign between a and b -- i.e. K(k) has a pole
    (m_0, m_L, or m_H blowing up) somewhere in this bracket, so an apparent K sign
    change here is a pole crossing, not a root of K(k)=0."""

    return all((da > 0.0) == (db > 0.0) for da, db in zip(a.denominators, b.denominators, strict=True))


def enumerate_candidates(p: RawPrimitives, derived: DerivedConstants, path_L: PostMarkPath, path_H: PostMarkPath, k_grid_points: int = 400) -> EnumerationResult:
    k_lo = max(derived.anchor_0.specialization_floor * (1.0 + 1.0e-6), path_L.k_min, path_H.k_min)
    k_hi = min(path_L.k_max, path_H.k_max)
    if k_hi <= k_lo:
        return EnumerationResult(candidates=[], k_domain=(k_lo, k_hi), max_log_distance_to_edge_used=float("nan"))
    k_grid = np.exp(np.linspace(np.log(k_lo), np.log(k_hi), k_grid_points))

    candidates: list[Candidate] = []
    min_edge_distance = float("inf")
    discarded_nonconvergent = 0
    for pi_index in (0, 1):
        for eps_kind, eps_index in (("interior", 0), ("interior", 1), ("boundary", 0), ("boundary", 1)):
            series = _slot_series(p, derived, path_L, path_H, k_grid, pi_index, eps_kind, eps_index)
            for i in range(len(series) - 1):
                a, b = series[i], series[i + 1]
                if a is None or b is None:
                    continue
                if not (np.isfinite(a.K) and np.isfinite(b.K)):
                    continue
                if not _denominators_consistent(a, b):
                    continue
                if a.K == 0.0 or a.K * b.K < 0.0:
                    refined = _refine_root(p, derived, path_L, path_H, pi_index, eps_kind, eps_index, a.k, a.K, b.k, b.K)
                    if refined is None:
                        continue
                    k_root, e, psi, pi = refined
                    g = point_geometry(p, derived, path_L, path_H, k_root)
                    if eps_kind == "interior":
                        nu_B = None
                    else:
                        nu_B_a, nu_B_b = debt_boundary_multiplier(
                            e, k=k_root, I_0=p.I_0, iota_star=derived.iota_star, rbar_0=p.rbar_0, Lambda=g.Lambda, H_L=g.H_L, H_H=g.H_H, J_L=g.J_L, J_H=g.J_H, lambda_L=p.lambda_L, lambda_H=p.lambda_H, eta_W=derived.eta_W, rho=p.rho, Delta_0=derived.Delta_0
                        )
                        nu_B = 0.5 * (nu_B_a + nu_B_b)
                    K_residual = _capital_residual_at(p, derived, path_L, path_H, g, e, psi, pi).K
                    if not np.isfinite(K_residual) or abs(K_residual) > _MAX_K_RESIDUAL_FOR_CANDIDATE:
                        # Bisection landed on a slot-tracking discontinuity, not a genuine
                        # root of K(k)=0 -- discard rather than report a fake candidate.
                        discarded_nonconvergent += 1
                        continue
                    b_val = psi - e
                    epsilon_B = 1.0e-6 * g.H_ref
                    branch = "debt_interior" if (eps_kind == "interior" and b_val >= epsilon_B) else "debt_boundary" if eps_kind == "boundary" else "debt_interior_margin_fail"
                    recovery = recover(
                        k=k_root, e=e, psi=psi, pi=pi, a_0=derived.inherited_state.a_0, I_0=p.I_0, iota_star=derived.iota_star, rbar_0=p.rbar_0, rho=p.rho, Lambda=g.Lambda, J_L=g.J_L, J_H=g.J_H, H_L=g.H_L, H_H=g.H_H, q_star=derived.q_star, q_L_at_k=g.q_L, q_H_at_k=g.q_H
                    )
                    candidates.append(
                        Candidate(
                            k=k_root, e=e, psi=psi, pi=pi, branch=branch, nu_B=nu_B, b=b_val, epsilon_B=epsilon_B, K_residual=K_residual, recovery=recovery, slot=f"pi[{pi_index}]/{eps_kind}[{eps_index}]"
                        )
                    )
                    min_edge_distance = min(min_edge_distance, path_L.log_distance_to_edge(k_root), path_H.log_distance_to_edge(k_root))
    return EnumerationResult(candidates=candidates, k_domain=(k_lo, k_hi), max_log_distance_to_edge_used=min_edge_distance, discarded_nonconvergent_brackets=discarded_nonconvergent)


def enumerate_with_domain_expansion(p: RawPrimitives, derived: DerivedConstants, path_L: PostMarkPath, path_H: PostMarkPath, k_grid_points: int = 400, max_expansions: int = 3) -> tuple[EnumerationResult, PostMarkPath, PostMarkPath]:
    """Wraps enumerate_candidates with CS005's domain-expansion rule: if any accepted root
    lies within 0.25 log units of a mark's certified edge, expand that mark's domain by
    one log unit (capped at |u|=8) and re-run."""

    for _ in range(max_expansions):
        result = enumerate_candidates(p, derived, path_L, path_H, k_grid_points)
        if not result.candidates or result.max_log_distance_to_edge_used >= 0.25:
            return result, path_L, path_H
        expanded_L = ensure_domain(path_L, path_L.u_min - 1.0, path_L.u_max + 1.0)
        expanded_H = ensure_domain(path_H, path_H.u_min - 1.0, path_H.u_max + 1.0)
        if expanded_L is path_L and expanded_H is path_H:
            return result, path_L, path_H  # already at the domain cap
        path_L, path_H = expanded_L, expanded_H
    return enumerate_candidates(p, derived, path_L, path_H, k_grid_points), path_L, path_H
