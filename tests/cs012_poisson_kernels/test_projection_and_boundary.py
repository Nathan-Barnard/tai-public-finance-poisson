"""Marketed projection, orthogonal fiscal gap, safe-account rank, and the literal
laissez-faire extended-real boundary."""

from __future__ import annotations

import json
import math

import pytest

from tai_public_finance.cs012_poisson_kernels.extended import (
    POSITIVE_INFINITY,
    UNDEFINED,
    ExtendedReal,
    ExtendedRealError,
)
from tai_public_finance.cs012_poisson_kernels.kernels import (
    KernelRefusal,
    evaluate_kernels,
)
from tai_public_finance.cs012_poisson_kernels.portfolio import decompose, solve_owner_root
from tai_public_finance.cs012_poisson_kernels.projection import (
    project_fiscal_gap,
    safe_account_rank,
)
from tai_public_finance.cs012_poisson_kernels.statuses import (
    NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE,
    PROJECTION_RESOLVED,
    UNRESOLVED_PAYOFF_NORM_REFUSED,
    ZERO_PAYOFF_NORM_REFUSED,
)

from .conftest import BRANCH_LITERAL_LAISSEZ_FAIRE, fixture, mark

ORTHOGONALITY_MAX = 1.0e-11


def test_two_mark_gap_is_orthogonal_with_a_zero_marketed_projection(frozen_fixtures):
    """The frozen two-mark fixture: zero marketed projection, nonzero orthogonal gap."""
    outcome = evaluate_kernels(frozen_fixtures["two_mark_orthogonal_gap"])
    projection = project_fiscal_gap(outcome)
    assert projection.status == PROJECTION_RESOLVED
    assert projection.denominator == pytest.approx(0.05625, abs=1e-15)
    assert projection.numerator == pytest.approx(0.0, abs=1e-17)
    assert projection.require_alpha() == pytest.approx(0.0, abs=1e-15)

    gaps = [component.gap for component in projection.components]
    assert gaps == pytest.approx([0.2, 0.8], abs=1e-15)
    assert [c.parallel for c in projection.components] == pytest.approx([0.0, 0.0], abs=1e-16)
    assert [c.orthogonal for c in projection.components] == pytest.approx([0.2, 0.8], abs=1e-15)

    # The orthogonal residual is nonzero even though D_government vanishes.
    assert projection.weighted_norm_orthogonal > 0.1
    assert projection.orthogonality_error <= ORTHOGONALITY_MAX
    assert decompose(outcome).d_government == pytest.approx(0.0, abs=1e-16)


def test_weighted_orthogonality_holds_on_every_resolvable_finite_fixture(frozen_fixtures):
    for name, item in frozen_fixtures.items():
        if item.declared_branch == BRANCH_LITERAL_LAISSEZ_FAIRE:
            continue
        projection = project_fiscal_gap(evaluate_kernels(item))
        if projection.status != PROJECTION_RESOLVED:
            continue
        assert projection.orthogonality_error <= ORTHOGONALITY_MAX, name


def test_zero_payoff_norm_is_refused_not_normalized(frozen_fixtures):
    projection = project_fiscal_gap(
        evaluate_kernels(frozen_fixtures["all_zero_payoff_unidentified"])
    )
    assert projection.status == ZERO_PAYOFF_NORM_REFUSED
    assert projection.alpha is None
    assert projection.components == ()
    with pytest.raises(RuntimeError):
        projection.require_alpha()


def test_a_catastrophically_cancelled_payoff_norm_is_refused():
    """A weighted norm that survives only as rounding noise is refused rather than
    reported as a direction."""
    tiny = 5.0e-200
    item = fixture(
        "tiny_norm",
        (mark("P", 0.2, 0.1, tiny, 1.0), mark("F", 0.1, 0.05, -tiny, 1.0)),
    )
    projection = project_fiscal_gap(evaluate_kernels(item))
    assert projection.status in {ZERO_PAYOFF_NORM_REFUSED, UNRESOLVED_PAYOFF_NORM_REFUSED}
    assert projection.alpha is None


def test_safe_account_has_zero_marked_payoff_and_does_not_change_risky_rank(frozen_fixtures):
    outcome = evaluate_kernels(frozen_fixtures["two_mark_orthogonal_gap"])
    safe = safe_account_rank(outcome)
    assert safe.safe_payoff_vector == (0.0, 0.0)
    assert safe.safe_account_has_zero_marked_payoff
    assert safe.rank_risky == 1
    assert safe.rank_with_safe_account == 1
    assert safe.rank_increase == 0


def test_safe_account_rank_is_zero_when_every_payoff_component_is_zero(frozen_fixtures):
    """An exact zero jump is a change in rank, not poor conditioning."""
    safe = safe_account_rank(
        evaluate_kernels(frozen_fixtures["all_zero_payoff_unidentified"])
    )
    assert safe.rank_risky == 0
    assert safe.rank_with_safe_account == 0
    assert safe.rank_increase == 0


def test_the_safe_account_is_never_sent_through_the_projection_routine(frozen_fixtures):
    """The projection routine is only ever handed the risky payoff vector; the safe
    account's zero vector reaches ``safe_account_rank`` instead."""
    outcome = evaluate_kernels(frozen_fixtures["two_mark_orthogonal_gap"])
    projection = project_fiscal_gap(outcome)
    payoffs = tuple(component.payoff_jump for component in projection.components)
    assert payoffs == tuple(m.payoff_jump for m in outcome.require_finite())
    assert any(jump != 0.0 for jump in payoffs)


# --- literal laissez-faire boundary ------------------------------------------------


def test_literal_laissez_faire_is_a_tagged_extended_real_boundary(frozen_fixtures):
    outcome = evaluate_kernels(frozen_fixtures["literal_laissez_faire_full_ak"])
    assert outcome.status == NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE
    assert outcome.marks == ()
    assert outcome.worker_consumption.require_finite() == 0.0
    (only,) = outcome.boundary_marks
    assert only.k_government.kind == POSITIVE_INFINITY
    assert only.gamma.kind == POSITIVE_INFINITY
    assert only.k_owner.require_finite() == pytest.approx(0.5, abs=1e-15)
    assert only.k_world.require_finite() == pytest.approx(0.5, abs=1e-15)


def test_no_finite_arithmetic_runs_at_the_boundary(frozen_fixtures):
    outcome = evaluate_kernels(frozen_fixtures["literal_laissez_faire_full_ak"])
    with pytest.raises(KernelRefusal):
        decompose(outcome)
    with pytest.raises(KernelRefusal):
        solve_owner_root(outcome)
    with pytest.raises(KernelRefusal):
        project_fiscal_gap(outcome)
    with pytest.raises(ExtendedRealError):
        outcome.boundary_marks[0].k_government.require_finite()


def test_the_boundary_serializes_without_a_sentinel_or_a_non_standard_token(frozen_fixtures):
    outcome = evaluate_kernels(frozen_fixtures["literal_laissez_faire_full_ak"])
    payload = outcome.boundary_marks[0].k_government.to_json()
    assert payload == {"kind": "positive_infinity", "value": None}
    # The kind is a string label; the numeric slot is null, so no non-standard
    # ``Infinity`` token and no large finite sentinel is ever emitted.
    text = json.dumps(payload, allow_nan=False)
    assert "Infinity" not in text
    assert payload["value"] is None
    assert json.loads(text) == payload
    assert ExtendedReal.from_json(payload) == outcome.boundary_marks[0].k_government


def test_the_relative_kernel_is_undefined_when_the_owner_kernel_is_itself_invalid():
    item = fixture(
        "boundary_bad_owner",
        (mark("F", 0.20, 0.10, 0.50, ExtendedReal(POSITIVE_INFINITY)),),
        owner_exposure=-2.0,  # 1 + pi*J = 0 exactly: an inadmissible private portfolio
        government_current_marginal_value=2.0,
        declared_branch=BRANCH_LITERAL_LAISSEZ_FAIRE,
        worker_consumption=0.0,
    )
    outcome = evaluate_kernels(item)
    assert outcome.status == NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE
    (only,) = outcome.boundary_marks
    assert only.k_owner.kind == UNDEFINED
    assert only.gamma.kind == UNDEFINED
    with pytest.raises(ExtendedRealError):
        only.gamma.as_float()


def test_a_boundary_fixture_must_actually_declare_zero_worker_consumption():
    item = fixture(
        "mislabelled_boundary",
        (mark("F", 0.20, 0.10, 0.50, ExtendedReal(POSITIVE_INFINITY)),),
        declared_branch=BRANCH_LITERAL_LAISSEZ_FAIRE,
        worker_consumption=0.25,
    )
    assert evaluate_kernels(item).status != NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE


def test_extended_real_rejects_a_value_on_a_non_finite_kind():
    with pytest.raises(ValueError):
        ExtendedReal(POSITIVE_INFINITY, 1.0e308)
    with pytest.raises(ValueError):
        ExtendedReal("finite", math.inf)
