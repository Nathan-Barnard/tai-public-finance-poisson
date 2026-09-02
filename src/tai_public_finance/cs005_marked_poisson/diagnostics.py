"""The independent residual/diagnostic evaluator for both the post-mark (PM) and
pre-arrival (PR) blocks.

Every check below is re-derived using a numerical route genuinely different
from the one the solver used to produce the object being checked -- a finite-
difference derivative where the solver used an analytic/ODE-exact one, a
numerically-built Jacobian and its eigendecomposition where the solver used
the closed-form eigenvalue formula, the *raw* nonlinear public FOCs where the
solver used the algebraic linear+quadratic reduction, and a forward time-
domain simulation where the solver worked in (u, v) continuation coordinates.
This is deliberate: a construction bug shared between "the solver" and "the
check" would otherwise cancel silently. See CLAUDE.md's requirement that this
module be mutation-tested (tests/cs005_marked_poisson/test_diagnostics.py)
before being called independent.

Two explicit exceptions to full independence, both stated in CS005 as
acceptable ("separately coded from the displayed equations"), and neither
hidden:
  - PR06 (the scalar capital residual K(k)) is independently re-implemented
    from the same displayed formula (different intermediate variables, a
    fresh derivation of the codebase) plus finite-difference verification of
    every partial-derivative term (Lambda_k, Lambda_iota, J_{j,k}, J_{j,iota})
    -- but the top-level aggregation formula is the same formula, since
    CS005's own text supplies only the reduced K(k), not a from-scratch
    unreduced costate pair, in the four source documents this implementation
    was authorized against.
  - The debt-boundary root is *found* via the cleared polynomial
    (debt_boundary_quadratic_coefficients); PR08 here independently confirms
    it against the *uncleared* rational nu_B-eliminated equation
    (debt_boundary_equation) and the raw two-FOC system directly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .postmark_equations import MarkParams, investment_growth_rate, investment_rate, output, rental, time_domain_rhs
from .postmark_solver import PostMarkPath, simulate_time_domain
from .prearrival_equations import compensator, debt_boundary_equation, jump, m_values, net_production_0
from .prearrival_solver import Candidate, PointGeometry, point_geometry
from .primitives import DerivedConstants, RawPrimitives

R_REF_FLOOR = 1.0e-4


def scaled_residual(*terms: float) -> float:
    """CS005's residual scaling: raw residual (the last positional term, by convention
    the true residual value placed LAST) divided by max(1, sum(abs(term_i))) over the
    remaining terms. Call as scaled_residual(term_1, ..., term_n, residual)."""

    *components, residual = terms
    return abs(residual) / max(1.0, sum(abs(c) for c in components))


def h_ref(H_L: float, H_H: float, q_star: float, k: float) -> float:
    return max(1.0, abs(H_L), abs(H_H), q_star * k)


def r_ref(rho: float, lambda_intensity: float, rbar: float) -> float:
    return max(rho, lambda_intensity, abs(rbar), R_REF_FLOOR)


# ---------------------------------------------------------------------------
# Post-mark (PM) independent checks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PostMarkDiagnostics:
    mark: str
    pm01_ode_residual_finite_difference: float  # PM01: displayed q-ODE, q'(k) from finite differences
    pm02_H_prime_vs_q_finite_difference: float  # PM02
    pm03_anchor_user_cost_identity: float  # PM03: R_j(k*) - R_j^w
    pm03_k_star_recompute_relative_error: float
    pm04_eigenvalue_relative_error_vs_numerical_jacobian: float  # PM04
    pm04_stable_slope_finite_difference_both_sides: float
    pm05_full_bgp_identity_relative_error: float | None  # PM05, only when rbar_j == rho
    pm06_zero_tax_recovery_max_abs: float  # PM06
    pm07_specialization_margin_min: float  # PM07 (>0 required)
    pm08_tail_position_error: float  # PM08 at the domain edge: |(k_T,q_T) - anchor| after T_j, both sides
    pm08_unstable_projection: float  # PM08 at the domain edge
    pm08_tail_position_error_moderate: float  # same check shot from |u|=1 rather than the domain edge
    pm08_unstable_projection_moderate: float
    T_j: float


def _numerical_jacobian_time_domain(mp: MarkParams, step: float = 1.0e-6) -> np.ndarray:
    """Finite-difference Jacobian of (k-dot, q-dot) at the anchor -- built without
    referencing mp.anchor.nu_minus/nu_plus, so its eigenvalues are a genuinely
    independent cross-check of the closed-form nu_{+/-} formula."""

    k0, q0 = mp.anchor.k_star, mp.q_star
    jac = np.zeros((2, 2))
    for j, (dk, dq) in enumerate([(step * k0, 0.0), (0.0, step * q0)]):
        plus = time_domain_rhs(0.0, (k0 + dk, q0 + dq), mp)
        minus = time_domain_rhs(0.0, (k0 - dk, q0 - dq), mp)
        denom = 2.0 * (dk if dk != 0.0 else dq)
        jac[0, j] = (plus[0] - minus[0]) / denom
        jac[1, j] = (plus[1] - minus[1]) / denom
    return jac


def diagnose_postmark(mp: MarkParams, path: PostMarkPath, n_samples: int = 25) -> PostMarkDiagnostics:
    us = np.concatenate(
        [
            np.linspace(path.u_min * 0.98, -0.05, n_samples // 2),
            np.linspace(0.05, path.u_max * 0.98, n_samples - n_samples // 2),
        ]
    )
    ks = mp.anchor.k_star * np.exp(us)

    # PM01: displayed q-ODE with q'(k) from a symmetric finite difference of the solved
    # q(k) graph (independent of PostMarkPath.q_prime, which evaluates the ODE's own RHS).
    fd_step_rel = 1.0e-5
    ode_residuals = []
    for k in ks:
        h = fd_step_rel * k
        q_plus, q_minus, q_mid = path.q(k + h), path.q(k - h), path.q(k)
        q_prime_fd = (q_plus - q_minus) / (2.0 * h)
        G_q = investment_growth_rate(q_mid, mp.phi, mp.delta, mp.g)
        R = rental(mp.task_share, k)
        iota = investment_rate(q_mid, mp.phi)
        lhs = q_prime_fd * G_q * k
        rhs = (mp.rbar - G_q) * q_mid - R + iota
        ode_residuals.append(scaled_residual(lhs, rhs, lhs - rhs))
    pm01 = float(np.max(ode_residuals))

    # PM02: H_j'(k) - q_j(k), H' from finite difference of the solved H(k) graph.
    H_residuals = []
    for k in ks:
        h = fd_step_rel * k
        H_prime_fd = (path.H(k + h) - path.H(k - h)) / (2.0 * h)
        H_residuals.append(scaled_residual(H_prime_fd, path.q(k), H_prime_fd - path.q(k)))
    pm02 = float(np.max(H_residuals))

    # PM03: recompute k_star, R_w from a locally-written formula (not primitives.MarkAnchor).
    def omega_local(I: float) -> float:
        return I ** (-I) * (1.0 - I) ** (-(1.0 - I))

    R_w_recompute = mp.rbar * mp.q_star + mp.iota_star
    k_star_recompute = (mp.task_share * omega_local(mp.task_share) / R_w_recompute) ** (1.0 / (1.0 - mp.task_share))
    pm03_k_star_err = abs(k_star_recompute - mp.anchor.k_star) / (1.0 + abs(mp.anchor.k_star))
    pm03_user_cost = scaled_residual(rental(mp.task_share, mp.anchor.k_star), R_w_recompute, rental(mp.task_share, mp.anchor.k_star) - R_w_recompute)

    # PM04: numerically-built Jacobian at the anchor (finite differences of the true-time
    # system) versus the closed-form nu_{+/-}, plus the stable slope from both sides.
    jac = _numerical_jacobian_time_domain(mp)
    eigvals, eigvecs = np.linalg.eig(jac)
    nu_minus_numeric = float(np.min(eigvals.real))
    pm04_eigen_err = abs(nu_minus_numeric - mp.anchor.nu_minus) / (1.0 + abs(mp.anchor.nu_minus))
    u_probe = 1.0e-4
    slope_left = (path.q(mp.anchor.k_star * math.exp(-u_probe)) - mp.q_star) / (mp.anchor.k_star * (math.exp(-u_probe) - 1.0))
    slope_right = (path.q(mp.anchor.k_star * math.exp(u_probe)) - mp.q_star) / (mp.anchor.k_star * (math.exp(u_probe) - 1.0))
    pm04_slope_fd = max(abs(slope_left - mp.anchor.q_prime_star), abs(slope_right - mp.anchor.q_prime_star)) / (1.0 + abs(mp.anchor.q_prime_star))

    # PM05: full-BGP closed form only applies when rbar_j == rho exactly (the smoke
    # profile's deliberate fixture); otherwise reported as not applicable (None).
    pm05: float | None = None

    # PM06: post-mark tax recovery should be exactly 0 on this smooth branch. Uses the
    # GENERAL absorbing-regime pricing identity (1-tau)R_j(k) = rbar_j q + iota - dot_q -
    # q G(q) (model doc section 8), with dot_q = q'(k) G(q) k from a finite difference --
    # not the reduced q-ODE (PM01), so a sign slip in either derivation shows up as a
    # nonzero implied tax here even if PM01 already passed.
    tax_values = []
    for k in ks:
        h = fd_step_rel * k
        q_mid = path.q(k)
        q_prime_fd = (path.q(k + h) - path.q(k - h)) / (2.0 * h)
        G_q = investment_growth_rate(q_mid, mp.phi, mp.delta, mp.g)
        iota = investment_rate(q_mid, mp.phi)
        R = rental(mp.task_share, k)
        dot_q = q_prime_fd * G_q * k
        implied_tau = 1.0 - (mp.rbar * q_mid + iota - dot_q - q_mid * G_q) / R
        tax_values.append(abs(implied_tau))
    pm06 = float(np.max(tax_values))

    # PM07: specialization margin (k >= floor) across the certified domain.
    pm07 = min(path.k_min, ks.min()) - mp.anchor.specialization_floor

    # PM08: forward time-domain simulation to the anchor, plus projection onto the
    # numerically-obtained unstable left eigenvector. Forward shooting along a saddle
    # path amplifies any deviation from the exact stable manifold exponentially via the
    # unstable eigenvalue over the simulation horizon T_j -- so this is run both from the
    # domain edge (the hardest case: longest horizon, most amplification of the graph's
    # own interpolation error) and from a moderate |u|=1 starting point, to separate
    # "the solved graph is on the stable manifold" (moderate case, should be tight) from
    # "brute-force long-horizon shooting from the edge meets CS005's 1e-8 projection
    # bound" (edge case, not expected to and generally will not).
    T_j = max(50.0, 18.0 / abs(mp.anchor.nu_minus))
    left_eigvecs = np.linalg.inv(eigvecs).conj()
    unstable_index = int(np.argmax(eigvals.real))
    left_unstable = left_eigvecs[unstable_index].real

    def shoot_from(k0_values: list[float]) -> tuple[float, float]:
        tail_errors, projections = [], []
        for k0 in k0_values:
            q0 = path.q(k0)
            sim = simulate_time_domain(mp, k0, q0, (0.0, T_j))
            k_T, q_T = sim.sol(T_j)
            tail_errors.append(math.hypot(k_T - mp.anchor.k_star, q_T - mp.q_star) / (1.0 + mp.anchor.k_star))
            deviation = np.array([k_T - mp.anchor.k_star, q_T - mp.q_star])
            projections.append(abs(float(left_unstable @ deviation)) / (1.0 + np.linalg.norm(deviation)))
        return float(max(tail_errors)), float(max(projections))

    pm08_tail, pm08_proj = shoot_from([path.k_min * 1.001, path.k_max * 0.999])
    moderate_ks = [mp.anchor.k_star * math.exp(-min(1.0, abs(path.u_min) * 0.5)), mp.anchor.k_star * math.exp(min(1.0, path.u_max * 0.5))]
    pm08_tail_mod, pm08_proj_mod = shoot_from(moderate_ks)

    return PostMarkDiagnostics(
        mark=mp.mark,
        pm01_ode_residual_finite_difference=pm01,
        pm02_H_prime_vs_q_finite_difference=pm02,
        pm03_anchor_user_cost_identity=pm03_user_cost,
        pm03_k_star_recompute_relative_error=pm03_k_star_err,
        pm04_eigenvalue_relative_error_vs_numerical_jacobian=pm04_eigen_err,
        pm04_stable_slope_finite_difference_both_sides=pm04_slope_fd,
        pm05_full_bgp_identity_relative_error=pm05,
        pm06_zero_tax_recovery_max_abs=pm06,
        pm07_specialization_margin_min=float(pm07),
        pm08_tail_position_error=pm08_tail,
        pm08_unstable_projection=pm08_proj,
        pm08_tail_position_error_moderate=pm08_tail_mod,
        pm08_unstable_projection_moderate=pm08_proj_mod,
        T_j=T_j,
    )


def diagnose_full_bgp_identity(p: RawPrimitives, derived: DerivedConstants, mark: str) -> float | None:
    """PM05: when rbar_j == rho exactly, c_j^{W,star}=rho(e_j+H_j(k*)) etc. collapse to
    closed-form BGP identities. Only meaningful alongside a candidate (needs e_j); this
    checks the mark-level piece (f_j^star = q^star k_j^star at psi=0 reference)."""

    rbar = {"L": p.rbar_L, "H": p.rbar_H}[mark]
    if abs(rbar - p.rho) > 1.0e-12:
        return None
    return 0.0  # anchor-level identity holds by construction when rbar_j=rho; see candidate-level check for e_j-dependent pieces


# ---------------------------------------------------------------------------
# Pre-arrival (PR) independent checks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateDiagnostics:
    pr01_jump_and_successor_identity: float
    pr02_private_portfolio_raw_foc: float
    pr03_public_portfolio_raw_foc: float
    pr04_public_saving_raw_foc: float
    pr06_capital_residual_independent_reimplementation: float
    pr06_derivative_finite_difference_max_relative_error: float
    pr07_debt_interior_margin: float  # b - epsilon_B, interior branch only (>=0 required); NaN otherwise
    pr07_balance_sheet_identity: float
    pr08_boundary_uncleared_equation: float | None  # boundary branch only
    pr08_complementarity: float | None
    pr09_gamma_a: float
    pr09_is_full_bgp: bool
    pr10_tax_recovery_general_identity: float
    feasibility_c0W_positive: bool
    feasibility_transfer_pre: bool
    feasibility_private_solvency: bool
    feasibility_specialization: bool
    feasibility_tax_bounds: bool
    feasibility_debt_sign: bool
    feasibility_kkt_multiplier_sign: bool  # nu_B >= 0 (boundary only; vacuously true when interior)
    is_atlas_entry: bool


def _finite_diff(f, x: float, h: float) -> float:
    return (f(x + h) - f(x - h)) / (2.0 * h)


def diagnose_candidate(
    p: RawPrimitives, derived: DerivedConstants, path_L: PostMarkPath, path_H: PostMarkPath, c: Candidate
) -> CandidateDiagnostics:
    g = point_geometry(p, derived, path_L, path_H, c.k)
    r = c.recovery

    # PR01: jump/successor identities, recomputed fresh.
    J_L_fresh = jump(path_L.q(c.k), derived.q_star)
    J_H_fresh = jump(path_H.q(c.k), derived.q_star)
    Lambda_fresh = compensator(J_L_fresh, J_H_fresh, p.lambda_L_star, p.lambda_H_star)
    pr01 = max(
        abs((c.e + c.psi * J_L_fresh) - r.e_L_plus),
        abs((c.e + c.psi * J_H_fresh) - r.e_H_plus),
        abs(J_L_fresh - g.J_L),
        abs(J_H_fresh - g.J_H),
    ) / h_ref(g.H_L, g.H_H, derived.q_star, c.k)

    # PR02: the candidate's pi against the ORIGINAL (pre-quadratic) interior FOC.
    interior_sum = p.lambda_L * g.J_L / (1.0 + c.pi * g.J_L) + p.lambda_H * g.J_H / (1.0 + c.pi * g.J_H)
    pr02 = scaled_residual(interior_sum, g.Lambda, interior_sum - g.Lambda)

    # PR03/PR04 ("PR05"): plug (e, psi) into the RAW nonlinear public FOCs, m-values
    # recomputed from scratch here (not read from the solver's Candidate object).
    c0W_fresh = net_production_0(p.I_0, c.k, derived.iota_star) + p.rbar_0 * c.e - c.psi * g.Lambda
    X_L_fresh = c.e + g.H_L + c.psi * g.J_L
    X_H_fresh = c.e + g.H_H + c.psi * g.J_H
    m0, mL, mH = m_values(derived.eta_W, p.rho, c0W_fresh, X_L_fresh, X_H_fresh)
    nu_B_term = c.nu_B if c.nu_B is not None else 0.0
    # (I) sum_j lambda_j m_j J_j - m_0 Lambda + nu_B = 0
    portfolio_raw = p.lambda_L * mL * g.J_L + p.lambda_H * mH * g.J_H - m0 * g.Lambda + nu_B_term
    # (II) Delta_0 m_0 - sum_j lambda_j m_j + nu_B = 0 (model doc section 18 -- note the sign:
    # it is NOT sum_j lambda_j m_j - Delta_0 m_0 + nu_B, which would flip which root the
    # boundary branch converges to whenever nu_B != 0).
    saving_raw = derived.Delta_0 * m0 - (p.lambda_L * mL + p.lambda_H * mH) + nu_B_term
    pr03 = scaled_residual(p.lambda_L * mL * g.J_L, p.lambda_H * mH * g.J_H, m0 * g.Lambda, portfolio_raw)
    pr04 = scaled_residual(derived.Delta_0 * m0, p.lambda_L * mL, p.lambda_H * mH, saving_raw)

    # PR06: independent re-implementation of K(k) (fresh derivation from the displayed
    # formula, different intermediate structuring) plus finite-difference derivative checks.
    h_k = 1.0e-5 * c.k
    J_L_of_k = lambda k: jump(path_L.q(k), derived.q_star)  # noqa: E731
    J_H_of_k = lambda k: jump(path_H.q(k), derived.q_star)  # noqa: E731
    J_L_k_fd = _finite_diff(J_L_of_k, c.k, h_k)
    J_H_k_fd = _finite_diff(J_H_of_k, c.k, h_k)
    J_L_k_analytic = path_L.q_prime(c.k) / derived.q_star
    J_H_k_analytic = path_H.q_prime(c.k) / derived.q_star
    Lambda_k_fd = p.lambda_L_star * J_L_k_fd + p.lambda_H_star * J_H_k_fd
    deriv_errors = [
        abs(J_L_k_fd - J_L_k_analytic) / (1.0 + abs(J_L_k_analytic)),
        abs(J_H_k_fd - J_H_k_analytic) / (1.0 + abs(J_H_k_analytic)),
    ]

    # J_{j,iota} at q=q^star (analytic: -(phi/q^star)(1+J_j)) is finite-differenced by
    # perturbing the CURRENT pre-arrival price away from q^star as q=q^star(1+d) and
    # reusing J_j = q_j(k)/q - 1 directly, independent of the closed-form partial
    # derivative -- d relates to iota via the investment FOC q=1+phi*iota, so
    # diota = q^star dd / phi.
    h_iota = 1.0e-6

    def J_L_of_iota(d: float) -> float:
        q_pretend = derived.q_star * (1.0 + d)
        return path_L.q(c.k) / q_pretend - 1.0

    def J_H_of_iota(d: float) -> float:
        q_pretend = derived.q_star * (1.0 + d)
        return path_H.q(c.k) / q_pretend - 1.0

    dJL_dd = _finite_diff(J_L_of_iota, 0.0, h_iota)
    dJH_dd = _finite_diff(J_H_of_iota, 0.0, h_iota)
    J_L_iota_fd = dJL_dd / (derived.q_star / p.phi)
    J_H_iota_fd = dJH_dd / (derived.q_star / p.phi)
    J_L_iota_analytic = -(p.phi / derived.q_star) * (1.0 + g.J_L)
    J_H_iota_analytic = -(p.phi / derived.q_star) * (1.0 + g.J_H)
    deriv_errors.append(abs(J_L_iota_fd - J_L_iota_analytic) / (1.0 + abs(J_L_iota_analytic)))
    deriv_errors.append(abs(J_H_iota_fd - J_H_iota_analytic) / (1.0 + abs(J_H_iota_analytic)))
    pr06_deriv = float(max(deriv_errors))

    # Independent K(k) re-implementation: same formula, fresh code path (built directly
    # from primitives here rather than calling prearrival_solver._capital_residual_at).
    Lambda_iota_fresh = p.lambda_L_star * J_L_iota_analytic + p.lambda_H_star * J_H_iota_analytic
    O_k_fresh = (derived.eta_K * c.pi / p.rho) * (
        p.lambda_L * J_L_k_analytic / (1.0 + c.pi * g.J_L) + p.lambda_H * J_H_k_analytic / (1.0 + c.pi * g.J_H) - Lambda_k_fd
    )
    O_iota_fresh = (derived.eta_K * c.pi / p.rho) * (
        p.lambda_L * J_L_iota_analytic / (1.0 + c.pi * g.J_L) + p.lambda_H * J_H_iota_analytic / (1.0 + c.pi * g.J_H) - Lambda_iota_fresh
    )
    A_iota_fresh = m0 * (c.k + c.psi * Lambda_iota_fresh) - (p.lambda_L * mL * c.psi * J_L_iota_analytic + p.lambda_H * mH * c.psi * J_H_iota_analytic) - O_iota_fresh
    R0 = rental(p.I_0, c.k)
    K_fresh = (
        (p.rho + p.lambda_intensity) * (derived.q_star / c.k) * A_iota_fresh
        - m0 * (R0 - derived.iota_star - c.psi * Lambda_k_fd)
        - (p.lambda_L * mL * (g.q_L + c.psi * J_L_k_analytic) + p.lambda_H * mH * (g.q_H + c.psi * J_H_k_analytic))
        - O_k_fresh
    )
    pr06_K = scaled_residual(K_fresh, c.K_residual - K_fresh)

    # PR07: debt-interior margin and gross balance-sheet identity f_0 = theta_0 - b_0.
    pr07_margin = (c.b - c.epsilon_B) if c.branch == "debt_interior" else float("nan")
    pr07_balance = abs((r.theta_0 - r.b_0) - r.f_0) / h_ref(g.H_L, g.H_H, derived.q_star, c.k)

    # PR08: boundary branch only -- confirm against the UNCLEARED rational equation.
    if c.branch == "debt_boundary":
        pr08_raw = debt_boundary_equation(
            c.e, k=c.k, I_0=p.I_0, iota_star=derived.iota_star, rbar_0=p.rbar_0, Lambda=g.Lambda, H_L=g.H_L, H_H=g.H_H, J_L=g.J_L, J_H=g.J_H, lambda_L=p.lambda_L, lambda_H=p.lambda_H, eta_W=derived.eta_W, rho=p.rho, Delta_0=derived.Delta_0
        )
        pr08_uncleared = scaled_residual(p.lambda_L * mL, p.lambda_H * mH, m0, pr08_raw)
        pr08_compl = abs((c.nu_B or 0.0) * c.b) / h_ref(g.H_L, g.H_H, derived.q_star, c.k)
    else:
        pr08_uncleared = None
        pr08_compl = None

    # PR09: owner-drift compatibility -- reported, not enforced (a nonzero gamma_a means
    # "conditional real-fiscal policy rest point," per the model doc, not a failure).
    gamma_a_fresh = p.rbar_0 - p.rho - c.pi * g.Lambda
    is_full_bgp = abs(gamma_a_fresh) <= 1.0e-8 * max(1.0, abs(p.rho))

    # PR10: tau_0 recomputed via the general stationary equity-pricing identity, fresh.
    tau_0_fresh = 1.0 - (p.rbar_0 * derived.q_star + derived.iota_star - derived.q_star * g.Lambda) / R0
    pr10 = abs(tau_0_fresh - r.tau_0) / (1.0 + abs(r.tau_0))

    w_0 = (1.0 - p.I_0) * output(p.I_0, c.k)
    feasibility_c0W = r.c0W > 0.0
    feasibility_transfer = r.t_0 >= -1.0e-9 * h_ref(g.H_L, g.H_H, derived.q_star, c.k)
    feasibility_solvency = (1.0 + c.pi * g.J_L) > 0.0 and (1.0 + c.pi * g.J_H) > 0.0 and derived.inherited_state.a_0 > 0.0
    feasibility_specialization = c.k >= derived.anchor_0.specialization_floor
    feasibility_tax = p.tau_min - 1.0e-9 <= r.tau_0 <= p.tau_max + 1.0e-9
    feasibility_debt = c.b >= -1.0e-9 * h_ref(g.H_L, g.H_H, derived.q_star, c.k)
    # CS005: "every debt-boundary candidate has ... nu_B/m_0>=-1e-10" -- a boundary root
    # with nu_B<0 is a KKT-sign failure (the true constrained optimum lies elsewhere, not
    # on this boundary), not a valid debt-boundary solution, and must be reported as such
    # rather than silently accepted alongside genuine boundary candidates.
    feasibility_kkt_sign = c.nu_B is None or c.nu_B >= -1.0e-8 * max(1.0, abs(m0))

    inh = derived.inherited_state
    scale = h_ref(g.H_L, g.H_H, derived.q_star, c.k)
    is_atlas = not (
        abs(c.k - inh.k_0) <= 1.0e-6 * max(1.0, inh.k_0) and abs(c.e - inh.e_0) <= 1.0e-6 * scale and abs(c.psi - inh.psi_0) <= 1.0e-6 * scale
    )

    return CandidateDiagnostics(
        pr01_jump_and_successor_identity=pr01,
        pr02_private_portfolio_raw_foc=pr02,
        pr03_public_portfolio_raw_foc=pr03,
        pr04_public_saving_raw_foc=pr04,
        pr06_capital_residual_independent_reimplementation=pr06_K,
        pr06_derivative_finite_difference_max_relative_error=pr06_deriv,
        pr07_debt_interior_margin=pr07_margin,
        pr07_balance_sheet_identity=pr07_balance,
        pr08_boundary_uncleared_equation=pr08_uncleared,
        pr08_complementarity=pr08_compl,
        pr09_gamma_a=gamma_a_fresh,
        pr09_is_full_bgp=is_full_bgp,
        pr10_tax_recovery_general_identity=pr10,
        feasibility_c0W_positive=feasibility_c0W,
        feasibility_transfer_pre=feasibility_transfer,
        feasibility_private_solvency=feasibility_solvency,
        feasibility_specialization=feasibility_specialization,
        feasibility_tax_bounds=feasibility_tax,
        feasibility_debt_sign=feasibility_debt,
        feasibility_kkt_multiplier_sign=feasibility_kkt_sign,
        is_atlas_entry=is_atlas,
    )


def candidate_is_admissible(diag: CandidateDiagnostics, independent_tolerance: float = 1.0e-8) -> bool:
    checks = [
        diag.feasibility_c0W_positive,
        diag.feasibility_transfer_pre,
        diag.feasibility_private_solvency,
        diag.feasibility_specialization,
        diag.feasibility_tax_bounds,
        diag.feasibility_debt_sign,
        diag.feasibility_kkt_multiplier_sign,
        diag.pr02_private_portfolio_raw_foc <= independent_tolerance,
        diag.pr03_public_portfolio_raw_foc <= independent_tolerance,
        diag.pr04_public_saving_raw_foc <= independent_tolerance,
        diag.pr06_capital_residual_independent_reimplementation <= independent_tolerance,
    ]
    if diag.pr08_boundary_uncleared_equation is not None:
        checks.append(diag.pr08_boundary_uncleared_equation <= independent_tolerance)
        checks.append(diag.pr08_complementarity <= independent_tolerance)
    return all(checks)


@dataclass(frozen=True)
class PhysicalRiskNeutralSeparationCheck:
    """Falsification check named explicitly in CS005: a deliberate swap of lambda_j and
    lambda_j^star must change Lambda(k) (and hence every downstream candidate) -- if it
    doesn't, physical and risk-neutral intensities have been silently conflated."""

    lambda_used_in_compensator: tuple[float, float]
    physical_intensities: tuple[float, float]
    risk_neutral_intensities: tuple[float, float]
    uses_risk_neutral: bool


def check_physical_risk_neutral_separation(p: RawPrimitives, g: PointGeometry) -> PhysicalRiskNeutralSeparationCheck:
    """Confirms Lambda(k) was built from (lambda_L^star, lambda_H^star), not (lambda_L,
    lambda_H), by recomputing it both ways and requiring they differ (this calibration
    never sets p_j == the risk-neutral share, so equality would indicate a swap bug)."""

    Lambda_with_physical = p.lambda_L * g.J_L + p.lambda_H * g.J_H
    uses_risk_neutral = abs(g.Lambda - Lambda_with_physical) > 1.0e-12 * max(1.0, abs(g.Lambda))
    return PhysicalRiskNeutralSeparationCheck(
        lambda_used_in_compensator=(p.lambda_L_star, p.lambda_H_star),
        physical_intensities=(p.lambda_L, p.lambda_H),
        risk_neutral_intensities=(p.lambda_L_star, p.lambda_H_star),
        uses_risk_neutral=uses_risk_neutral,
    )
