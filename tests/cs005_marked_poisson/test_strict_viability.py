"""W5 strict fiscal-viability tests: the frontier bounds, the constant-tax witness,
the three-label classification, mutation tests (tightening/weakening the frontier must
flip the pass flag), and the candidate-level admissibility wiring."""

from __future__ import annotations

import math

import pytest

from tai_public_finance.cs005_marked_poisson.postmark_equations import mark_params, rental
from tai_public_finance.cs005_marked_poisson.prearrival_solver import Candidate
from tai_public_finance.cs005_marked_poisson.prearrival_equations import Recovery
from tai_public_finance.cs005_marked_poisson import strict_viability as sv


# ---------------------------------------------------------------------------
# Unit: the capital-rescaling identity the witness family rests on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tau", [0.0, 0.15, 0.4, 0.75])
@pytest.mark.parametrize("task_share", [0.22, 0.32, 0.46])
def test_constant_tax_rescaling_identity(tau, task_share):
    # (1-tau) R_j(k) = R_j(k / s(tau)) with s = (1-tau)^(1/(1-I_j)) -- exact, not approximate.
    s = sv.tax_capital_scale(tau, task_share)
    for k in (0.7, 3.0, 25.0):
        assert (1.0 - tau) * rental(task_share, k) == pytest.approx(rental(task_share, k / s), rel=1.0e-13)


def test_stationary_capacity_tax_is_one_minus_task_share():
    # d/dtau [tau (1-tau)^(I/(1-I))] = 0 at tau = 1 - I: check numerically.
    task_share = 0.3
    a = task_share / (1.0 - task_share)

    def stationary_flow(tau: float) -> float:
        return tau * (1.0 - tau) ** a

    tau_cap = sv.stationary_capacity_tax(task_share)
    eps = 1.0e-4
    assert stationary_flow(tau_cap) > stationary_flow(tau_cap - eps)
    assert stationary_flow(tau_cap) > stationary_flow(tau_cap + eps)


# ---------------------------------------------------------------------------
# Witness PV: stationary anchor, feasibility, independence
# ---------------------------------------------------------------------------


def test_witness_at_tau_stationary_point_matches_closed_form(smoke_primitives, smoke_derived, smoke_postmark):
    # Start the witness exactly at the tau-stationary capital s(tau) k*: the transition
    # is empty and PV = tau R_j(k_tau) k_tau / rbar_j in closed form. On the smoke
    # profile rbar_j = rho, so at tau = tau_cap = 1 - I_j this is CS005's exact
    # stationary capacity anchor T_max/rho.
    mp_L, _mp_H, path_L, _path_H = smoke_postmark
    tau_cap = sv.stationary_capacity_tax(mp_L.task_share)
    s = sv.tax_capital_scale(tau_cap, mp_L.task_share)
    k0 = s * mp_L.anchor.k_star
    w = sv.capacity_witness(mp_L, path_L, k0, tau_cap)
    assert w is not None and w.constraints_pass
    closed_form = tau_cap * rental(mp_L.task_share, k0) * k0 / mp_L.rbar
    assert w.pv == pytest.approx(closed_form, rel=1.0e-9)
    assert w.transition_horizon == 0.0


def test_capacity_lower_bound_attains_stationary_anchor(smoke_primitives, smoke_postmark):
    # At k0 = s(tau_cap) k*, the constant-tax family contains the stationary maximum, so
    # the certified lower bound must be at least the closed-form anchor value.
    mp_L, _mp_H, path_L, _path_H = smoke_postmark
    p = smoke_primitives
    tau_cap = sv.stationary_capacity_tax(mp_L.task_share)
    k0 = sv.tax_capital_scale(tau_cap, mp_L.task_share) * mp_L.anchor.k_star
    lb = sv.capacity_lower_bound(mp_L, path_L, k0, p.tau_min, p.tau_max)
    anchor_value = tau_cap * rental(mp_L.task_share, k0) * k0 / mp_L.rbar
    assert lb.value >= anchor_value * (1.0 - 1.0e-6)
    assert lb.witness is not None and lb.witness.constraints_pass


def test_witness_transition_pv_positive_and_independently_verified(real_primitives, real_derived, real_postmark):
    _mp_L, mp_H, _path_L, path_H = real_postmark
    p = real_primitives
    k0 = 6.3236  # the previously admissible candidate's capital: a genuine transition
    path = sv.ensure_witness_domain(p, mp_H, path_H, k0)
    w = sv.capacity_witness(mp_H, path, k0, 0.5)
    assert w is not None
    assert w.reached_anchor
    assert w.pv > 0.0
    assert w.pv_transition > 0.0 and w.pv_stationary_tail > 0.0
    assert w.min_specialization_margin >= 0.0 and w.min_q > 0.0
    # The u-coordinate four-times-finer re-integration must agree with the true-time PV.
    assert w.independent_agreement <= 1.0e-8
    assert w.constraints_pass


def test_witness_zero_tax_has_zero_pv(real_primitives, real_postmark):
    mp_L, _mp_H, path_L, _path_H = real_postmark
    w = sv.capacity_witness(mp_L, path_L, 6.3236, 0.0)
    assert w is not None
    assert w.pv == pytest.approx(0.0, abs=1.0e-12)


def test_capacity_lower_bound_dominates_individual_witnesses(real_primitives, real_postmark):
    mp_L, _mp_H, path_L, _path_H = real_postmark
    p = real_primitives
    k0 = 6.3236
    path = sv.ensure_witness_domain(p, mp_L, path_L, k0)
    lb = sv.capacity_lower_bound(mp_L, path, k0, p.tau_min, p.tau_max)
    assert lb.value >= 0.0
    for tau in (0.2, 0.45, 0.6):
        w = sv.capacity_witness(mp_L, path, k0, tau, with_independent=False)
        if w is not None and w.reached_anchor and w.min_specialization_margin >= 0.0:
            assert lb.value >= w.pv * (1.0 - 1.0e-9)


def test_outer_bound_dominates_lower_bound(real_primitives, real_postmark):
    # C_lower <= C_j <= C_upper: the bracket must be ordered, and the outer bound must
    # be the tau=1 declared-domain revenue maximum.
    mp_L, mp_H, path_L, path_H = real_postmark
    p = real_primitives
    for mp, path in ((mp_L, path_L), (mp_H, path_H)):
        path2 = sv.ensure_witness_domain(p, mp, path, 6.3236)
        lb = sv.capacity_lower_bound(mp, path2, 6.3236, p.tau_min, p.tau_max)
        ob = sv.capacity_outer_bound(mp, path2)
        assert 0.0 <= lb.value < ob
        assert ob == pytest.approx(rental(mp.task_share, path2.k_max) * path2.k_max / mp.rbar, rel=1.0e-3)


def test_witness_is_domain_limited_not_misclassified(real_primitives, real_postmark):
    # A tau whose rescaled start falls outside the certified domain returns None
    # (domain-limited), never a fabricated PV.
    mp_L, _mp_H, path_L, _path_H = real_postmark
    k_huge = path_L.k_max * 0.99
    w = sv.capacity_witness(mp_L, path_L, k_huge, 0.6)  # k_huge/s far beyond k_max
    assert w is None


# ---------------------------------------------------------------------------
# Classification and mutation tests
# ---------------------------------------------------------------------------


def test_classify_three_labels():
    label, margin = sv.classify_mark_viability(f_plus=10.0, capacity_lower=5.0, capacity_outer=50.0, margin_requirement=1.0e-6)
    assert label == sv.CERTIFIED_VIABLE and margin == pytest.approx(15.0)
    label, _ = sv.classify_mark_viability(f_plus=-60.0, capacity_lower=5.0, capacity_outer=50.0, margin_requirement=1.0e-6)
    assert label == sv.CERTIFIED_INFEASIBLE
    label, _ = sv.classify_mark_viability(f_plus=-20.0, capacity_lower=5.0, capacity_outer=50.0, margin_requirement=1.0e-6)
    assert label == sv.FRONTIER_UNRESOLVED


def test_unresolved_band_never_certifies_infeasible_from_missing_witness():
    # CS005: W5 may not classify a candidate infeasible from failure to find a path.
    # Even with a useless (zero) lower bound, anything above -C_upper stays unresolved.
    label, _ = sv.classify_mark_viability(f_plus=-49.9, capacity_lower=0.0, capacity_outer=50.0, margin_requirement=1.0e-6)
    assert label == sv.FRONTIER_UNRESOLVED


def test_mutation_tightening_the_frontier_flips_a_viable_flag():
    # A candidate just above the inner frontier bound is certified_viable; TIGHTEN the
    # frontier (shrink the certified capacity, raising -C_lower past f_plus) and the
    # flag must flip to unresolved. A W5 check that ignores the frontier would not move.
    f_plus, c_lower, c_upper, margin_req = -4.0, 5.0, 50.0, 1.0e-3
    label_before, _ = sv.classify_mark_viability(f_plus, c_lower, c_upper, margin_req)
    assert label_before == sv.CERTIFIED_VIABLE
    label_after, _ = sv.classify_mark_viability(f_plus, c_lower - 2.0, c_upper, margin_req)
    assert label_after == sv.FRONTIER_UNRESOLVED


def test_mutation_weakening_the_frontier_flips_an_unresolved_flag():
    f_plus, c_lower, c_upper, margin_req = -8.0, 5.0, 50.0, 1.0e-3
    label_before, _ = sv.classify_mark_viability(f_plus, c_lower, c_upper, margin_req)
    assert label_before == sv.FRONTIER_UNRESOLVED
    label_after, _ = sv.classify_mark_viability(f_plus, c_lower + 5.0, c_upper, margin_req)
    assert label_after == sv.CERTIFIED_VIABLE


def test_mutation_margin_requirement_gates_marginal_candidates(real_primitives, real_derived, real_postmark):
    # End-to-end on real objects: choose f_plus so the margin sits between two margin
    # requirements; tightening the requirement must flip certified_viable -> unresolved.
    mp_L, _mp_H, path_L, _path_H = real_postmark
    p, derived = real_primitives, real_derived
    k0 = 6.3236
    path = sv.ensure_witness_domain(p, mp_L, path_L, k0)
    lb = sv.capacity_lower_bound(mp_L, path, k0, p.tau_min, p.tau_max)
    h_ref_value = 100.0
    f_plus = -lb.value + 5.0e-5 * h_ref_value  # margin = 5e-5 * H_ref
    loose = sv.mark_viability(p, mp_L, path, k0, f_plus, h_ref_value, margin_factor=1.0e-6)
    tight = sv.mark_viability(p, mp_L, path, k0, f_plus, h_ref_value, margin_factor=1.0e-3)
    assert loose.label == sv.CERTIFIED_VIABLE
    assert tight.label == sv.FRONTIER_UNRESOLVED


# ---------------------------------------------------------------------------
# Candidate-level wiring
# ---------------------------------------------------------------------------


def _candidate_with_successor_wealth(k: float, f_L_plus: float, f_H_plus: float) -> Candidate:
    recovery = Recovery(
        d_0=0.0, c0W=1.0, t_0=0.0, f_0=0.0, theta_0=0.0, b_0=0.0, tau_0=0.0,
        e_L_plus=0.0, e_H_plus=0.0, f_L_plus=f_L_plus, f_H_plus=f_H_plus,
        a_L_plus=1.0, a_H_plus=1.0, n_0=1.0, gamma_a=0.0,
    )
    return Candidate(k=k, e=0.0, psi=0.0, pi=0.0, branch="debt_interior", nu_B=None, b=0.0, epsilon_B=0.0, K_residual=0.0, recovery=recovery, slot="test")


def test_candidate_viability_labels_and_pass_flag(real_primitives, real_derived, real_postmark):
    _mp_L, _mp_H, path_L, path_H = real_postmark
    p, derived = real_primitives, real_derived
    k0 = 6.3236

    viable = sv.candidate_strict_viability(p, derived, path_L, path_H, _candidate_with_successor_wealth(k0, 50.0, 50.0))
    assert viable.checked and viable.label == sv.CERTIFIED_VIABLE and viable.passes
    assert viable.failure_reason is None
    assert set(viable.marks) == {"L", "H"}
    assert viable.method == sv.W5_METHOD

    # Successor wealth below -C_upper for both marks: certified infeasible on the
    # declared domain -- and the reason must say which marks.
    deep = sv.candidate_strict_viability(p, derived, path_L, path_H, _candidate_with_successor_wealth(k0, -1.0e5, -1.0e5))
    assert deep.label == sv.CERTIFIED_INFEASIBLE and not deep.passes
    assert "outer frontier bound" in deep.failure_reason

    # Between the bounds: unresolved, not infeasible, and not passing.
    mid = sv.candidate_strict_viability(p, derived, path_L, path_H, _candidate_with_successor_wealth(k0, -60.0, -110.0))
    assert mid.label == sv.FRONTIER_UNRESOLVED and not mid.passes
    assert "not an infeasibility finding" in mid.failure_reason
    assert mid.min_margin == pytest.approx(min(v.margin for v in mid.marks.values()))


def test_one_infeasible_mark_dominates_an_unresolved_mark(real_primitives, real_derived, real_postmark):
    # Strict support-based viability: EVERY supported mark must be viable; one
    # certified-infeasible mark labels the candidate infeasible even if the other
    # mark is unresolved or viable.
    _mp_L, _mp_H, path_L, path_H = real_postmark
    p, derived = real_primitives, real_derived
    c = _candidate_with_successor_wealth(6.3236, 50.0, -1.0e5)
    out = sv.candidate_strict_viability(p, derived, path_L, path_H, c)
    assert out.marks["L"].label == sv.CERTIFIED_VIABLE
    assert out.marks["H"].label == sv.CERTIFIED_INFEASIBLE
    assert out.label == sv.CERTIFIED_INFEASIBLE and not out.passes
