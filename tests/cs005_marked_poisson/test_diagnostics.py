from __future__ import annotations

import pytest

from tai_public_finance.cs005_marked_poisson.diagnostics import (
    check_physical_risk_neutral_separation,
    diagnose_candidate,
    diagnose_postmark,
)
from tai_public_finance.cs005_marked_poisson.prearrival_solver import enumerate_with_domain_expansion, point_geometry

_TIGHT = 1e-6  # generous relative to the 1e-10..1e-16 residuals actually observed


def test_postmark_diagnostics_pass_at_high_precision(real_postmark):
    mp_L, mp_H, path_L, path_H = real_postmark
    for mp, path in ((mp_L, path_L), (mp_H, path_H)):
        pm = diagnose_postmark(mp, path)
        assert pm.pm01_ode_residual_finite_difference < _TIGHT
        assert pm.pm02_H_prime_vs_q_finite_difference < _TIGHT
        assert pm.pm03_anchor_user_cost_identity < _TIGHT
        assert pm.pm03_k_star_recompute_relative_error < _TIGHT
        assert pm.pm04_eigenvalue_relative_error_vs_numerical_jacobian < _TIGHT
        assert pm.pm04_stable_slope_finite_difference_both_sides < 1e-4
        assert pm.pm06_zero_tax_recovery_max_abs < _TIGHT
        assert pm.pm07_specialization_margin_min > 0.0


def test_smoke_profile_full_bgp_fixture_has_matching_intensities_at_anchor(smoke_primitives):
    # The smoke profile sets rbar_0=rbar_L=rbar_H=rho=0.04 exactly so a full-BGP
    # closed-form cross-check is available -- this is a fixture property, not a
    # numerical result, but worth pinning so a future edit can't silently break it.
    p = smoke_primitives
    assert p.rbar_0 == pytest.approx(p.rho)
    assert p.rbar_L == pytest.approx(p.rho)
    assert p.rbar_H == pytest.approx(p.rho)


def test_candidate_diagnostics_pass_at_high_precision_for_every_found_root(real_primitives, real_derived, real_postmark):
    _mp_L, _mp_H, path_L, path_H = real_postmark
    result, path_L, path_H = enumerate_with_domain_expansion(real_primitives, real_derived, path_L, path_H, k_grid_points=300)
    assert result.candidates
    for c in result.candidates:
        diag = diagnose_candidate(real_primitives, real_derived, path_L, path_H, c)
        assert diag.pr01_jump_and_successor_identity < _TIGHT
        assert diag.pr02_private_portfolio_raw_foc < _TIGHT
        assert diag.pr03_public_portfolio_raw_foc < _TIGHT
        assert diag.pr04_public_saving_raw_foc < _TIGHT
        assert diag.pr06_capital_residual_independent_reimplementation < _TIGHT
        assert diag.pr06_derivative_finite_difference_max_relative_error < 1e-4
        assert diag.pr07_balance_sheet_identity < _TIGHT
        assert diag.pr10_tax_recovery_general_identity < _TIGHT
        if c.branch == "debt_boundary":
            assert diag.pr08_boundary_uncleared_equation < _TIGHT
            assert diag.pr08_complementarity < _TIGHT
        else:
            assert diag.pr08_boundary_uncleared_equation is None


def test_gamma_a_is_reported_not_enforced(real_primitives, real_derived, real_postmark):
    _mp_L, _mp_H, path_L, path_H = real_postmark
    result, path_L, path_H = enumerate_with_domain_expansion(real_primitives, real_derived, path_L, path_H, k_grid_points=300)
    diags = [diagnose_candidate(real_primitives, real_derived, path_L, path_H, c) for c in result.candidates]
    # rbar_0 != rho for the real profile, so a generic candidate should NOT land on
    # gamma_a=0 -- if every candidate here claimed is_full_bgp, that would suggest the
    # check is a no-op rather than a real evaluation.
    assert any(not d.pr09_is_full_bgp for d in diags)


def test_negative_nu_B_boundary_candidate_is_flagged_inadmissible(real_primitives, real_derived, real_postmark):
    # CS005: "every debt-boundary candidate has ... nu_B/m_0>=-1e-10" -- a boundary root
    # with nu_B<0 is a KKT-sign failure, not a valid solution, and candidate_is_admissible
    # must say so rather than silently accepting it alongside genuine boundary roots.
    _mp_L, _mp_H, path_L, path_H = real_postmark
    result, path_L, path_H = enumerate_with_domain_expansion(real_primitives, real_derived, path_L, path_H, k_grid_points=300)
    negative_nu_B = [c for c in result.candidates if c.branch == "debt_boundary" and c.nu_B is not None and c.nu_B < -1e-6]
    assert negative_nu_B, "sanity: this profile/grid should surface at least one negative-nu_B boundary root to check"
    for c in negative_nu_B:
        diag = diagnose_candidate(real_primitives, real_derived, path_L, path_H, c)
        assert not diag.feasibility_kkt_multiplier_sign
        from tai_public_finance.cs005_marked_poisson.diagnostics import candidate_is_admissible

        assert not candidate_is_admissible(diag)


def test_physical_risk_neutral_separation_holds_by_default(real_primitives, real_derived, real_postmark):
    _mp_L, _mp_H, path_L, path_H = real_postmark
    g = point_geometry(real_primitives, real_derived, path_L, path_H, real_derived.inherited_state.k_0)
    sep = check_physical_risk_neutral_separation(real_primitives, g)
    assert sep.uses_risk_neutral
