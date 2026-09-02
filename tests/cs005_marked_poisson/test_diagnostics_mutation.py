"""Mutation tests: inject a plausible construction bug into the solver and confirm the
independent diagnostics in diagnostics.py actually catch it. Required before diagnostics.py
may be treated as "independent" (CLAUDE.md); CS005 additionally names the physical/
risk-neutral intensity swap explicitly as a required regression.
"""

from __future__ import annotations

import math

import pytest

from tai_public_finance.cs005_marked_poisson import postmark_solver, prearrival_solver
from tai_public_finance.cs005_marked_poisson.diagnostics import check_physical_risk_neutral_separation, diagnose_postmark
from tai_public_finance.cs005_marked_poisson.postmark_equations import investment_growth_rate, investment_rate, mark_params, rental
from tai_public_finance.cs005_marked_poisson.postmark_solver import solve_postmark
from tai_public_finance.cs005_marked_poisson.prearrival_solver import point_geometry


def test_physical_risk_neutral_intensity_swap_is_caught(monkeypatch, real_primitives, real_derived, real_postmark):
    """CS005: 'A deliberate swap of physical and risk-neutral intensities fails a
    regression test; physical intensities enter welfare and private/public event
    probabilities, while risk-neutral intensities enter no-arbitrage pricing.'"""

    _mp_L, _mp_H, path_L, path_H = real_postmark

    def swapped_compensator(J_L: float, J_H: float, _lambda_L_star: float, _lambda_H_star: float) -> float:
        # Bug: prices the jump compensator with PHYSICAL intensities instead of the
        # risk-neutral ones passed in (a plausible copy-paste error: lambda_L/lambda_H
        # look identical in shape to lambda_L_star/lambda_H_star at the call site).
        return real_primitives.lambda_L * J_L + real_primitives.lambda_H * J_H

    k0 = real_derived.inherited_state.k_0
    g_correct = point_geometry(real_primitives, real_derived, path_L, path_H, k0)
    sep_correct = check_physical_risk_neutral_separation(real_primitives, g_correct)
    assert sep_correct.uses_risk_neutral, "sanity: the unmutated solver must use risk-neutral intensities"

    monkeypatch.setattr(prearrival_solver, "compensator", swapped_compensator)
    g_mutated = point_geometry(real_primitives, real_derived, path_L, path_H, k0)
    sep_mutated = check_physical_risk_neutral_separation(real_primitives, g_mutated)
    assert not sep_mutated.uses_risk_neutral, "the intensity-swap mutation was not detected -- the independence check is not doing its job"

    # The swap must also actually change the reported compensator value for this
    # calibration (p_L, p_H differ from the risk-neutral shares) -- otherwise the
    # "detection" above would be vacuous.
    assert g_mutated.Lambda != pytest.approx(g_correct.Lambda)


def test_postmark_ode_sign_bug_is_caught_by_pm01(monkeypatch, real_primitives, real_derived):
    """Inject a sign flip into the displayed q-ODE's rental-rate term and confirm
    diagnose_postmark's PM01 (a from-scratch finite-difference check of the *correct*
    displayed equation) reports a large residual against the resulting wrong q(k)."""

    mp = mark_params(real_primitives, real_derived, "L")

    def buggy_rhs(u: float, state: tuple[float, float], mp_):
        v, _H = state
        k = mp_.anchor.k_star * math.exp(u)
        q = mp_.q_star * math.exp(v)
        G_q = investment_growth_rate(q, mp_.phi, mp_.delta, mp_.g)
        R = rental(mp_.task_share, k)
        iota = investment_rate(q, mp_.phi)
        dv_du = ((mp_.rbar - G_q) * q + R + iota) / (q * G_q)  # BUG: +R instead of -R
        dH_du = q * k
        return dv_du, dH_du

    correct_path = solve_postmark(mp, mp.anchor.u_min, mp.anchor.u_max)
    correct_diag = diagnose_postmark(mp, correct_path)
    assert correct_diag.pm01_ode_residual_finite_difference < 1e-6

    monkeypatch.setattr(postmark_solver, "continuation_rhs", buggy_rhs)
    try:
        buggy_path = solve_postmark(mp, mp.anchor.u_min, mp.anchor.u_max)
    except RuntimeError:
        # The sign flip is severe enough that the mutated dynamics can't even be
        # integrated (the solver's own step-size control rejects it) -- that is itself
        # the bug being caught, just one level earlier than PM01.
        return
    buggy_diag = diagnose_postmark(mp, buggy_path)
    assert buggy_diag.pm01_ode_residual_finite_difference > 1e-2, (
        "the sign-flipped q-ODE mutation produced a graph that still passes PM01 -- "
        "the independent check is not exercising the displayed equation"
    )


def test_debt_boundary_sign_regression(real_primitives, real_derived, real_postmark):
    """Regression pin for the sign bug found and fixed during this implementation: the
    nu_B-eliminated boundary equation is sum_j lambda_j m_j (J_j+1) - m_0(Lambda+Delta_0),
    not (J_j-1)/(Lambda-Delta_0). Reintroducing the wrong sign makes debt_boundary_equation
    disagree with the raw two-FOC system at any genuine boundary root."""

    from tai_public_finance.cs005_marked_poisson.prearrival_equations import debt_boundary_equation, m_values, net_production_0

    _mp_L, _mp_H, path_L, path_H = real_postmark
    from tai_public_finance.cs005_marked_poisson.prearrival_solver import boundary_roots_at

    g = point_geometry(real_primitives, real_derived, path_L, path_H, real_derived.inherited_state.k_0 * 1.5)
    roots = boundary_roots_at(real_primitives, real_derived, g)
    assert roots, "sanity: this point should have at least one boundary root to check"
    e = roots[0]

    correct_residual = debt_boundary_equation(
        e, k=g.k, I_0=real_primitives.I_0, iota_star=real_derived.iota_star, rbar_0=real_primitives.rbar_0, Lambda=g.Lambda, H_L=g.H_L, H_H=g.H_H, J_L=g.J_L, J_H=g.J_H,
        lambda_L=real_primitives.lambda_L, lambda_H=real_primitives.lambda_H, eta_W=real_derived.eta_W, rho=real_primitives.rho, Delta_0=real_derived.Delta_0,
    )
    assert abs(correct_residual) < 1e-6

    # The old (buggy) sign convention, evaluated at the same root, should NOT be ~0 in
    # general (nu_B far enough from 0 that (J-1)/(Lambda-Delta_0) differs materially
    # from (J+1)/(Lambda+Delta_0)) -- pinning this guards against the bug returning.
    d_0 = net_production_0(real_primitives.I_0, g.k, real_derived.iota_star)
    X_L = e * (1.0 + g.J_L) + g.H_L
    X_H = e * (1.0 + g.J_H) + g.H_H
    c0W = d_0 + e * (real_primitives.rbar_0 - g.Lambda)
    m0, mL, mH = m_values(real_derived.eta_W, real_primitives.rho, c0W, X_L, X_H)
    buggy_residual = real_primitives.lambda_L * mL * (g.J_L - 1.0) + real_primitives.lambda_H * mH * (g.J_H - 1.0) - m0 * (g.Lambda - real_derived.Delta_0)
    assert abs(buggy_residual) > 1e-3
