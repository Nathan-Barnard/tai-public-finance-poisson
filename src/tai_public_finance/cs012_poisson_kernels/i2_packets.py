"""Frozen packets for CS012 block I2a: the public-prefunding family and SYN-02.

``P-CS012-PREFUND-01``
    A predeclared one-sided continuation in the inherited public safe buffer, bound by
    fingerprint to ``P-CS012-ECO-02``. Its rows are different inherited public-wealth
    continuations, not free endowments and not a welfare comparison across a common
    ``(S_0, M_0)``. ``F = 0`` is held outside the finite sequence as the exact literal
    laissez-faire boundary.

``P-CS012-SYN-02``
    A directly constructed analytic fixture, written down here rather than borrowed. It
    replaces the false "stationary-compatible" characterization that
    ``P-CS012-SYN-01`` carried: no genuinely stationary-compatible fixture exists at the
    pinned CS011 commit. SYN-01 is quarantined, not modified and not relabelled.

Both are immutable and fingerprinted over their operative fields only.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .extended import sha256_of_object
from .i1_packets import PacketError

PREFUNDING_PACKET_ID = "P-CS012-PREFUND-01"
PREFUNDING_PACKET_IDS = ("P-CS012-PREFUND-01", "P-CS012-PREFUND-02")
"""Closed, enumerated set of prefunding packets."""
SYNTHETIC_ANALYTIC_PACKET_ID = "P-CS012-SYN-02"
SYNTHETIC_ANALYTIC_PACKET_IDS = ("P-CS012-SYN-02", "P-CS012-SYN-03")
"""Closed, enumerated set of directly constructed analytic fixtures. SYN-03 is the
rho = 3% companion to SYN-02; SYN-01 is quarantined and is not a member."""

LITERAL_BOUNDARY_STATUS = "nonfinite_fiscal_kernel_at_literal_laissez_faire"

SYN01_QUARANTINE = {
    "packet_id": "P-CS012-SYN-01",
    "status": "quarantined",
    "defect": (
        "P-CS012-SYN-01 describes the pinned dependency's manufactured-two-mark fixture "
        "as stationary-compatible. That characterization is false: the dependency "
        "describes that fixture's state as an arbitrary probe, not an equilibrium "
        "point, and no genuinely stationary-compatible fixture exists at commit "
        "6b457682c4eed8ad4e3bdd867d1292abac38f424."
    ),
    "true_character": (
        "an arbitrary successor-service software probe with no economic interpretation"
    ),
    "disposition": (
        "not modified, not relabelled, and not deleted; its historical outputs stand "
        "under their own hashes and support nothing"
    ),
    "replacement": SYNTHETIC_ANALYTIC_PACKET_ID,
}


def _real(payload: Any, field: str) -> float:
    if isinstance(payload, bool) or not isinstance(payload, (int, float)):
        raise PacketError(f"{field} must be a JSON number")
    return float(payload)


@dataclass(frozen=True, slots=True)
class PrefundingPacket:
    """The frozen positive public-prefunding family, bound to one economic packet."""

    packet_id: str
    packet_kind: str
    time_unit: str
    value_unit: str
    bound_packet_id: str
    bound_packet_fingerprint: str
    scale_name: str
    scale_value: float
    prefunding_ratios: tuple[float, ...]
    baseline_capital: float
    public_installed_equity: float
    source_tax: float
    main_interior_reference: float | None
    minimum_transfer_margin_requirement: float | None
    provenance: str
    limits: str

    def levels(self) -> tuple[float, ...]:
        """``F`` in current goods: the ratio times the named scale ``a_0``."""
        return tuple(ratio * self.scale_value for ratio in self.prefunding_ratios)

    def safe_debt(self, F: float) -> float:
        """``B = -F``. Positive inherited wealth is a negative gross debt position."""
        return -F

    def direct_fields(self) -> dict[str, Any]:
        fields: dict[str, Any] = {
            "packet_id": self.packet_id,
            "packet_kind": self.packet_kind,
            "time_unit": self.time_unit,
            "value_unit": self.value_unit,
            "bound_economic_packet": {
                "packet_id": self.bound_packet_id,
                "fingerprint": self.bound_packet_fingerprint,
            },
            "scale": {"name": self.scale_name, "value": self.scale_value},
            "prefunding_ratio_sequence": list(self.prefunding_ratios),
            "literal_boundary": {
                "prefunding_ratio": 0.0,
                "in_finite_sequence": False,
                "status": LITERAL_BOUNDARY_STATUS,
            },
            "balance_sheet_convention": {
                "public_installed_equity_Theta": self.public_installed_equity,
                "public_safe_debt_B_rule": "-F",
                "source_tax_tau": self.source_tax,
                "event_map_rule": "e_j_plus = F - q_j(K)*K",
            },
            "baseline_capital": self.baseline_capital,
        }
        # Only a packet that actually designates a main reference carries these keys, so
        # P-CS012-PREFUND-01's operative fingerprint is unchanged by their introduction.
        if self.main_interior_reference is not None:
            fields["main_interior_reference"] = self.main_interior_reference
            fields["minimum_transfer_margin_requirement"] = (
                self.minimum_transfer_margin_requirement
            )
        return fields

    @property
    def fingerprint(self) -> str:
        return sha256_of_object(self.direct_fields())


@dataclass(frozen=True, slots=True)
class AnalyticFixture:
    """SYN-02: a directly constructed full-AK pure-safe-fund benchmark.

    ``q_F`` and ``A_bar`` are *derived from the stated rules*, never stored, so they
    cannot drift away from the primitives that define them.
    """

    packet_id: str
    packet_kind: str
    fixture_scope: str
    rho: float
    varphi: float
    delta: float
    target_growth: float
    prefunding_ratios: tuple[float, ...]
    stated_r_F_bar: float
    stated_q_F: float
    stated_A_bar: float
    stated_implied_growth: float
    stated_stationary_residual: float
    stated_tvc_margin: float
    provenance: str
    limits: str

    @property
    def r_F_bar(self) -> float:
        """``r_F_bar = rho + g``: the stationary-compatibility condition, by construction."""
        return self.rho + self.target_growth

    @property
    def q_F(self) -> float:
        """``q_F = exp(varphi*(g + delta))``."""
        return math.exp(self.varphi * (self.target_growth + self.delta))

    @property
    def A_bar(self) -> float:
        """``A_bar = q_F*(r_F_bar - g) + (q_F - 1)/varphi``, the inverted user cost."""
        return self.q_F * (self.r_F_bar - self.target_growth) + (self.q_F - 1.0) / self.varphi

    @property
    def implied_growth(self) -> float:
        """``g = log(q_F)/varphi - delta``, recovered from the price."""
        return math.log(self.q_F) / self.varphi - self.delta

    @property
    def stationary_residual(self) -> float:
        """``r_F_bar - rho - g``. Zero is what makes the fixture stationary-compatible."""
        return self.r_F_bar - self.rho - self.target_growth

    @property
    def tvc_margin(self) -> float:
        """``r_F_bar - g``, the strict productive-value transversality margin."""
        return self.r_F_bar - self.target_growth

    def user_cost_residual(self) -> float:
        """``r_F_bar q_F - [A_bar - iota(q_F) + q_F g(q_F)]``, the zero-tax AK equation."""
        iota = (self.q_F - 1.0) / self.varphi
        return self.r_F_bar * self.q_F - (
            self.A_bar - iota + self.q_F * self.implied_growth
        )

    def direct_fields(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "packet_kind": self.packet_kind,
            "fixture_scope": self.fixture_scope,
            "construction": "direct",
            "preferences": {"rho": self.rho},
            "installation": {"varphi": self.varphi, "delta": self.delta},
            "target_growth_g": self.target_growth,
            "world_rates": {"r_F_bar_rule": "rho + g"},
            "derived_rules": {
                "q_F": "exp(varphi*(g + delta))",
                "A_bar": "q_F*(r_F_bar - g) + (q_F - 1)/varphi",
            },
            "analytic_expectations": {
                "r_F_bar": self.stated_r_F_bar,
                "q_F": self.stated_q_F,
                "A_bar": self.stated_A_bar,
                "implied_growth": self.stated_implied_growth,
                "stationary_residual": self.stated_stationary_residual,
                "productive_tvc_margin": self.stated_tvc_margin,
            },
            "prefunding_ratio_sequence": list(self.prefunding_ratios),
            "literal_boundary": {
                "prefunding_ratio": 0.0,
                "in_finite_sequence": False,
                "status": LITERAL_BOUNDARY_STATUS,
            },
        }

    @property
    def fingerprint(self) -> str:
        return sha256_of_object(self.direct_fields())


def _check_sequence(ratios: tuple[float, ...], label: str) -> None:
    if not ratios:
        raise PacketError(f"{label}: the prefunding sequence must be non-empty")
    for ratio in ratios:
        if not math.isfinite(ratio) or ratio <= 0.0:
            raise PacketError(
                f"{label}: every prefunding ratio must be finite and strictly positive; "
                "F = 0 is the literal boundary and is represented separately, never as a "
                "sequence member"
            )
    if list(ratios) != sorted(ratios, reverse=True):
        raise PacketError(f"{label}: the sequence must decrease toward the boundary")


def load_prefunding_packet(path: str | Path) -> PrefundingPacket:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("packet_id") not in PREFUNDING_PACKET_IDS:
        raise PacketError(
            f"expected one of {list(PREFUNDING_PACKET_IDS)}, found "
            f"{payload.get('packet_id')!r}"
        )
    boundary = payload["literal_boundary"]
    if boundary.get("in_finite_sequence") is not False:
        raise PacketError("F = 0 must be declared outside the finite sequence")
    if boundary.get("status") != LITERAL_BOUNDARY_STATUS:
        raise PacketError(f"the literal boundary must carry {LITERAL_BOUNDARY_STATUS}")
    convention = payload["balance_sheet_convention"]
    if convention.get("public_safe_debt_B_rule") != "-F":
        raise PacketError("the safe-debt convention must be B = -F")
    scale = payload["scale"]
    reference = payload.get("main_interior_reference")
    packet = PrefundingPacket(
        packet_id=payload["packet_id"],
        packet_kind=payload["packet_kind"],
        time_unit=payload["time_unit"],
        value_unit=payload["value_unit"],
        bound_packet_id=payload["bound_economic_packet"]["packet_id"],
        bound_packet_fingerprint=payload["bound_economic_packet"]["fingerprint"],
        scale_name=scale["name"],
        scale_value=_real(scale["value"], "scale.value"),
        prefunding_ratios=tuple(
            _real(r, "prefunding_ratio_sequence") for r in payload["prefunding_ratio_sequence"]
        ),
        baseline_capital=_real(payload["baseline_capital"], "baseline_capital"),
        public_installed_equity=_real(
            convention["public_installed_equity_Theta"], "Theta"
        ),
        source_tax=_real(convention["source_tax_tau"], "tau"),
        main_interior_reference=(
            None if reference is None else _real(reference["prefunding_ratio"], "main reference")
        ),
        minimum_transfer_margin_requirement=(
            None
            if reference is None
            else _real(reference["minimum_transfer_margin_requirement"], "margin requirement")
        ),
        provenance=str(payload.get("provenance", "")),
        limits=str(payload.get("limits", "")),
    )
    _check_sequence(packet.prefunding_ratios, PREFUNDING_PACKET_ID)
    if packet.main_interior_reference is not None:
        if packet.main_interior_reference not in packet.prefunding_ratios:
            raise PacketError("the main interior reference must be a member of the frozen sequence")
    if packet.scale_value <= 0.0:
        raise PacketError("the named scale must be strictly positive")
    if packet.public_installed_equity != 0.0 or packet.source_tax != 0.0:
        raise PacketError(
            "the I2a prefunding family holds public installed equity and the source tax "
            "at zero; a nonzero position belongs to a later block"
        )
    return packet


def load_analytic_fixture(path: str | Path) -> AnalyticFixture:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("packet_id") not in SYNTHETIC_ANALYTIC_PACKET_IDS:
        raise PacketError(
            f"expected one of {list(SYNTHETIC_ANALYTIC_PACKET_IDS)}, found "
            f"{payload.get('packet_id')!r}"
        )
    if payload.get("construction") != "direct":
        raise PacketError(
            "SYN-02 must declare itself directly constructed; it must not claim to come "
            "from a dependency fixture"
        )
    if payload["world_rates"].get("r_F_bar_rule") != "rho + g":
        raise PacketError(
            "SYN-02's world rate must be the stationary-compatibility rule rho + g"
        )
    expectations = payload["analytic_expectations"]
    fixture = AnalyticFixture(
        packet_id=payload["packet_id"],
        packet_kind=payload["packet_kind"],
        fixture_scope=payload["fixture_scope"],
        rho=_real(payload["preferences"]["rho"], "rho"),
        varphi=_real(payload["installation"]["varphi"], "varphi"),
        delta=_real(payload["installation"]["delta"], "delta"),
        target_growth=_real(payload["target_growth_g"], "target_growth_g"),
        prefunding_ratios=tuple(
            _real(r, "prefunding_ratio_sequence") for r in payload["prefunding_ratio_sequence"]
        ),
        stated_r_F_bar=_real(expectations["r_F_bar"], "expected r_F_bar"),
        stated_q_F=_real(expectations["q_F"], "expected q_F"),
        stated_A_bar=_real(expectations["A_bar"], "expected A_bar"),
        stated_implied_growth=_real(expectations["implied_growth"], "expected g"),
        stated_stationary_residual=_real(
            expectations["stationary_residual"], "expected stationary residual"
        ),
        stated_tvc_margin=_real(
            expectations["productive_tvc_margin"], "expected TVC margin"
        ),
        provenance=str(payload.get("provenance", "")),
        limits=str(payload.get("limits", "")),
    )
    _check_sequence(fixture.prefunding_ratios, SYNTHETIC_ANALYTIC_PACKET_ID)
    if fixture.rho <= 0.0 or fixture.varphi <= 0.0:
        raise PacketError("rho and varphi must be strictly positive")
    if abs(fixture.stationary_residual) > 1.0e-15:
        raise PacketError(
            f"SYN-02 is not stationary-compatible: r_F_bar - rho - g = "
            f"{fixture.stationary_residual!r}"
        )
    if fixture.tvc_margin <= 0.0:
        raise PacketError("SYN-02 must satisfy the strict productive-value TVC r_F_bar > g")
    if abs(fixture.user_cost_residual()) > 1.0e-12:
        raise PacketError(
            f"SYN-02 fails its own zero-tax user-cost equation: residual "
            f"{fixture.user_cost_residual()!r}"
        )
    # The stated and the derived representations must pin each other. Deriving alone
    # would make the fixture unfalsifiable -- any primitive edit would silently produce
    # a new, still self-consistent, fixture. Stating alone would let the numbers drift
    # from the rules. Requiring both to agree is what makes a perturbation detectable.
    for label, derived, stated in (
        ("r_F_bar", fixture.r_F_bar, fixture.stated_r_F_bar),
        ("q_F", fixture.q_F, fixture.stated_q_F),
        ("A_bar", fixture.A_bar, fixture.stated_A_bar),
        ("implied_growth", fixture.implied_growth, fixture.stated_implied_growth),
        ("stationary_residual", fixture.stationary_residual, fixture.stated_stationary_residual),
        ("productive_tvc_margin", fixture.tvc_margin, fixture.stated_tvc_margin),
    ):
        if abs(derived - stated) > 1.0e-12:
            raise PacketError(
                f"SYN-02 stationary identity {label} disagrees with its stated value: "
                f"derived {derived!r} vs stated {stated!r}"
            )
    return fixture


__all__ = [
    "LITERAL_BOUNDARY_STATUS",
    "PREFUNDING_PACKET_ID",
    "SYN01_QUARANTINE",
    "PREFUNDING_PACKET_IDS",
    "SYNTHETIC_ANALYTIC_PACKET_ID",
    "SYNTHETIC_ANALYTIC_PACKET_IDS",
    "AnalyticFixture",
    "PrefundingPacket",
    "load_analytic_fixture",
    "load_prefunding_packet",
]
