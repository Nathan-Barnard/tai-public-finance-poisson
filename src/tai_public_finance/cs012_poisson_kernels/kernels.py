"""The three jump pricing kernels and the literal laissez-faire boundary.

Formulas, frozen by CS012 v0.1 "Timing and coordinate conventions":

    k_world[j]                 = lambda_risk_neutral[j] / lambda_physical[j]
    owner_wealth_multiplier[j] = 1 + owner_exposure * payoff_jump[j]
    k_owner[j]                 = 1 / owner_wealth_multiplier[j]
    k_government[j]            = government_successor_marginal_value[j]
                                 / government_current_marginal_value
    gamma[j]                   = k_government[j] / k_owner[j]

The world kernel prices internationally traded payoffs; the owner kernel is the
domestic log owner's marginal-utility ratio; the government kernel is a fiscal
marginal-value object and is *not* a second market stochastic discount factor.
The three stay distinct objects here and downstream.

The finite maintained branch requires strictly positive physical intensities,
strictly positive current and successor government marginal values, and strictly
positive owner wealth multipliers; the world risk-neutral intensity is only
required to be nonnegative. A non-positive wealth multiplier is an inadmissible
private portfolio, not a large finite kernel. The only admissible positive
infinity is an explicitly declared literal-laissez-faire boundary value.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .extended import (
    POSITIVE_INFINITE,
    UNDEFINED_VALUE,
    ExtendedReal,
)
from .inputs import FixtureInput, MarkInput
from .statuses import (
    BRANCH_LITERAL_LAISSEZ_FAIRE,
    FINITE_MAINTAINED_BRANCH,
    INVALID_DIRECT_WEALTH_RATIO,
    NONFINITE_FINITE_BRANCH_INPUT,
    NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE,
)

WEALTH_ROUTE_TOLERANCE = 1.0e-12
"""Maximum normalized disagreement between the ``owner_exposure`` route and the
``owner_wealth_before``/``owner_wealth_after`` route before the input is refused."""


class KernelRefusal(RuntimeError):
    """Raised when finite kernel values are demanded from a refused evaluation."""

    def __init__(self, status: str, detail: str) -> None:
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


@dataclass(frozen=True, slots=True)
class MarkKernels:
    """Finite kernel values for one labelled mark. All fields are ordinary floats
    because this object is only ever constructed on the finite maintained branch."""

    mark_id: str
    lambda_physical: float
    lambda_risk_neutral: float
    payoff_jump: float
    owner_wealth_multiplier: float
    k_world: float
    k_owner: float
    k_government: float
    gamma: float


@dataclass(frozen=True, slots=True)
class BoundaryKernels:
    """The literal laissez-faire extended-real boundary for one labelled mark.

    CS012 v0.1, I2: where the full-AK successor gives zero wage and zero worker
    consumption, the government's successor marginal value and jump kernel are
    ``+inf``. The relative kernel is ``+inf`` too, unless the owner kernel is
    itself invalid, in which case it is explicitly ``undefined`` rather than any
    number. No ``log(0)`` is evaluated, nothing is replaced by machine epsilon,
    and no kernel is capped.
    """

    mark_id: str
    lambda_physical: float
    lambda_risk_neutral: float
    payoff_jump: float
    k_world: ExtendedReal
    owner_wealth_multiplier: ExtendedReal
    k_owner: ExtendedReal
    k_government: ExtendedReal
    gamma: ExtendedReal


@dataclass(frozen=True, slots=True)
class KernelOutcome:
    """Tagged result of evaluating one fixture's kernels.

    ``status`` is authoritative and always set. ``marks`` is populated only on the
    finite maintained branch; ``boundary_marks`` only at the declared literal
    laissez-faire boundary. ``detail`` is a human-readable note, never the signal.
    """

    fixture_id: str
    status: str
    detail: str
    marks: tuple[MarkKernels, ...] = ()
    boundary_marks: tuple[BoundaryKernels, ...] = ()
    worker_consumption: ExtendedReal | None = None

    @property
    def is_finite_branch(self) -> bool:
        return self.status == FINITE_MAINTAINED_BRANCH

    def require_finite(self) -> tuple[MarkKernels, ...]:
        """Finite kernels, or a raise. Never a ``None``, ``NaN``, or empty tuple
        standing in for a refusal."""
        if not self.is_finite_branch:
            raise KernelRefusal(self.status, self.detail)
        return self.marks


def _owner_multiplier(exposure: float, payoff_jump: float) -> float:
    return 1.0 + exposure * payoff_jump


def _wealth_route_disagreement(mark: MarkInput, multiplier: float) -> float | None:
    """Normalized gap between the two owner-kernel routes, or ``None`` if the
    wealth-ratio route was not supplied. A structurally unusable ratio returns
    ``math.inf`` so the caller refuses it."""
    if mark.owner_wealth_before is None or mark.owner_wealth_after is None:
        return None
    before = mark.owner_wealth_before
    after = mark.owner_wealth_after
    if not math.isfinite(before) or not math.isfinite(after) or before <= 0.0 or after <= 0.0:
        return math.inf
    ratio = after / before
    if not math.isfinite(ratio) or ratio <= 0.0:
        return math.inf
    return abs(ratio - multiplier) / max(1.0, abs(ratio), abs(multiplier))


def evaluate_kernels(fixture: FixtureInput) -> KernelOutcome:
    """Evaluate the world, owner, and government kernels for one fixture.

    Returns a tagged outcome; it never raises on an inadmissible economic input.
    Structurally malformed input is a parse-time ``InputError`` instead.
    """
    if fixture.declared_branch == BRANCH_LITERAL_LAISSEZ_FAIRE:
        return _evaluate_literal_laissez_faire(fixture)
    return _evaluate_finite_branch(fixture)


def _evaluate_finite_branch(fixture: FixtureInput) -> KernelOutcome:
    exposure = fixture.owner_exposure
    mu_current = fixture.government_current_marginal_value

    if not math.isfinite(exposure):
        return KernelOutcome(
            fixture.fixture_id,
            NONFINITE_FINITE_BRANCH_INPUT,
            "owner_exposure is not finite",
        )
    if not math.isfinite(mu_current) or mu_current <= 0.0:
        return KernelOutcome(
            fixture.fixture_id,
            NONFINITE_FINITE_BRANCH_INPUT,
            "government_current_marginal_value must be finite and strictly positive",
        )

    computed: list[MarkKernels] = []
    for mark in fixture.marks:
        tag = f"mark {mark.mark_id}"
        if not math.isfinite(mark.lambda_physical) or mark.lambda_physical <= 0.0:
            return KernelOutcome(
                fixture.fixture_id,
                NONFINITE_FINITE_BRANCH_INPUT,
                f"{tag}: lambda_physical must be finite and strictly positive",
            )
        if not math.isfinite(mark.lambda_risk_neutral) or mark.lambda_risk_neutral < 0.0:
            return KernelOutcome(
                fixture.fixture_id,
                NONFINITE_FINITE_BRANCH_INPUT,
                f"{tag}: lambda_risk_neutral must be finite and nonnegative",
            )
        if not math.isfinite(mark.payoff_jump):
            return KernelOutcome(
                fixture.fixture_id,
                NONFINITE_FINITE_BRANCH_INPUT,
                f"{tag}: payoff_jump must be finite",
            )
        successor = mark.government_successor_marginal_value
        if not successor.is_finite:
            return KernelOutcome(
                fixture.fixture_id,
                NONFINITE_FINITE_BRANCH_INPUT,
                f"{tag}: government_successor_marginal_value is {successor.kind} on a "
                "finite maintained branch; only an explicitly declared literal "
                "laissez-faire fixture may carry positive infinity",
            )
        successor_value = successor.require_finite()
        if successor_value <= 0.0:
            return KernelOutcome(
                fixture.fixture_id,
                NONFINITE_FINITE_BRANCH_INPUT,
                f"{tag}: government_successor_marginal_value must be strictly positive",
            )

        multiplier = _owner_multiplier(exposure, mark.payoff_jump)
        if not math.isfinite(multiplier) or multiplier <= 0.0:
            return KernelOutcome(
                fixture.fixture_id,
                NONFINITE_FINITE_BRANCH_INPUT,
                f"{tag}: owner wealth multiplier 1+pi*J = {multiplier!r} is not "
                "strictly positive; this is an inadmissible private portfolio, "
                "not a large finite kernel",
            )

        disagreement = _wealth_route_disagreement(mark, multiplier)
        if disagreement is not None and (
            not math.isfinite(disagreement) or disagreement > WEALTH_ROUTE_TOLERANCE
        ):
            return KernelOutcome(
                fixture.fixture_id,
                INVALID_DIRECT_WEALTH_RATIO,
                f"{tag}: owner wealth-ratio route disagrees with the owner_exposure "
                f"route by {disagreement!r} (normalized), or is structurally unusable",
            )

        k_world = mark.lambda_risk_neutral / mark.lambda_physical
        k_owner = 1.0 / multiplier
        k_government = successor_value / mu_current
        gamma = k_government / k_owner
        for name, value in (
            ("k_world", k_world),
            ("k_owner", k_owner),
            ("k_government", k_government),
            ("gamma", gamma),
        ):
            if not math.isfinite(value):
                return KernelOutcome(
                    fixture.fixture_id,
                    NONFINITE_FINITE_BRANCH_INPUT,
                    f"{tag}: {name} evaluated to a non-finite value",
                )
        computed.append(
            MarkKernels(
                mark_id=mark.mark_id,
                lambda_physical=mark.lambda_physical,
                lambda_risk_neutral=mark.lambda_risk_neutral,
                payoff_jump=mark.payoff_jump,
                owner_wealth_multiplier=multiplier,
                k_world=k_world,
                k_owner=k_owner,
                k_government=k_government,
                gamma=gamma,
            )
        )

    return KernelOutcome(
        fixture.fixture_id,
        FINITE_MAINTAINED_BRANCH,
        "all kernels finite and positive on the maintained branch",
        marks=tuple(computed),
        worker_consumption=(
            None
            if fixture.worker_consumption is None
            else ExtendedReal.of(fixture.worker_consumption)
        ),
    )


def _evaluate_literal_laissez_faire(fixture: FixtureInput) -> KernelOutcome:
    """Literal laissez-faire: zero public tax, transfer, equity, money-market, and
    net-wealth positions, so the full-AK successor leaves workers with zero
    consumption. The fiscal kernel is ``+inf`` by construction, and this outcome
    deliberately carries no finite residual arithmetic."""
    if fixture.worker_consumption is None or fixture.worker_consumption != 0.0:
        return KernelOutcome(
            fixture.fixture_id,
            NONFINITE_FINITE_BRANCH_INPUT,
            "a literal_laissez_faire fixture must declare worker_consumption = 0",
        )
    mu_current = fixture.government_current_marginal_value
    if not math.isfinite(mu_current) or mu_current <= 0.0:
        return KernelOutcome(
            fixture.fixture_id,
            NONFINITE_FINITE_BRANCH_INPUT,
            "the pre-event government marginal value must still be finite and "
            "strictly positive at the literal laissez-faire boundary",
        )

    boundary: list[BoundaryKernels] = []
    for mark in fixture.marks:
        successor = mark.government_successor_marginal_value
        if successor.kind != POSITIVE_INFINITE.kind:
            return KernelOutcome(
                fixture.fixture_id,
                NONFINITE_FINITE_BRANCH_INPUT,
                f"mark {mark.mark_id}: a literal laissez-faire fixture declares a "
                "positive-infinite successor government marginal value",
            )
        multiplier = _owner_multiplier(fixture.owner_exposure, mark.payoff_jump)
        owner_valid = math.isfinite(multiplier) and multiplier > 0.0
        k_owner = (
            ExtendedReal.of(1.0 / multiplier) if owner_valid else UNDEFINED_VALUE
        )
        k_world = (
            ExtendedReal.of(mark.lambda_risk_neutral / mark.lambda_physical)
            if math.isfinite(mark.lambda_physical) and mark.lambda_physical > 0.0
            else UNDEFINED_VALUE
        )
        boundary.append(
            BoundaryKernels(
                mark_id=mark.mark_id,
                lambda_physical=mark.lambda_physical,
                lambda_risk_neutral=mark.lambda_risk_neutral,
                payoff_jump=mark.payoff_jump,
                k_world=k_world,
                owner_wealth_multiplier=(
                    ExtendedReal.of(multiplier) if owner_valid else UNDEFINED_VALUE
                ),
                k_owner=k_owner,
                k_government=POSITIVE_INFINITE,
                # gamma = k_government / k_owner is +inf for a finite positive
                # owner kernel, and undefined -- not a number -- otherwise.
                gamma=POSITIVE_INFINITE if owner_valid else UNDEFINED_VALUE,
            )
        )

    return KernelOutcome(
        fixture.fixture_id,
        NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE,
        "full-AK continuation with zero public wealth and transfers gives "
        "hand-to-mouth workers zero consumption; the fiscal marginal value is "
        "not finite and is excluded from all residual arithmetic",
        boundary_marks=tuple(boundary),
        worker_consumption=ExtendedReal.of(0.0),
    )


__all__ = [
    "WEALTH_ROUTE_TOLERANCE",
    "BoundaryKernels",
    "KernelOutcome",
    "KernelRefusal",
    "MarkKernels",
    "evaluate_kernels",
]
