from __future__ import annotations

import pytest

from tai_public_finance.cs005_marked_poisson.prearrival_solver import enumerate_with_domain_expansion


@pytest.fixture(scope="module")
def real_candidates(real_primitives, real_derived, real_postmark):
    _mp_L, _mp_H, path_L, path_H = real_postmark
    result, _path_L, _path_H = enumerate_with_domain_expansion(real_primitives, real_derived, path_L, path_H, k_grid_points=300)
    return result


@pytest.fixture(scope="module")
def smoke_candidates(smoke_primitives, smoke_derived, smoke_postmark):
    _mp_L, _mp_H, path_L, path_H = smoke_postmark
    result, _path_L, _path_H = enumerate_with_domain_expansion(smoke_primitives, smoke_derived, path_L, path_H, k_grid_points=300)
    return result


def test_finds_at_least_one_candidate_each_profile(real_candidates, smoke_candidates):
    assert len(real_candidates.candidates) > 0
    assert len(smoke_candidates.candidates) > 0


def test_every_reported_candidate_has_tiny_K_residual(real_candidates, smoke_candidates):
    for result in (real_candidates, smoke_candidates):
        for c in result.candidates:
            assert abs(c.K_residual) < 1e-6, f"candidate at k={c.k} has K_residual={c.K_residual}"


def test_both_debt_interior_and_debt_boundary_branches_appear(real_candidates, smoke_candidates):
    branches = {c.branch for r in (real_candidates, smoke_candidates) for c in r.candidates}
    assert "debt_interior" in branches
    assert "debt_boundary" in branches


def test_debt_is_never_clipped(real_candidates, smoke_candidates):
    # b = psi - e should reproduce exactly from the reported e, psi -- if debt were
    # ever clipped to a floor/ceiling, this identity would break.
    for result in (real_candidates, smoke_candidates):
        for c in result.candidates:
            assert c.b == pytest.approx(c.psi - c.e, abs=1e-9)


def test_debt_interior_candidates_meet_their_own_margin_or_are_relabelled(real_candidates, smoke_candidates):
    for result in (real_candidates, smoke_candidates):
        for c in result.candidates:
            if c.branch == "debt_interior":
                assert c.b >= c.epsilon_B


def test_debt_boundary_candidates_have_near_zero_b(real_candidates, smoke_candidates):
    # b=psi-e=0 is imposed exactly when solving the boundary branch; nu_B's SIGN is a
    # separate KKT feasibility question (a root can legitimately have nu_B<0, meaning
    # it's a boundary stationary point of the algebra but not a valid KKT solution --
    # see test_diagnostics.py's feasibility_kkt_multiplier_sign check for that).
    for result in (real_candidates, smoke_candidates):
        for c in result.candidates:
            if c.branch == "debt_boundary":
                assert abs(c.b) < 1e-6
                assert c.nu_B is not None
