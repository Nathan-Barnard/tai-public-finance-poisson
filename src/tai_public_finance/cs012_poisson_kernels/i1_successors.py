"""Bridge from a CS012 I1 packet to the pinned CS011 N1 successor services.

The CS011 dependency is pinned by full commit in ``pyproject.toml``/``uv.lock``. Only
four of its surfaces are imported here, exactly as the I1 handoff permits:

* ``params``      -- immutable parameter and domain schemas;
* ``tolerances``  -- solver settings (never thresholds that decide a result);
* ``successors.ak``      -- the absorbing AK successor service; and
* ``successors.partial`` -- the fixed-``I_P`` stable-manifold successor service,

plus ``fixtures`` for the synthetic packet, which is pure data construction over those
same schemas and contains no solver or model equation.

Deliberately **not** imported: the CS011 stationary, continuation, certificate,
recovery, rows, profiles, evaluator, or assembly machinery (its N2/N3 layer), and its
``exposure`` module. The owner portfolio root is CS012's own object and is solved with
the reviewed CS012 I0 functions, not with the dependency's private-portfolio solver.

No CS011 equation is copied. The payoff convention below is CS012's, stated in the I1
handoff:

    J_j(K) = q_j(K)/q_0 - 1
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ak_partial_ramsey.fixtures import get_fixture
from ak_partial_ramsey.params import (
    AkRootInterval,
    AkTechnology,
    Installation,
    MarkIntensities,
    ModelParameters,
    PartialCapitalInterval,
    Preferences,
    TaskTechnology,
    WorldRates,
)
from ak_partial_ramsey.successors.ak import AkSuccessor, solve_ak_successor
from ak_partial_ramsey.successors.partial import PartialSuccessor, solve_partial_successor
from ak_partial_ramsey.tolerances import SolverTolerances

from .i1_packets import EconomicPacket

MARK_P = "P"
MARK_F = "F"
MARK_ORDER = (MARK_P, MARK_F)
"""Mark labels are carried explicitly and never sorted or relabelled by payoff size."""


def dependency_provenance() -> dict[str, Any]:
    """The resolved dependency distribution, read from installed metadata.

    Reading the resolved commit back from ``direct_url.json`` rather than from the
    lockfile means the report records what actually ran, not what was requested.
    """
    import importlib.metadata as metadata
    import json as _json

    distribution = metadata.distribution("ak-partial-ramsey")
    direct_url = distribution.read_text("direct_url.json")
    resolved: dict[str, Any] = {}
    if direct_url:
        payload = _json.loads(direct_url)
        vcs = payload.get("vcs_info", {})
        resolved = {
            "url": payload.get("url"),
            "vcs": vcs.get("vcs"),
            "commit_id": vcs.get("commit_id"),
            "requested_revision": vcs.get("requested_revision"),
        }
    return {
        "distribution": "ak-partial-ramsey",
        "version": distribution.version,
        "resolved": resolved,
    }


def model_parameters(packet: EconomicPacket) -> ModelParameters:
    """Map the CS012 economic packet onto the CS011 parameter schema.

    A pure renaming plus the maintained ``lambda_j = lambda_total * p_j`` split. The
    risk-neutral intensities pass through as separate direct fields and are never
    inferred from the physical ones.
    """
    return ModelParameters(
        preferences=Preferences(rho=packet.rho),
        installation=Installation(varphi=packet.varphi, delta=packet.delta),
        pre_arrival_technology=TaskTechnology(Z=packet.Z, I=packet.I_0),
        partial_technology=TaskTechnology(Z=packet.Z, I=packet.I_P),
        ak_technology=AkTechnology(A_bar=packet.A_bar),
        rates=WorldRates(
            r0_bar=packet.r_0_bar, rF_bar=packet.r_F_bar, rP_bar=packet.r_P_bar
        ),
        intensities=MarkIntensities(
            lambda_total=packet.lambda_total,
            p_P=packet.p_P,
            p_F=packet.p_F,
            lambda_P_star=packet.lambda_P_star,
            lambda_F_star=packet.lambda_F_star,
        ),
    )


@dataclass(frozen=True, slots=True)
class SuccessorServices:
    """Both solved successors plus the domains they were solved on."""

    ak: AkSuccessor
    partial: PartialSuccessor
    ak_root_interval: tuple[float, float]
    partial_capital_interval: tuple[float, float]
    params: ModelParameters

    @property
    def certified_domain(self) -> tuple[float, float]:
        return self.partial.certified_domain

    def q_F(self) -> float:
        """The selected AK price. Constant in ``K``, so ``J_{F,K} = 0``."""
        return self.ak.q_F

    def q_P(self, K: float) -> float:
        return self.partial.q_P(K)

    def q_P_derivative(self, K: float) -> float:
        return self.partial.q_P_derivative(K)

    def covers(self, K: float) -> bool:
        lo, hi = self.certified_domain
        return lo <= K <= hi


def solve_successors(
    params: ModelParameters,
    ak_root_interval: tuple[float, float],
    partial_capital_interval: tuple[float, float],
    tolerances: SolverTolerances | None = None,
) -> SuccessorServices:
    """Solve both absorbing successors on their declared domains.

    Every failure the dependency raises -- no root passing the strict productive-value
    TVC, an ambiguous selection, a domain violation, a nesting refusal -- propagates.
    None is caught and turned into a default.
    """
    tolerances = tolerances or SolverTolerances()
    ak = solve_ak_successor(params, AkRootInterval(*ak_root_interval), tolerances)
    partial = solve_partial_successor(
        params, PartialCapitalInterval(*partial_capital_interval), tolerances
    )
    return SuccessorServices(
        ak=ak,
        partial=partial,
        ak_root_interval=ak_root_interval,
        partial_capital_interval=partial_capital_interval,
        params=params,
    )


def payoff_jump(q_successor: float, q_0: float) -> float:
    """``J_j = q_j/q_0 - 1``, the CS012 marked total-gain jump on installed equity."""
    if q_0 <= 0.0:
        raise ValueError("the inherited installed price q_0 must be strictly positive")
    if q_successor <= 0.0:
        raise ValueError("a successor installed price must be strictly positive")
    return q_successor / q_0 - 1.0


def ak_root_report(services: SuccessorServices) -> dict[str, Any]:
    """Full AK enumeration: every root, accepted or rejected, with its reason."""
    ak = services.ak
    return {
        "declared_interval": list(services.ak_root_interval),
        "selected_q_F": ak.q_F,
        "selected_branch": ak.branch,
        "tvc_margin": ak.tvc_margin,
        "iota_F": ak.iota_F,
        "g_F": ak.g_F,
        "installation_margin": ak.installation_margin,
        "recovered_tau_F": ak.recovered_tau_F,
        "residual_polynomial": ak.residual_polynomial,
        "residual_level": ak.residual_level,
        "full_bgp_residual": ak.full_bgp_residual,
        "n_roots_enumerated": len(ak.candidates),
        "n_accepted": sum(1 for c in ak.candidates if c.accepted),
        "candidates": [c.as_dict() for c in ak.candidates],
        "diagnostics": ak.diagnostics,
    }


def partial_manifold_report(services: SuccessorServices) -> dict[str, Any]:
    """Stationary point, linearisation, certified domain, and both independent routes.

    ``max_ivp_bvp_difference`` compares the integrated manifold with a two-point
    collocation solve seeded from the *linear* stable solution, and
    ``wealth_route_max_gap`` compares quadrature productive wealth with the algebraic
    productive-wealth equation. Both are the dependency's own diagnostics; CS012 does
    not re-derive the manifold and does not claim to.
    """
    partial = services.partial
    diagnostics = dict(partial.diagnostics)
    return {
        "declared_interval": list(services.partial_capital_interval),
        "certified_domain": list(partial.certified_domain),
        "covers_declared_interval": (
            partial.certified_domain[0] <= services.partial_capital_interval[0]
            and partial.certified_domain[1] >= services.partial_capital_interval[1]
        ),
        "stationary_point": partial.point.as_dict(),
        "linearization": partial.linearization.as_dict(),
        "H_anchor": partial.H_anchor,
        "independent_route_diagnostics": {
            "max_ivp_bvp_difference": diagnostics.get("max_ivp_bvp_difference"),
            "wealth_route_max_gap": diagnostics.get("wealth_route_max_gap"),
            "derivative_identity_max_gap": diagnostics.get("derivative_identity_max_gap"),
            "manifold_invariance_max_residual": diagnostics.get(
                "manifold_invariance_max_residual"
            ),
            "rest_point_slope_gap": diagnostics.get("rest_point_slope_gap"),
            "max_offset_size_spread": diagnostics.get("max_offset_size_spread"),
            "n_interpolation_nodes": diagnostics.get("n_interpolation_nodes"),
            "collocation_checks": diagnostics.get("collocation_checks"),
        },
        "independence_note": (
            "These are the pinned dependency's own IVP-versus-collocation and "
            "quadrature-versus-algebraic comparisons. They are genuinely two routes to "
            "the same object inside CS011. The CS012 standalone checker does NOT "
            "re-derive the stable manifold: it treats q_P(K) and H_P(K) as serialized "
            "data. Manifold construction is evidenced by CS011's own 204-test suite at "
            "the pinned commit, not by this block."
        ),
    }


def synthetic_fixture_provenance(name: str) -> dict[str, Any]:
    """Read a dependency fixture's own provenance strings, verbatim, at load time."""
    fixture = get_fixture(name)
    return {
        "name": fixture.name,
        "provenance": fixture.provenance,
        "source_locator": fixture.source_locator,
        "economic_interpretation": fixture.economic_interpretation,
        "manufactured_fields": list(fixture.manufactured_fields),
        "notes": fixture.notes,
    }


__all__ = [
    "MARK_F",
    "MARK_ORDER",
    "MARK_P",
    "SuccessorServices",
    "ak_root_report",
    "dependency_provenance",
    "model_parameters",
    "partial_manifold_report",
    "payoff_jump",
    "solve_successors",
    "synthetic_fixture_provenance",
]
