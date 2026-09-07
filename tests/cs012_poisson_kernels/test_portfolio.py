"""Exposure interval construction, owner-root statuses, and residual monotonicity."""

from __future__ import annotations

import math

import pytest

from tai_public_finance.cs012_poisson_kernels.kernels import evaluate_kernels
from tai_public_finance.cs012_poisson_kernels.portfolio import (
    exposure_interval,
    one_mark_analytic_root,
    owner_residual,
    owner_residual_derivative,
    owner_residual_limit,
    solve_owner_root,
)
from tai_public_finance.cs012_poisson_kernels.statuses import (
    NO_INTERIOR_ROOT_BOUNDARY_LIMIT,
    UNIQUE_INTERIOR_ROOT,
    ZERO_PAYOFF_UNIDENTIFIED,
)

from .conftest import fixture, mark

ROOT_RESIDUAL_MAX = 1.0e-11
BOUNDARY_MARGIN_FACTOR = 1.0e-10


@pytest.mark.parametrize(
    ("payoffs", "lower", "upper"),
    [
        ((0.5,), -2.0, math.inf),
        ((0.5, 0.25), -2.0, math.inf),           # all positive
        ((-0.5, -0.25), -math.inf, 2.0),          # all negative
        ((0.5, -0.25), -2.0, 4.0),                # mixed
        ((0.0, 0.4), -2.5, math.inf),             # one zero component
        ((0.4, 0.0, -0.8), -2.5, 1.25),           # zero component with both signs
    ],
)
def test_exposure_interval_is_the_open_intersection(payoffs, lower, upper):
    interval = exposure_interval(payoffs)
    assert interval.lower == pytest.approx(lower)
    assert interval.upper == pytest.approx(upper)
    assert interval.lower_is_finite == math.isfinite(lower)
    assert interval.upper_is_finite == math.isfinite(upper)


@pytest.mark.parametrize(
    "payoffs",
    [(0.5,), (0.5, 0.25), (-0.5, -0.25), (0.5, -0.25), (0.0, 0.4), (0.4, 0.0, -0.8),
     (1e-6,), (-1e-6,), (12.5, -0.125)],
)
def test_zero_exposure_is_always_interior(payoffs):
    """A correctly constructed interval can never be empty: pi = 0 satisfies every
    1 + pi*J_j > 0 constraint."""
    interval = exposure_interval(payoffs)
    assert interval.contains(0.0)
    assert interval.lower < 0.0 < interval.upper


def test_zero_payoff_vector_defines_no_interval():
    with pytest.raises(ValueError):
        exposure_interval((0.0, 0.0))


def test_unique_interior_root_on_a_mixed_sign_two_mark_case():
    item = fixture(
        "mixed",
        (mark("P", 0.20, 0.12, 0.50, 1.0), mark("F", 0.10, 0.04, -0.25, 1.0)),
        owner_exposure=0.0,
    )
    outcome = evaluate_kernels(item)
    root = solve_owner_root(outcome)
    assert root.status == UNIQUE_INTERIOR_ROOT
    pi = root.require_exposure()
    assert root.interval.contains(pi)
    assert abs(root.residual_at_root) <= ROOT_RESIDUAL_MAX
    assert root.derivative_at_root < 0.0
    assert root.boundary_margin >= BOUNDARY_MARGIN_FACTOR * max(1.0, abs(pi))


def test_one_zero_component_still_yields_the_analytic_one_mark_root(frozen_fixtures):
    outcome = evaluate_kernels(frozen_fixtures["two_mark_one_zero_payoff"])
    root = solve_owner_root(outcome)
    assert root.status == UNIQUE_INTERIOR_ROOT
    analytic = one_mark_analytic_root(0.15, 0.09, 0.40)
    assert root.require_exposure() == pytest.approx(analytic, abs=1e-12)
    # The zero-payoff mark stays in the kernel report but contributes nothing.
    marks = outcome.require_finite()
    assert marks[0].payoff_jump == 0.0
    assert marks[0].k_world == pytest.approx(0.8)


def test_boundary_only_limiting_root_is_reported_not_invented(frozen_fixtures):
    outcome = evaluate_kernels(frozen_fixtures["one_mark_zero_risk_neutral_limit"])
    root = solve_owner_root(outcome)
    assert root.status == NO_INTERIOR_ROOT_BOUNDARY_LIMIT
    assert root.exposure is None
    assert root.residual_at_zero > 0.0
    assert root.limit_at_unbounded_end == pytest.approx(0.0, abs=1e-18)
    with pytest.raises(RuntimeError):
        root.require_exposure()


def test_zero_payoff_vector_is_unidentified_not_a_default_exposure(frozen_fixtures):
    outcome = evaluate_kernels(frozen_fixtures["all_zero_payoff_unidentified"])
    root = solve_owner_root(outcome)
    assert root.status == ZERO_PAYOFF_UNIDENTIFIED
    assert root.exposure is None
    assert root.interval is None
    with pytest.raises(RuntimeError):
        root.require_exposure()


def test_owner_residual_is_strictly_decreasing_over_the_admissible_interval():
    item = fixture(
        "monotone",
        (mark("P", 0.20, 0.12, 0.50, 1.0), mark("F", 0.10, 0.04, -0.25, 1.0)),
    )
    marks = evaluate_kernels(item).require_finite()
    interval = exposure_interval((0.50, -0.25))
    grid = [
        interval.lower + (interval.upper - interval.lower) * fraction
        for fraction in (0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99)
    ]
    values = [owner_residual(marks, pi) for pi in grid]
    assert all(later < earlier for earlier, later in zip(values, values[1:]))
    assert all(owner_residual_derivative(marks, pi) < 0.0 for pi in grid)


def test_analytic_derivative_matches_a_centred_finite_difference_away_from_boundaries():
    item = fixture(
        "derivative",
        (mark("P", 0.20, 0.12, 0.50, 1.0), mark("F", 0.10, 0.04, -0.25, 1.0)),
    )
    marks = evaluate_kernels(item).require_finite()
    step = 1.0e-6
    for pi in (-1.0, -0.5, 0.0, 0.5, 1.0, 2.0):
        analytic = owner_residual_derivative(marks, pi)
        numeric = (
            owner_residual(marks, pi + step) - owner_residual(marks, pi - step)
        ) / (2.0 * step)
        assert numeric == pytest.approx(analytic, rel=1e-6, abs=1e-9)


def test_owner_residual_limit_matches_a_far_field_evaluation():
    item = fixture("limit", (mark("F", 0.25, 0.10, 0.60, 1.0),))
    marks = evaluate_kernels(item).require_finite()
    limit = owner_residual_limit(marks)
    assert limit == pytest.approx(-0.10 * 0.60, abs=1e-15)
    assert owner_residual(marks, 1.0e12) == pytest.approx(limit, abs=1e-9)


def test_the_root_search_never_evaluates_a_pole():
    """A finite endpoint is approached geometrically from strictly inside, so
    1 + pi*J_j stays positive at every probe."""
    item = fixture(
        "near_pole",
        (mark("P", 0.20, 0.30, 0.50, 1.0), mark("F", 0.10, 0.05, -0.25, 1.0)),
    )
    outcome = evaluate_kernels(item)
    root = solve_owner_root(outcome)
    assert root.status == UNIQUE_INTERIOR_ROOT
    pi = root.require_exposure()
    for m in outcome.require_finite():
        assert 1.0 + pi * m.payoff_jump > 0.0
