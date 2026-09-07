"""CS012 block I2a: the literal laissez-faire boundary and the positive-prefunding family.

Successor-side objects only. For each inherited public safe buffer ``F > 0``, with
public installed equity ``Theta = 0``, safe debt ``B = -F``, and source tax ``tau = 0``:

    e_j^+   = F - q_j(K) K                      event map, K continuous
    X_P     = F + H_P(K) - q_P(K) K             partial-automation worker resources
    X_F     = F                                 full-AK: productive human wealth
                                                exactly offsets installed-capital value
    C_j^W   = rho X_j                           log optimum after arrival
    V_{j,e} = 1/(rho X_j)                       successor marginal value

At ``F = 0`` the full-AK branch has zero worker consumption and a non-finite successor
marginal value. That point is held outside every logarithm, finite difference and
finite-axis calculation, and is returned as an explicitly tagged extended real. The
partial branch stays finite there whenever ``H_P(K) - q_P(K) K > 0``, and that contrast
is the substantive content of the block.

**A successor marginal value is not a government kernel.** ``k^G_j = V_{j,e}/mu_e``
needs the pre-event optimized government marginal value, which :func:`audit_mu_e_closure`
looks for and, at the pinned commits, does not find. Nothing here divides by anything.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .extended import POSITIVE_INFINITE, ExtendedReal
from .i2_packets import LITERAL_BOUNDARY_STATUS

MU_E_UNAVAILABLE = "unavailable_missing_optimized_pre_event_value_gradient"
MU_E_AVAILABLE = "available_optimized_pre_event_value_gradient"

FORBIDDEN_MU_E_SUBSTITUTES = (
    "unit normalization mu_e = 1",
    "1/C_0 or 1/W_0 without a solved optimized continuation",
    "the domestic owner's kernel",
    "the world kernel",
    "a fixed-policy value derivative",
    "a value from an unpinned or unapproved dependency revision",
    "a newly invented pre-event equation, terminal condition, or policy rule",
)


class PrefundingError(RuntimeError):
    """A structural or domain condition of the prefunding family failed."""


# --- pre-event mu_e closure audit ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClosureAudit:
    """Result of the read-only search for a valid pre-event optimized ``mu_e``."""

    status: str
    detail: str
    evidence: tuple[str, ...]
    missing_object: str
    missing_interface: str

    @property
    def government_kernels_permitted(self) -> bool:
        return self.status == MU_E_AVAILABLE

    def as_dict(self) -> dict[str, Any]:
        return {
            "pre_event_mu_e_status": self.status,
            "detail": self.detail,
            "evidence": list(self.evidence),
            "missing_computational_object": self.missing_object,
            "missing_interface": self.missing_interface,
            "government_kernels_permitted": self.government_kernels_permitted,
            "forbidden_substitutes_not_used": list(FORBIDDEN_MU_E_SUBSTITUTES),
        }


def audit_mu_e_closure() -> ClosureAudit:
    """Search the installed pinned dependency for a solved pre-event ``mu_e``.

    This introspects what is actually installed rather than asserting a conclusion. A
    valid ``mu_e`` must be the derivative of the *optimized* pre-event government
    continuation with respect to public net wealth, under the same state, controls,
    timing, zero-tax continuation, boundary and terminal condition, and TVCs. A module
    that supplies the costate *equations* does not supply their solution.
    """
    import importlib
    import inspect

    evidence: list[str] = []
    solver_found = False

    try:
        canonical = importlib.import_module("ak_partial_ramsey.canonical")
    except ImportError:
        canonical = None
        evidence.append(
            "ak_partial_ramsey.canonical is not importable at the pinned commit"
        )
    if canonical is not None:
        doc = inspect.getdoc(canonical) or ""
        evidence.append(
            "ak_partial_ramsey.canonical supplies the four-dimensional pre-arrival "
            "costate system for z = (K, e, mu_K, mu_e) as EQUATIONS only; its own "
            "module docstring states that solving the transition boundary-value "
            "problem is block N4 and is deliberately not implemented there"
            + (" (docstring confirms 'not implemented here')" if "not implemented here" in doc else "")
        )
        # Every mu_e-aware callable takes mu_e as an input; none returns one.
        consumers = []
        for name, function in inspect.getmembers(canonical, inspect.isfunction):
            try:
                parameters = inspect.signature(function).parameters
            except (TypeError, ValueError):
                continue
            if "mu_e" in parameters:
                consumers.append(name)
        if consumers:
            evidence.append(
                "every mu_e-aware callable there accepts mu_e as a caller-supplied "
                f"argument and none returns it: {sorted(consumers)}"
            )

    try:
        assembly = importlib.import_module("ak_partial_ramsey.assembly")
        parameters = inspect.signature(assembly.evaluate_state).parameters
        if "C" in parameters and "q_dot" in parameters:
            evidence.append(
                "ak_partial_ramsey.assembly.evaluate_state requires pre-event "
                "consumption C and the price drift q_dot as caller-supplied inputs, so "
                "the only mu_e it could express is 1/C at a supplied C -- a "
                "fixed-policy derivative, not an optimized one"
            )
    except (ImportError, AttributeError):
        evidence.append("ak_partial_ramsey.assembly.evaluate_state is not available")

    for module_name in (
        "ak_partial_ramsey.stationary",
        "ak_partial_ramsey.continuation",
        "ak_partial_ramsey.certificate",
    ):
        try:
            importlib.import_module(module_name)
            solver_found = True
            evidence.append(f"{module_name} IS present at the installed commit")
        except ImportError:
            evidence.append(f"{module_name} is absent at the pinned commit")

    if solver_found:
        return ClosureAudit(
            status=MU_E_UNAVAILABLE,
            detail=(
                "A pre-arrival solver module is present, which is not the pinned "
                "configuration this block audited. Stop and re-audit rather than using "
                "it: a dependency pin change is out of scope here."
            ),
            evidence=tuple(evidence),
            missing_object="a re-audit against the actually installed dependency",
            missing_interface="unchanged pin, or a new approved pin with its own audit",
        )

    return ClosureAudit(
        status=MU_E_UNAVAILABLE,
        detail=(
            "No optimized pre-event government value gradient exists at the pinned "
            "commits. The pre-arrival costate system is available only as equations; "
            "solving it is CS011 block N4, which is not implemented at the pinned "
            "commit. The single candidate, mu_e = 1/C from the interior "
            "consumption first-order condition, requires C from a solved optimized "
            "pre-arrival continuation; supplying C by hand would make it a "
            "fixed-policy derivative, which CS012 explicitly excludes -- the "
            "specification requires the derivative of the *optimized* government "
            "continuation, 'not the derivative of a rule that mechanically fixes all "
            "laissez-faire policies after a marginal resource arrives'. No substitute "
            "was used and no finite government kernel is reported."
        ),
        evidence=tuple(evidence),
        missing_object=(
            "mu_e(K_0, e_0): the gradient in public net wealth of the optimized "
            "pre-event government continuation value, on the maintained zero-tax "
            "admissible branch with its boundary/terminal conditions and TVCs"
        ),
        missing_interface=(
            "a solved pre-arrival transition (CS011 block N4) returning the converged "
            "costate pair (mu_K, mu_e) at the reference state, together with the "
            "branch, terminal condition and TVC certificates under which it was solved"
        ),
    )


# --- successor rows --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SuccessorRow:
    """One mark's successor-side quantities at one positive prefunding level."""

    mark_id: str
    is_exact: bool
    relaxation_label: str
    prefunding_level: float
    event_wealth_coordinate: float
    productive_wealth: float
    installed_capital_value: float
    worker_resources: float
    worker_consumption: float
    successor_marginal_value: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "mark_id": self.mark_id,
            "is_exact": self.is_exact,
            "relaxation_label": self.relaxation_label,
            "prefunding_level_F": self.prefunding_level,
            "event_wealth_coordinate_e_plus": self.event_wealth_coordinate,
            "productive_wealth_H": self.productive_wealth,
            "installed_capital_value_qK": self.installed_capital_value,
            "worker_resources_X": self.worker_resources,
            "worker_consumption_C_W": self.worker_consumption,
            "successor_marginal_value_V_e": self.successor_marginal_value,
        }


def unrestricted_upper_relaxation_row(
    mark_id: str,
    F: float,
    rho: float,
    productive_wealth: float,
    installed_capital_value: float,
    *,
    wage_floor: float,
) -> SuccessorRow:
    """The **unrestricted** annuity row: ``C = rho X``, ``V = 1/(rho X)``.

    This is an economically valid successor value only where the nonnegative-transfer
    constraint is slack for all ``t``, which by (12.6)-(12.7) requires
    ``X >= sup_t e^{-(r-rho)t} W(K_t)/rho``. With a strictly positive wage floor that is
    a real restriction, and where it fails the value here is an **upper relaxation
    only** -- it prices a consumption path that would need a negative transfer.

    ``wage_floor`` must therefore be supplied explicitly. A zero floor (the full-AK
    branch, ``W_F = 0``) makes the row exact; a positive floor marks it as a relaxation,
    and the caller must obtain a transfer-slack certificate, or use the constrained
    solver in :mod:`~tai_public_finance.cs012_poisson_kernels.i2b_constrained`, before
    treating it as an economic successor value.

    Renamed from ``successor_row`` after review found the historical I2a partial rows
    had used it outside its transfer-feasible domain.
    """
    if not math.isfinite(F) or F <= 0.0:
        raise PrefundingError(
            f"mark {mark_id}: the finite branch takes strictly positive F only; "
            "F = 0 is the literal boundary and is handled separately"
        )
    X = F + productive_wealth - installed_capital_value
    if not math.isfinite(X) or X <= 0.0:
        raise PrefundingError(
            f"mark {mark_id}: worker resources X = {X!r} are not strictly positive, so "
            "the log continuation is undefined; no floor is substituted"
        )
    return SuccessorRow(
        mark_id=mark_id,
        is_exact=wage_floor == 0.0,
        relaxation_label=(
            "exact_zero_wage_floor" if wage_floor == 0.0 else "unrestricted_upper_relaxation"
        ),
        prefunding_level=F,
        event_wealth_coordinate=F - installed_capital_value,
        productive_wealth=productive_wealth,
        installed_capital_value=installed_capital_value,
        worker_resources=X,
        worker_consumption=rho * X,
        successor_marginal_value=1.0 / (rho * X),
    )


@dataclass(frozen=True, slots=True)
class LiteralBoundary:
    """The exact ``F = 0`` full-AK laissez-faire boundary, as extended reals."""

    status: str
    worker_consumption: ExtendedReal
    successor_marginal_value: ExtendedReal
    partial_worker_resources: ExtendedReal
    partial_successor_marginal_value: ExtendedReal
    contrast: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "prefunding_level_F": 0.0,
            "full_ak": {
                "worker_consumption": self.worker_consumption.to_json(),
                "successor_marginal_value": self.successor_marginal_value.to_json(),
            },
            "partial_automation": {
                "worker_resources_X": self.partial_worker_resources.to_json(),
                "successor_marginal_value": self.partial_successor_marginal_value.to_json(),
            },
            "contrast": self.contrast,
            "excluded_from_logarithms_and_finite_differences": True,
        }


def literal_boundary(rho: float, partial_residual_wealth: float) -> LiteralBoundary:
    """Classify ``F = 0`` exactly.

    Full AK: productive human wealth exactly offsets installed-capital value, so
    ``X_F = F = 0``, worker consumption is exactly zero and the successor marginal value
    is positive infinity. No logarithm of zero is evaluated, nothing is replaced by an
    epsilon, and nothing is capped.

    Partial automation: ``X_P = H_P(K) - q_P(K) K`` at ``F = 0``, which stays strictly
    positive at this baseline, so its marginal value has a finite limit.
    """
    if partial_residual_wealth > 0.0:
        partial_X = ExtendedReal.of(partial_residual_wealth)
        partial_V = ExtendedReal.of(1.0 / (rho * partial_residual_wealth))
        contrast = (
            "Full automation eliminates worker human wealth, so worker consumption is "
            "exactly zero at F = 0 and the successor marginal value is positive "
            "infinity. Partial automation retains strictly positive worker human wealth "
            f"net of installed-capital value ({partial_residual_wealth!r}), so its "
            "successor marginal value has a finite limit. The two branches are "
            "structurally different at the boundary, not merely different in scale."
        )
    else:
        partial_X = ExtendedReal.of(partial_residual_wealth)
        partial_V = POSITIVE_INFINITE
        contrast = (
            "Both branches lose worker resources at F = 0 under this baseline, so both "
            "successor marginal values diverge."
        )
    return LiteralBoundary(
        status=LITERAL_BOUNDARY_STATUS,
        worker_consumption=ExtendedReal.of(0.0),
        successor_marginal_value=POSITIVE_INFINITE,
        partial_worker_resources=partial_X,
        partial_successor_marginal_value=partial_V,
        contrast=contrast,
    )


# --- elasticities and transversality ---------------------------------------------------


def adjacent_log_log_elasticities(
    levels: tuple[float, ...], values: tuple[float, ...]
) -> tuple[float, ...]:
    """``dlog V / dlog F`` between adjacent *positive* points only.

    Refuses a non-positive level or value rather than dropping it silently: the literal
    boundary must never reach a logarithm.
    """
    if len(levels) != len(values):
        raise PrefundingError("levels and values must have the same length")
    for level, value in zip(levels, values, strict=True):
        if level <= 0.0 or value <= 0.0:
            raise PrefundingError(
                "log-log elasticities are defined on strictly positive points only; "
                f"received level {level!r} and value {value!r}"
            )
    return tuple(
        (math.log(values[i + 1]) - math.log(values[i]))
        / (math.log(levels[i + 1]) - math.log(levels[i]))
        for i in range(len(levels) - 1)
    )


def safe_position_tvc(rho: float, r_bar: float) -> dict[str, Any]:
    """Discounted gross safe-position transversality on the full-AK branch.

    With ``X_F = F``, ``C_F = rho F`` and ``Fdot = (r_bar - rho) F``, the utility-value
    discounted position is ``e^{-rho t} V_{F,e}(t) F(t) = e^{-rho t}/rho``, which
    vanishes for any ``rho > 0``; and the market-discounted position is
    ``e^{-r_bar t} F(t) = F e^{-rho t}``, which vanishes on the same condition. Both are
    reported rather than one being taken as decisive.
    """
    return {
        "F_growth_rate": r_bar - rho,
        "utility_discounted_limit_exponent": -rho,
        "market_discounted_limit_exponent": -rho,
        "utility_discounted_tvc_holds": rho > 0.0,
        "market_discounted_tvc_holds": rho > 0.0,
        "detail": (
            "e^{-rho t} V_{F,e}(t) F(t) = e^{-rho t}/rho -> 0 and "
            "e^{-r_bar t} F(t) = F e^{-rho t} -> 0, both for rho > 0"
        ),
    }


__all__ = [
    "FORBIDDEN_MU_E_SUBSTITUTES",
    "MU_E_AVAILABLE",
    "MU_E_UNAVAILABLE",
    "ClosureAudit",
    "LiteralBoundary",
    "PrefundingError",
    "SuccessorRow",
    "adjacent_log_log_elasticities",
    "audit_mu_e_closure",
    "literal_boundary",
    "safe_position_tvc",
    "unrestricted_upper_relaxation_row",
]
