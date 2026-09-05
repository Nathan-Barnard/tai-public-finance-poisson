"""Frozen fixtures, all three kernel routes, and both decomposition identities."""

from __future__ import annotations

import math

import pytest

from tai_public_finance.cs012_poisson_kernels.extended import ExtendedReal
from tai_public_finance.cs012_poisson_kernels.independent import reconstruct
from tai_public_finance.cs012_poisson_kernels.kernels import (
    KernelRefusal,
    evaluate_kernels,
)
from tai_public_finance.cs012_poisson_kernels.portfolio import (
    decompose,
    normalized_error,
    one_mark_analytic_root,
    solve_owner_root,
)
from tai_public_finance.cs012_poisson_kernels.statuses import (
    FINITE_MAINTAINED_BRANCH,
    INVALID_DIRECT_WEALTH_RATIO,
    NONFINITE_FINITE_BRANCH_INPUT,
    UNIQUE_INTERIOR_ROOT,
)

from .conftest import BRANCH_LITERAL_LAISSEZ_FAIRE, fixture, mark

IDENTITY_MAX = 1.0e-11
INDEPENDENT_MAX = 1.0e-10
ROOT_RESIDUAL_MAX = 1.0e-11


def test_one_mark_alignment_fixture_is_hand_checkable(frozen_fixtures):
    """All three kernels equal 0.5, gamma_F = 1, and both residuals vanish."""
    outcome = evaluate_kernels(frozen_fixtures["one_mark_alignment"])
    assert outcome.status == FINITE_MAINTAINED_BRANCH
    (only,) = outcome.require_finite()
    assert only.mark_id == "F"
    assert only.owner_wealth_multiplier == pytest.approx(2.0, abs=1e-15)
    assert only.k_world == pytest.approx(0.5, abs=1e-15)
    assert only.k_owner == pytest.approx(0.5, abs=1e-15)
    assert only.k_government == pytest.approx(0.5, abs=1e-15)
    assert only.gamma == pytest.approx(1.0, abs=1e-15)

    decomposition = decompose(outcome)
    assert decomposition.d_owner == pytest.approx(0.0, abs=1e-15)
    assert decomposition.d_government == pytest.approx(0.0, abs=1e-15)
    assert decomposition.d_government_owner == pytest.approx(0.0, abs=1e-15)
    assert decomposition.d_relative == pytest.approx(0.0, abs=1e-15)
    assert decomposition.decomposition_error <= IDENTITY_MAX
    assert decomposition.relative_identity_error <= IDENTITY_MAX


def test_one_mark_alignment_root_matches_the_analytic_exposure(frozen_fixtures):
    """The bracketed root reproduces (lambda/lambda_star - 1)/J = 2 exactly."""
    outcome = evaluate_kernels(frozen_fixtures["one_mark_alignment"])
    root = solve_owner_root(outcome)
    assert root.status == UNIQUE_INTERIOR_ROOT
    analytic = one_mark_analytic_root(0.20, 0.10, 0.50)
    assert analytic == pytest.approx(2.0, abs=1e-15)
    assert root.require_exposure() == pytest.approx(analytic, abs=1e-12)
    assert abs(root.residual_at_root) <= ROOT_RESIDUAL_MAX
    assert root.derivative_at_root < 0.0
    # The fixture's declared exposure is itself the private optimum here, so the
    # owner residual was already zero before any root was solved for.
    assert root.residual_at_zero != 0.0


def test_two_mark_orthogonal_gap_fixture_is_hand_checkable(frozen_fixtures):
    """k_world = k_owner = [1,1], gamma = [1.2,1.8], g = [0.2,0.8]."""
    outcome = evaluate_kernels(frozen_fixtures["two_mark_orthogonal_gap"])
    marks = outcome.require_finite()
    assert [m.mark_id for m in marks] == ["P", "F"]
    assert [m.k_world for m in marks] == pytest.approx([1.0, 1.0], abs=1e-15)
    assert [m.k_owner for m in marks] == pytest.approx([1.0, 1.0], abs=1e-15)
    assert [m.k_government for m in marks] == pytest.approx([1.2, 1.8], abs=1e-15)
    assert [m.gamma for m in marks] == pytest.approx([1.2, 1.8], abs=1e-15)

    decomposition = decompose(outcome)
    assert decomposition.d_owner == pytest.approx(0.0, abs=1e-16)
    assert decomposition.d_government == pytest.approx(0.0, abs=1e-16)
    assert decomposition.decomposition_error <= IDENTITY_MAX
    assert decomposition.relative_identity_error <= IDENTITY_MAX
    # Opposite payoff signs are intentional and load-bearing.
    assert marks[0].payoff_jump > 0.0 > marks[1].payoff_jump


def test_both_decomposition_identities_hold_on_every_finite_frozen_fixture(frozen_fixtures):
    for name, item in frozen_fixtures.items():
        if item.declared_branch == BRANCH_LITERAL_LAISSEZ_FAIRE:
            continue
        decomposition = decompose(evaluate_kernels(item))
        assert decomposition.decomposition_error <= IDENTITY_MAX, name
        assert decomposition.relative_identity_error <= IDENTITY_MAX, name
        assert decomposition.relative_identity_applies, name


def test_production_agrees_with_the_independent_route_on_every_finite_fixture(frozen_fixtures):
    for name, item in frozen_fixtures.items():
        if item.declared_branch == BRANCH_LITERAL_LAISSEZ_FAIRE:
            continue
        production = decompose(evaluate_kernels(item))
        alternative = reconstruct(item)
        scale = tuple(
            value
            for term in production.terms
            for value in (term.owner, term.government, term.government_owner, term.relative)
        )
        for produced, rebuilt in (
            (production.d_owner, alternative.d_owner),
            (production.d_government, alternative.d_government),
            (production.d_government_owner, alternative.d_government_owner),
            (production.d_relative, alternative.d_relative),
        ):
            assert normalized_error(produced, rebuilt, scale) <= INDEPENDENT_MAX, name


def test_owner_kernel_agrees_across_the_exposure_and_wealth_ratio_routes():
    """CS012 acceptance check 1: both owner-kernel routes must give the same value."""
    exposure = 0.75
    jump = 0.4
    multiplier = 1.0 + exposure * jump
    item = fixture(
        "dual_route",
        (mark("F", 0.2, 0.1, jump, 1.0, owner_wealth_before=3.0,
              owner_wealth_after=3.0 * multiplier),),
        owner_exposure=exposure,
    )
    (only,) = evaluate_kernels(item).require_finite()
    assert only.k_owner == pytest.approx(1.0 / multiplier, abs=1e-15)


def test_disagreeing_wealth_ratio_is_refused_not_preferred():
    item = fixture(
        "bad_route",
        (mark("F", 0.2, 0.1, 0.4, 1.0, owner_wealth_before=1.0, owner_wealth_after=2.0),),
        owner_exposure=0.75,
    )
    outcome = evaluate_kernels(item)
    assert outcome.status == INVALID_DIRECT_WEALTH_RATIO
    with pytest.raises(KernelRefusal):
        outcome.require_finite()


@pytest.mark.parametrize(
    ("label", "item"),
    [
        (
            "nan_intensity",
            fixture("nan", (mark("F", math.nan, 0.1, 0.4, 1.0),)),
        ),
        (
            "zero_physical_intensity",
            fixture("zero_lambda", (mark("F", 0.0, 0.1, 0.4, 1.0),)),
        ),
        (
            "negative_physical_intensity",
            fixture("negative_lambda", (mark("F", -0.2, 0.1, 0.4, 1.0),)),
        ),
        (
            "negative_risk_neutral_intensity",
            fixture("negative_lambda_star", (mark("F", 0.2, -0.1, 0.4, 1.0),)),
        ),
        (
            "infinite_payoff",
            fixture("inf_payoff", (mark("F", 0.2, 0.1, math.inf, 1.0),)),
        ),
        (
            "nan_successor",
            fixture(
                "nan_successor",
                (mark("F", 0.2, 0.1, 0.4, ExtendedReal.of(math.nan)),),
            ),
        ),
        (
            "infinite_successor_on_finite_branch",
            fixture(
                "inf_successor",
                (mark("F", 0.2, 0.1, 0.4, ExtendedReal.of(math.inf)),),
            ),
        ),
        (
            "non_positive_successor",
            fixture("zero_successor", (mark("F", 0.2, 0.1, 0.4, 0.0),)),
        ),
        (
            "non_positive_current_marginal_value",
            fixture(
                "zero_mu",
                (mark("F", 0.2, 0.1, 0.4, 1.0),),
                government_current_marginal_value=0.0,
            ),
        ),
        (
            "negative_wealth_multiplier",
            fixture(
                "bad_multiplier",
                (mark("F", 0.2, 0.1, 0.5, 1.0),),
                owner_exposure=-3.0,
            ),
        ),
        (
            "exactly_zero_wealth_multiplier",
            fixture(
                "zero_multiplier",
                (mark("F", 0.2, 0.1, 0.5, 1.0),),
                owner_exposure=-2.0,
            ),
        ),
        (
            "nan_exposure",
            fixture("nan_exposure", (mark("F", 0.2, 0.1, 0.4, 1.0),), owner_exposure=math.nan),
        ),
    ],
)
def test_invalid_finite_branch_inputs_are_refused_explicitly(label, item):
    outcome = evaluate_kernels(item)
    assert outcome.status == NONFINITE_FINITE_BRANCH_INPUT, label
    assert outcome.marks == (), label
    assert outcome.detail, label
    with pytest.raises(KernelRefusal):
        outcome.require_finite()


def test_a_refusal_is_never_hidden_behind_none_or_nan():
    outcome = evaluate_kernels(fixture("nan", (mark("F", math.nan, 0.1, 0.4, 1.0),)))
    assert outcome.status in {NONFINITE_FINITE_BRANCH_INPUT}
    assert not outcome.is_finite_branch
    # Nothing in the public surface silently returns a number.
    with pytest.raises(KernelRefusal):
        decompose(outcome)
    with pytest.raises(KernelRefusal):
        solve_owner_root(outcome)


def test_owner_residual_is_not_zeroed_by_construction(frozen_fixtures):
    """D_owner is evaluated at the fixture's declared exposure, not assumed zero."""
    decomposition = decompose(evaluate_kernels(frozen_fixtures["two_mark_one_zero_payoff"]))
    assert decomposition.d_owner != 0.0
    assert decomposition.d_owner == pytest.approx(0.014, abs=1e-15)
