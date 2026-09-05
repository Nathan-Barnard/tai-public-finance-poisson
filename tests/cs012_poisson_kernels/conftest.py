"""Shared fixtures for the CS012 I0 identity-core tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tai_public_finance.cs012_poisson_kernels.extended import ExtendedReal
from tai_public_finance.cs012_poisson_kernels.inputs import (
    FixtureInput,
    MarkInput,
    load_fixtures,
)
from tai_public_finance.cs012_poisson_kernels.statuses import (
    BRANCH_FINITE_MAINTAINED,
    BRANCH_LITERAL_LAISSEZ_FAIRE,
)

REPOSITORY = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPOSITORY / "configs" / "cs012" / "i0_manufactured_fixtures.json"


def finite_value(value: float) -> ExtendedReal:
    return ExtendedReal.of(value)


def mark(
    mark_id: str,
    lambda_physical: float,
    lambda_risk_neutral: float,
    payoff_jump: float,
    successor: float | ExtendedReal,
    *,
    owner_wealth_before: float | None = None,
    owner_wealth_after: float | None = None,
) -> MarkInput:
    return MarkInput(
        mark_id=mark_id,
        lambda_physical=lambda_physical,
        lambda_risk_neutral=lambda_risk_neutral,
        payoff_jump=payoff_jump,
        government_successor_marginal_value=(
            successor if isinstance(successor, ExtendedReal) else ExtendedReal.of(successor)
        ),
        owner_wealth_before=owner_wealth_before,
        owner_wealth_after=owner_wealth_after,
    )


def fixture(
    fixture_id: str,
    marks: tuple[MarkInput, ...],
    *,
    owner_exposure: float = 0.0,
    government_current_marginal_value: float = 1.0,
    declared_branch: str = BRANCH_FINITE_MAINTAINED,
    worker_consumption: float | None = None,
) -> FixtureInput:
    return FixtureInput(
        fixture_id=fixture_id,
        declared_branch=declared_branch,
        owner_exposure=owner_exposure,
        government_current_marginal_value=government_current_marginal_value,
        marks=marks,
        worker_consumption=worker_consumption,
    )


@pytest.fixture(scope="session")
def fixture_path() -> Path:
    return FIXTURE_PATH


@pytest.fixture(scope="session")
def frozen_fixtures() -> dict[str, FixtureInput]:
    return {item.fixture_id: item for item in load_fixtures(FIXTURE_PATH)}


__all__ = [
    "BRANCH_FINITE_MAINTAINED",
    "BRANCH_LITERAL_LAISSEZ_FAIRE",
    "FIXTURE_PATH",
    "REPOSITORY",
    "finite_value",
    "fixture",
    "mark",
]
