"""Seeded property tests over a declared well-conditioned box.

The generator stays inside the box CS012 v0.1 declares for I0: one to four marks,
strictly positive physical intensities, nonnegative risk-neutral intensities, both
payoff signs, occasional exact zero components, and exposures at least
``1e-6 * max(1, abs(pi))`` inside every finite wealth boundary. It uses a fixed
seed and prints the smallest failing case rather than only the first.
"""

from __future__ import annotations

import math
import random

import pytest

from tai_public_finance.cs012_poisson_kernels.independent import reconstruct
from tai_public_finance.cs012_poisson_kernels.kernels import evaluate_kernels
from tai_public_finance.cs012_poisson_kernels.portfolio import (
    decompose,
    exposure_interval,
    normalized_error,
    one_mark_analytic_root,
    owner_residual,
    owner_residual_derivative,
    solve_owner_root,
)
from tai_public_finance.cs012_poisson_kernels.projection import (
    project_fiscal_gap,
    safe_account_rank,
)
from tai_public_finance.cs012_poisson_kernels.statuses import (
    FINITE_MAINTAINED_BRANCH,
    PROJECTION_RESOLVED,
    UNIQUE_INTERIOR_ROOT,
)

from .conftest import fixture, mark

SEED = 20260905
CASE_COUNT = 240
IDENTITY_MAX = 1.0e-11
INDEPENDENT_MAX = 1.0e-10
ROOT_RESIDUAL_MAX = 1.0e-11
ORTHOGONALITY_MAX = 1.0e-11
INTERIOR_FRACTION = 1.0e-6


def _generate(rng: random.Random, index: int):
    """One well-conditioned case: marks, then an exposure strictly inside the
    admissible interval by at least ``INTERIOR_FRACTION * max(1, abs(pi))``."""
    count = rng.randint(1, 4)
    payoffs: list[float] = []
    for position in range(count):
        if rng.random() < 0.15 and count > 1:
            payoffs.append(0.0)
        else:
            magnitude = math.exp(rng.uniform(math.log(0.02), math.log(2.0)))
            payoffs.append(magnitude if rng.random() < 0.5 else -magnitude)
    if all(jump == 0.0 for jump in payoffs):
        payoffs[rng.randrange(count)] = 0.5

    interval = exposure_interval(tuple(payoffs))
    lower = interval.lower if interval.lower_is_finite else -10.0
    upper = interval.upper if interval.upper_is_finite else 10.0
    # Keep a wide margin from both endpoints: the box is well-conditioned by
    # construction, so a near-pole exposure is out of scope here.
    span = upper - lower
    exposure = lower + span * rng.uniform(0.15, 0.85)
    for jump in payoffs:
        assert 1.0 + exposure * jump > 0.0
    margin = interval.distance_to_boundary(exposure)
    assert margin >= INTERIOR_FRACTION * max(1.0, abs(exposure))

    marks = tuple(
        mark(
            f"M{position}",
            lambda_physical=rng.uniform(0.01, 1.5),
            lambda_risk_neutral=(0.0 if rng.random() < 0.08 else rng.uniform(0.0, 1.5)),
            payoff_jump=jump,
            successor=rng.uniform(0.05, 4.0),
        )
        for position, jump in enumerate(payoffs)
    )
    return fixture(
        f"prop_{index:04d}",
        marks,
        owner_exposure=exposure,
        government_current_marginal_value=rng.uniform(0.05, 4.0),
    )


def _case_size(item) -> tuple[int, float]:
    return (len(item.marks), max(abs(m.payoff_jump) for m in item.marks))


def _check_case(item) -> str | None:
    """Return a failure description, or ``None`` if the case passes."""
    outcome = evaluate_kernels(item)
    if outcome.status != FINITE_MAINTAINED_BRANCH:
        return f"kernel status {outcome.status}: {outcome.detail}"

    production = decompose(outcome)
    scale = tuple(
        value
        for term in production.terms
        for value in (term.owner, term.government, term.government_owner, term.relative)
    )
    if production.decomposition_error > IDENTITY_MAX:
        return f"decomposition error {production.decomposition_error!r}"
    if production.relative_identity_error > IDENTITY_MAX:
        return f"relative identity error {production.relative_identity_error!r}"

    alternative = reconstruct(item)
    for name, produced, rebuilt in (
        ("d_owner", production.d_owner, alternative.d_owner),
        ("d_government", production.d_government, alternative.d_government),
        ("d_government_owner", production.d_government_owner, alternative.d_government_owner),
        ("d_relative", production.d_relative, alternative.d_relative),
    ):
        error = normalized_error(produced, rebuilt, scale)
        if error > INDEPENDENT_MAX:
            return f"independent {name} error {error!r}"

    marks = outcome.require_finite()
    interval = exposure_interval(item.payoff_vector)
    if not interval.contains(0.0):
        return "zero exposure is not interior to the admissible interval"

    # Strict negativity of the residual derivative wherever a nonzero payoff exists.
    for fraction in (0.05, 0.25, 0.5, 0.75, 0.95):
        lower = interval.lower if interval.lower_is_finite else -50.0
        upper = interval.upper if interval.upper_is_finite else 50.0
        pi = lower + (upper - lower) * fraction
        if not interval.contains(pi):
            continue
        if owner_residual_derivative(marks, pi) >= 0.0:
            return f"non-negative residual derivative at pi={pi!r}"

    root = solve_owner_root(outcome)
    if root.status == UNIQUE_INTERIOR_ROOT:
        pi = root.require_exposure()
        if not interval.contains(pi):
            return f"root {pi!r} outside the admissible interval"
        residual_error = normalized_error(owner_residual(marks, pi), 0.0, scale)
        if residual_error > ROOT_RESIDUAL_MAX:
            return f"root residual {residual_error!r}"
        margin = interval.distance_to_boundary(pi)
        if margin < 1.0e-10 * max(1.0, abs(pi)):
            return f"root margin {margin!r} too close to a finite wealth boundary"
        if len(marks) == 1 and marks[0].lambda_risk_neutral > 0.0:
            analytic = one_mark_analytic_root(
                marks[0].lambda_physical,
                marks[0].lambda_risk_neutral,
                marks[0].payoff_jump,
            )
            if abs(pi - analytic) > 1.0e-9 * max(1.0, abs(analytic)):
                return f"one-mark root {pi!r} differs from analytic {analytic!r}"

    projection = project_fiscal_gap(outcome)
    if projection.status == PROJECTION_RESOLVED:
        if projection.orthogonality_error > ORTHOGONALITY_MAX:
            return f"orthogonality error {projection.orthogonality_error!r}"

    safe = safe_account_rank(outcome)
    if safe.rank_increase != 0 or safe.rank_with_safe_account != safe.rank_risky:
        return "the safe account changed the risky payoff rank"
    return None


def test_seeded_property_cases_pass_every_declared_tolerance():
    rng = random.Random(SEED)
    cases = [_generate(rng, index) for index in range(CASE_COUNT)]
    assert len(cases) >= 200
    failures = []
    for item in cases:
        problem = _check_case(item)
        if problem is not None:
            failures.append((_case_size(item), item, problem))
    if failures:
        failures.sort(key=lambda entry: entry[0])
        size, smallest, problem = failures[0]
        pytest.fail(
            f"{len(failures)} of {len(cases)} property cases failed. Smallest "
            f"failing case (size {size}): {smallest.direct_fields()!r} -> {problem}"
        )


def test_the_generator_covers_both_payoff_signs_and_exact_zeros():
    rng = random.Random(SEED)
    cases = [_generate(rng, index) for index in range(CASE_COUNT)]
    payoffs = [jump for item in cases for jump in item.payoff_vector]
    assert any(jump > 0.0 for jump in payoffs)
    assert any(jump < 0.0 for jump in payoffs)
    assert any(jump == 0.0 for jump in payoffs)
    assert any(m.lambda_risk_neutral == 0.0 for item in cases for m in item.marks)
    assert {len(item.marks) for item in cases} == {1, 2, 3, 4}


def test_the_seed_is_fixed_so_the_case_set_is_reproducible():
    rng_a = random.Random(SEED)
    rng_b = random.Random(SEED)
    first = [_generate(rng_a, index) for index in range(25)]
    second = [_generate(rng_b, index) for index in range(25)]
    assert [item.direct_fields() for item in first] == [
        item.direct_fields() for item in second
    ]
