"""Regression tests for the unbounded owner-root classification defect.

Independent review of the 2026-09-05 I0 commit found that the root solver decided
existence by searching a fixed 200 geometric doublings and reported
``no_interior_root_boundary_limit`` whenever that search failed. A root beyond
``2**200 ~ 1.6e60`` was therefore reported as absent. The counterexample below is
the reviewer's:

    lambda_physical = 1, lambda_risk_neutral = 1e-100, payoff_jump = 1

whose exact root is ``(lambda/lambda_star - 1)/J = 1e100 - 1``.

Existence is now decided analytically from strict monotonicity plus the residual
limit, before any search runs, so no search budget can turn a far-away root into an
absent one. These tests pin down every branch of that decision.
"""

from __future__ import annotations

import math
import sys

import pytest

from tai_public_finance.cs012_poisson_kernels.kernels import evaluate_kernels
from tai_public_finance.cs012_poisson_kernels.portfolio import (
    exposure_interval,
    finite_root_exists,
    one_mark_analytic_root,
    owner_residual,
    solve_owner_root,
)
from tai_public_finance.cs012_poisson_kernels.statuses import (
    FINITE_ROOT_NOT_REPRESENTABLE,
    NO_INTERIOR_ROOT_BOUNDARY_LIMIT,
    ROOT_STATUSES,
    UNIQUE_INTERIOR_ROOT,
    ZERO_PAYOFF_UNIDENTIFIED,
)

from .conftest import fixture, mark

EXTREME_RISK_NEUTRAL = 1.0e-100
UNREPRESENTABLE_RISK_NEUTRAL = 1.0e-320


def one_mark(payoff_jump: float, lambda_risk_neutral: float, lambda_physical: float = 1.0):
    return fixture(
        "extreme",
        (mark("F", lambda_physical, lambda_risk_neutral, payoff_jump, 1.0),),
        owner_exposure=0.0,
    )


@pytest.mark.parametrize("payoff_jump", [1.0, -1.0])
def test_an_extreme_but_representable_root_is_found_not_called_a_boundary(payoff_jump):
    """The reviewer's counterexample, in both unbounded directions.

    ``J = +1`` puts the root at ``+1e100`` with the interval unbounded above;
    ``J = -1`` mirrors it to ``-1e100`` with the interval unbounded below.
    """
    item = one_mark(payoff_jump, EXTREME_RISK_NEUTRAL)
    outcome = evaluate_kernels(item)
    root = solve_owner_root(outcome)

    assert root.status == UNIQUE_INTERIOR_ROOT
    exact = one_mark_analytic_root(1.0, EXTREME_RISK_NEUTRAL, payoff_jump)
    assert exact == pytest.approx(payoff_jump * 1.0e100, rel=1e-12)
    pi = root.require_exposure()
    assert pi == pytest.approx(exact, rel=1e-12)
    assert root.interval.contains(pi)
    assert root.residual_at_root == pytest.approx(0.0, abs=1e-101)
    assert root.derivative_at_root < 0.0

    # The interval is unbounded on exactly the side the root lies on.
    if payoff_jump > 0.0:
        assert not root.interval.upper_is_finite and root.interval.lower_is_finite
    else:
        assert not root.interval.lower_is_finite and root.interval.upper_is_finite


@pytest.mark.parametrize("payoff_jump", [1.0, -1.0])
def test_existence_is_decided_analytically_before_any_search(payoff_jump):
    """The limit strictly beyond zero in the direction of travel is what settles it."""
    marks = evaluate_kernels(one_mark(payoff_jump, EXTREME_RISK_NEUTRAL)).require_finite()
    interval = exposure_interval((payoff_jump,))
    exists, at_zero, limit = finite_root_exists(marks, interval)
    assert exists
    assert at_zero == pytest.approx(payoff_jump, rel=1e-12)
    # limit = -lambda_star * J, which sits strictly beyond zero from at_zero.
    assert limit == pytest.approx(-EXTREME_RISK_NEUTRAL * payoff_jump, rel=1e-12)
    assert (at_zero > 0.0) == (limit < 0.0)


def test_a_search_budget_alone_would_still_have_missed_the_root():
    """The old 200-doubling cap reached only ~1.6e60, far short of 1e100. This
    documents why the fix had to change the criterion, not enlarge the budget."""
    marks = evaluate_kernels(one_mark(1.0, EXTREME_RISK_NEUTRAL)).require_finite()
    assert 2.0**200 < 1.0e100
    # The residual has not yet changed sign anywhere the old search looked.
    assert owner_residual(marks, 2.0**200) > 0.0
    # It has changed sign well before the largest finite double.
    assert owner_residual(marks, sys.float_info.max) < 0.0


def test_a_zero_risk_neutral_intensity_stays_a_genuine_boundary_only_limit():
    """The preserved true negative: the limit is exactly zero, so the strictly
    decreasing residual approaches it without ever reaching it."""
    item = one_mark(1.0, 0.0)
    outcome = evaluate_kernels(item)
    root = solve_owner_root(outcome)
    assert root.status == NO_INTERIOR_ROOT_BOUNDARY_LIMIT
    assert root.exposure is None
    assert root.residual_at_zero > 0.0
    assert root.limit_at_unbounded_end == pytest.approx(0.0, abs=0.0)
    marks = outcome.require_finite()
    exists, _, _ = finite_root_exists(marks, exposure_interval((1.0,)))
    assert not exists
    # No finite exposure, however large, drives the residual to zero or below.
    assert owner_residual(marks, sys.float_info.max) > 0.0
    with pytest.raises(RuntimeError):
        root.require_exposure()


@pytest.mark.parametrize("payoff_jump", [1.0, -1.0])
def test_a_mathematically_finite_root_beyond_fp64_is_a_numerical_refusal(payoff_jump):
    """A root at roughly ``1e320`` exists mathematically but is not representable.
    It must be reported as a numerical refusal, never as a boundary-only limit."""
    outcome = evaluate_kernels(one_mark(payoff_jump, UNREPRESENTABLE_RISK_NEUTRAL))
    root = solve_owner_root(outcome)
    assert root.status == FINITE_ROOT_NOT_REPRESENTABLE
    assert root.status != NO_INTERIOR_ROOT_BOUNDARY_LIMIT
    assert root.exposure is None
    # Existence still holds analytically; only the arithmetic runs out.
    marks = outcome.require_finite()
    exists, _, limit = finite_root_exists(marks, exposure_interval((payoff_jump,)))
    assert exists
    assert limit != 0.0
    far = math.copysign(sys.float_info.max, payoff_jump)
    assert (owner_residual(marks, far) > 0.0) == (payoff_jump > 0.0)
    assert "not representable" in root.detail or "outside double precision" in root.detail


def test_ordinary_one_and_two_mark_roots_are_unchanged(frozen_fixtures):
    """The repair must not move any root that was already correct."""
    one = solve_owner_root(evaluate_kernels(frozen_fixtures["one_mark_alignment"]))
    assert one.status == UNIQUE_INTERIOR_ROOT
    assert one.require_exposure() == pytest.approx(2.0, abs=1e-12)
    assert one.boundary_margin == pytest.approx(4.0, abs=1e-12)

    two = solve_owner_root(evaluate_kernels(frozen_fixtures["two_mark_orthogonal_gap"]))
    assert two.status == UNIQUE_INTERIOR_ROOT
    assert two.require_exposure() == pytest.approx(0.0, abs=1e-15)

    zero_component = solve_owner_root(
        evaluate_kernels(frozen_fixtures["two_mark_one_zero_payoff"])
    )
    assert zero_component.status == UNIQUE_INTERIOR_ROOT
    assert zero_component.require_exposure() == pytest.approx(
        one_mark_analytic_root(0.15, 0.09, 0.40), abs=1e-12
    )

    limiting = solve_owner_root(
        evaluate_kernels(frozen_fixtures["one_mark_zero_risk_neutral_limit"])
    )
    assert limiting.status == NO_INTERIOR_ROOT_BOUNDARY_LIMIT

    unidentified = solve_owner_root(
        evaluate_kernels(frozen_fixtures["all_zero_payoff_unidentified"])
    )
    assert unidentified.status == ZERO_PAYOFF_UNIDENTIFIED


def test_a_mixed_sign_two_mark_root_survives_an_extreme_risk_neutral_intensity():
    """Both endpoints finite: the residual diverges at each, so a root exists
    regardless of how extreme the intensities are."""
    item = fixture(
        "mixed_extreme",
        (mark("P", 1.0, 1.0e-100, 0.5, 1.0), mark("F", 1.0, 1.0e-100, -0.25, 1.0)),
        owner_exposure=0.0,
    )
    outcome = evaluate_kernels(item)
    root = solve_owner_root(outcome)
    assert root.status == UNIQUE_INTERIOR_ROOT
    pi = root.require_exposure()
    assert root.interval.lower_is_finite and root.interval.upper_is_finite
    assert root.interval.contains(pi)
    assert abs(root.residual_at_root) <= 1e-11


def test_the_general_route_never_divides_by_a_selected_payoff_component():
    """A two-mark case with one exactly zero component still solves through the
    unmultiplied residual, which the one-mark analytic formula could not do."""
    item = fixture(
        "zero_component_extreme",
        (mark("P", 0.3, 0.24, 0.0, 1.0), mark("F", 1.0, 1.0e-100, 1.0, 1.0)),
        owner_exposure=0.0,
    )
    root = solve_owner_root(evaluate_kernels(item))
    assert root.status == UNIQUE_INTERIOR_ROOT
    assert root.require_exposure() == pytest.approx(1.0e100, rel=1e-12)


def test_every_root_status_is_reachable_and_demonstrated(frozen_fixtures):
    observed = {
        solve_owner_root(evaluate_kernels(item)).status
        for item in (
            frozen_fixtures["one_mark_alignment"],
            frozen_fixtures["one_mark_zero_risk_neutral_limit"],
            frozen_fixtures["all_zero_payoff_unidentified"],
            one_mark(1.0, UNREPRESENTABLE_RISK_NEUTRAL),
        )
    }
    assert observed == set(ROOT_STATUSES)
