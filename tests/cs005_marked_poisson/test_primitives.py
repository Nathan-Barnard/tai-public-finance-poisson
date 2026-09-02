from __future__ import annotations

import math

import pytest

from tai_public_finance.cs005_marked_poisson.primitives import (
    Omega,
    RawPrimitives,
    compute_derived_constants,
    run_fingerprint,
)


def test_smoke_derived_constants_match_cs005_worked_values(smoke_primitives, smoke_derived):
    # CS005 v0.7's smoke profile section states q^star=1.1735108709918103 and
    # iota^star=0.08675543549590514 as regression targets computed from phi=2.0,
    # delta=0.06, g=0.02.
    assert smoke_derived.q_star == pytest.approx(1.1735108709918103, abs=1e-15)
    assert smoke_derived.iota_star == pytest.approx(0.08675543549590514, abs=1e-15)


def test_derived_constants_are_computed_not_hand_entered(smoke_primitives, smoke_derived):
    p, d = smoke_primitives, smoke_derived
    assert d.q_star == pytest.approx(math.exp(p.phi * (p.delta + p.g)), abs=1e-15)
    assert d.iota_star == pytest.approx((d.q_star - 1.0) / p.phi, abs=1e-15)
    assert d.eta_W == pytest.approx(p.chi * p.omega_W, abs=1e-15)
    assert d.eta_K == pytest.approx((1.0 - p.chi) * p.omega_K, abs=1e-15)
    assert d.Delta_0 == pytest.approx(p.rho + p.lambda_intensity - p.rbar_0, abs=1e-15)
    for mark, task_share, rbar in (("L", p.I_L, p.rbar_L), ("H", p.I_H, p.rbar_H)):
        a = d.anchors[mark]
        R_w = rbar * d.q_star + d.iota_star
        assert a.R_w == pytest.approx(R_w, abs=1e-15)
        assert a.k_star == pytest.approx((task_share * Omega(task_share) / R_w) ** (1.0 / (1.0 - task_share)), abs=1e-12)


def test_physical_intensities_never_derived_from_risk_neutral(real_primitives):
    p = real_primitives
    assert p.lambda_L == pytest.approx(p.lambda_intensity * p.p_L)
    assert p.lambda_H == pytest.approx(p.lambda_intensity * p.p_H)
    # The risk-neutral intensities are direct profile inputs, deliberately distinct
    # from a physical-probability-weighted split of lambda_intensity.
    assert p.lambda_L_star != pytest.approx(p.lambda_intensity * p.p_L)
    assert p.lambda_H_star != pytest.approx(p.lambda_intensity * p.p_H)


@pytest.mark.parametrize(
    "mutate,message",
    [
        (lambda raw: raw["parameters"].__setitem__("I_L", 0.9), "I_0 < I_L < I_H"),
        (lambda raw: raw["parameters"].__setitem__("rho", -0.01), "rho"),
        (lambda raw: raw["parameters"].__setitem__("p_H", 0.9), "p_L \\+ p_H"),
        (lambda raw: raw["parameters"].__setitem__("rbar_L", 0.0), "rbar_0, rbar_L, rbar_H"),
        (lambda raw: raw["parameters"].__setitem__("tau_max", 1.5), "tau_min"),
        (lambda raw: raw["parameters"].__setitem__("b_min", 1.0), "b_min"),
    ],
)
def test_invalid_primitive_mutations_are_rejected(smoke_primitives, mutate, message):
    raw = dict(smoke_primitives.raw)
    raw = {**raw, "parameters": dict(raw["parameters"])}
    mutate(raw)
    with pytest.raises(ValueError, match=message):
        RawPrimitives.from_dict(raw)


def test_inherited_state_smoke_is_zero_debt_protected(smoke_derived):
    inh = smoke_derived.inherited_state
    assert inh.e_0 == 0.0
    assert inh.psi_0 == 0.0
    assert inh.b_0 == 0.0
    assert inh.theta_0 == pytest.approx(smoke_derived.q_star * inh.k_0)


def test_inherited_state_real_has_one_year_output_debt(real_primitives, real_derived):
    from tai_public_finance.cs005_marked_poisson.postmark_equations import output

    inh = real_derived.inherited_state
    y0 = output(real_primitives.I_0, inh.k_0)
    assert inh.theta_0 == 0.0
    assert inh.b_0 == pytest.approx(y0, rel=1e-12)
    assert inh.f_0 == pytest.approx(-y0, rel=1e-12)
    assert inh.e_0 == pytest.approx(-y0 - real_derived.q_star * inh.k_0, rel=1e-12)


def test_run_fingerprint_is_deterministic_and_sensitive_to_inputs(smoke_primitives):
    tolerances = {"independent_tolerance": 1e-8}
    extra = {"k_grid_points": 300}
    fp1 = run_fingerprint(smoke_primitives, tolerances, extra)
    fp2 = run_fingerprint(smoke_primitives, tolerances, extra)
    assert fp1 == fp2
    assert len(fp1) == 64

    fp_different_tolerance = run_fingerprint(smoke_primitives, {"independent_tolerance": 1e-6}, extra)
    assert fp_different_tolerance != fp1

    fp_different_grid = run_fingerprint(smoke_primitives, tolerances, {"k_grid_points": 301})
    assert fp_different_grid != fp1


def test_compute_derived_constants_rejects_nonpositive_world_user_cost():
    raw = {
        "primitive_set_id": "P-TEST-BAD",
        "spec_id": "CS005",
        "spec_version": "0.7",
        "inherited_state_convention": "smoke_protected_zero_debt",
        "parameters": {
            # g very negative relative to delta makes q_star=exp(phi(delta+g)) < 1, hence
            # iota_star < 0; combined with a small rbar_L this drives R_w = rbar*q_star +
            # iota_star negative, which _build_mark_anchor must reject rather than
            # silently take a fractional power of a negative number.
            "rho": 0.04, "g": -0.1, "delta": 0.06, "phi": 2.0, "chi": 0.8,
            "omega_W": 1.0, "omega_K": 1.0, "I_0": 0.2, "I_L": 0.3, "I_H": 0.4,
            "lambda_intensity": 0.02, "p_L": 0.5, "p_H": 0.5,
            "lambda_L_star": 0.008, "lambda_H_star": 0.012,
            "rbar_0": 0.04, "rbar_L": 0.04, "rbar_H": 0.04,
            "gamma_C": 0.5, "tau_min": 0.0, "tau_max": 1.0, "t_min": 0.0, "b_min": 0.0,
        },
        "provenance": {"source": "test"},
    }
    p = RawPrimitives.from_dict(raw)
    q_star = math.exp(p.phi * (p.delta + p.g))
    assert q_star < 1.0  # sanity: this fixture really does produce iota_star < 0
    with pytest.raises(ValueError, match="orld user cost"):
        compute_derived_constants(p)
