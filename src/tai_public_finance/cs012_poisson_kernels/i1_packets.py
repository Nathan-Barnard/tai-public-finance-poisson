"""Frozen, fingerprinted parameter packets for CS012 block I1.

Two packets exist and they are not interchangeable:

``P-CS012-SYN-01``
    A stationary-compatible *software* packet. It names fixtures inside the pinned
    CS011 dependency and carries their own provenance strings verbatim, read at load
    time rather than transcribed, so a fixture that stops calling itself manufactured
    cannot silently become a scenario here. It has no economic interpretation.

``P-CS012-ECO-01`` and ``P-CS012-ECO-02``
    *Provisional illustrative* economic scenarios. Neither is an estimate, a country
    calibration, or a baseline for any policy statement. Their judgement values are
    inherited from the provisional marked-Poisson design ``EMP005`` (profile
    ``P-CS005-REAL-01``), which states of itself that it "is not an estimate and not a
    country baseline". ``ECO-02`` differs from ``ECO-01`` in exactly one primitive,
    ``technology.A_bar``, and is a companion to it rather than a replacement: both
    remain valid under their own fingerprints. The recognized set is closed and
    enumerated -- an unrecognized or misspelled id is refused, so a stray file cannot
    become a scenario by being pointed at.

Time unit: years. Value unit: current goods.

The packets are immutable once written. Neither may be tuned after seeing a result:
CS012 v0.1 makes a changed primitive a new run, not an edit.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .extended import sha256_of_object

SYNTHETIC_PACKET_ID = "P-CS012-SYN-01"
ECONOMIC_PACKET_ID = "P-CS012-ECO-01"
ECONOMIC_PACKET_IDS = ("P-CS012-ECO-01", "P-CS012-ECO-02", "P-CS012-ECO-03")
"""The closed set of recognized economic packet ids. Extending it is a deliberate
edit, never a pattern match: an arbitrary ``P-CS012-ECO-*`` name is not accepted."""

TIME_UNIT = "year"
VALUE_UNIT = "current goods"


class PacketError(ValueError):
    """A packet is structurally malformed or internally inconsistent."""


def _real(payload: Any, field: str) -> float:
    if isinstance(payload, bool) or not isinstance(payload, (int, float)):
        raise PacketError(f"{field} must be a JSON number")
    return float(payload)


@dataclass(frozen=True, slots=True)
class EconomicPacket:
    """The provisional illustrative economic scenario, field by field.

    Every field is a direct input. Nothing here is derived from a solver result, and
    ``q_0`` is stated as a *rule* (``exp(varphi*delta)``) rather than a number so the
    inherited price cannot drift away from the installation primitives.
    """

    packet_id: str
    packet_kind: str
    time_unit: str
    value_unit: str
    rho: float
    varphi: float
    delta: float
    I_0: float
    I_P: float
    Z: float
    A_bar: float
    r_0_bar: float
    r_P_bar: float
    r_F_bar: float
    lambda_total: float
    p_P: float
    p_F: float
    lambda_P: float
    lambda_F: float
    lambda_P_star: float
    lambda_F_star: float
    K_0: float
    a_0: float
    public_installed_equity: float
    public_safe_asset: float
    public_safe_debt: float
    source_tax: float
    ak_root_interval: tuple[float, float]
    partial_capital_interval: tuple[float, float]
    diagnostic_capital_grid: tuple[float, ...]
    baseline_capital: float
    provenance: str
    limits: str

    @property
    def q_0(self) -> float:
        """``q_0 = exp(varphi * delta)``, the zero-growth inherited installed price."""
        import math

        return math.exp(self.varphi * self.delta)

    def direct_fields(self) -> dict[str, Any]:
        """Operative fields only, in a fixed order. Excludes prose and paths."""
        return {
            "packet_id": self.packet_id,
            "packet_kind": self.packet_kind,
            "time_unit": self.time_unit,
            "value_unit": self.value_unit,
            "preferences": {"rho": self.rho},
            "installation": {"varphi": self.varphi, "delta": self.delta},
            "technology": {
                "I_0": self.I_0,
                "I_P": self.I_P,
                "Z": self.Z,
                "A_bar": self.A_bar,
            },
            "world_rates": {
                "r_0_bar": self.r_0_bar,
                "r_P_bar": self.r_P_bar,
                "r_F_bar": self.r_F_bar,
            },
            "shock_law": {
                "lambda_total": self.lambda_total,
                "p_P": self.p_P,
                "p_F": self.p_F,
                "lambda_P": self.lambda_P,
                "lambda_F": self.lambda_F,
                "lambda_P_star": self.lambda_P_star,
                "lambda_F_star": self.lambda_F_star,
            },
            "inherited_state": {
                "K_0": self.K_0,
                "q_0_rule": "exp(varphi*delta)",
                "a_0": self.a_0,
                "public_installed_equity": self.public_installed_equity,
                "public_safe_asset": self.public_safe_asset,
                "public_safe_debt": self.public_safe_debt,
                "source_tax": self.source_tax,
                "M_0": "empty_under_one_time_protection",
            },
            "successor_domains": {
                "ak_root_interval": list(self.ak_root_interval),
                "partial_capital_interval": list(self.partial_capital_interval),
            },
            "diagnostics": {
                "diagnostic_capital_grid": list(self.diagnostic_capital_grid),
                "baseline_capital": self.baseline_capital,
            },
        }

    @property
    def fingerprint(self) -> str:
        return sha256_of_object(self.direct_fields())


@dataclass(frozen=True, slots=True)
class SyntheticPacket:
    """The stationary-compatible software packet: names of pinned dependency fixtures."""

    packet_id: str
    packet_kind: str
    dependency_repository: str
    dependency_commit: str
    primary_fixture: str
    regression_fixtures: tuple[str, ...]
    provenance: str
    limits: str

    def direct_fields(self) -> dict[str, Any]:
        return {
            "packet_id": self.packet_id,
            "packet_kind": self.packet_kind,
            "dependency_repository": self.dependency_repository,
            "dependency_commit": self.dependency_commit,
            "primary_fixture": self.primary_fixture,
            "regression_fixtures": list(self.regression_fixtures),
        }

    @property
    def fingerprint(self) -> str:
        return sha256_of_object(self.direct_fields())


def _check_economic_consistency(packet: EconomicPacket) -> None:
    """Refuse a packet whose stated intensities contradict its own shock law.

    ``lambda_j = lambda_total * p_j`` is an identity of the marked-Poisson law, but the
    physical and risk-neutral intensities are *separate direct fields* and neither is
    ever inferred from the other. This checks the physical identity and leaves the
    risk-neutral pair alone.
    """
    if not (packet.rho > 0 and packet.varphi > 0 and packet.delta >= 0):
        raise PacketError("rho and varphi must be strictly positive, delta nonnegative")
    if not 0.0 < packet.I_0 < packet.I_P < 1.0:
        raise PacketError("the task shares must satisfy 0 < I_0 < I_P < 1")
    if packet.Z <= 0.0 or packet.A_bar <= 0.0:
        raise PacketError("Z and A_bar must be strictly positive")
    if packet.lambda_total <= 0.0:
        raise PacketError("lambda_total must be strictly positive")
    if abs(packet.p_P + packet.p_F - 1.0) > 1e-12:
        raise PacketError("the mark split must sum to one")
    for label, physical, probability in (
        ("P", packet.lambda_P, packet.p_P),
        ("F", packet.lambda_F, packet.p_F),
    ):
        expected = packet.lambda_total * probability
        if abs(physical - expected) > 1e-15 * max(1.0, abs(expected)):
            raise PacketError(
                f"lambda_{label} = {physical!r} contradicts lambda_total*p_{label} = {expected!r}"
            )
    if packet.lambda_P_star < 0.0 or packet.lambda_F_star < 0.0:
        raise PacketError("risk-neutral intensities must be nonnegative")
    if packet.a_0 <= 0.0 or packet.K_0 <= 0.0:
        raise PacketError("owner wealth and inherited capital must be strictly positive")
    lo, hi = packet.ak_root_interval
    if not 0.0 < lo < hi:
        raise PacketError("the AK root interval must satisfy 0 < q_lo < q_hi")
    k_lo, k_hi = packet.partial_capital_interval
    if not 0.0 < k_lo < k_hi:
        raise PacketError("the partial capital interval must satisfy 0 < K_lo < K_hi")
    if not k_lo <= packet.baseline_capital <= k_hi:
        raise PacketError("the baseline capital must lie inside the partial capital interval")
    for K in packet.diagnostic_capital_grid:
        if not k_lo <= K <= k_hi:
            raise PacketError(f"diagnostic capital point {K!r} lies outside the certified domain")
    # I1 is an owner-side block. A nonzero public position here would invite a
    # government-kernel calculation that this block must not perform.
    for name, value in (
        ("public_installed_equity", packet.public_installed_equity),
        ("public_safe_asset", packet.public_safe_asset),
        ("public_safe_debt", packet.public_safe_debt),
        ("source_tax", packet.source_tax),
    ):
        if value != 0.0:
            raise PacketError(
                f"{name} must be zero in the I1 owner-side packet; the positive "
                "prefunding family is frozen separately before I2"
            )


def load_economic_packet(path: str | Path) -> EconomicPacket:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("packet_id") not in ECONOMIC_PACKET_IDS:
        raise PacketError(
            f"expected one of {list(ECONOMIC_PACKET_IDS)}, found "
            f"{payload.get('packet_id')!r}"
        )
    tech = payload["technology"]
    rates = payload["world_rates"]
    shock = payload["shock_law"]
    state = payload["inherited_state"]
    domains = payload["successor_domains"]
    diagnostics = payload["diagnostics"]
    if state.get("q_0_rule") != "exp(varphi*delta)":
        raise PacketError("q_0 must be stated as the rule exp(varphi*delta)")
    if state.get("M_0") != "empty_under_one_time_protection":
        raise PacketError("M_0 must be declared empty under the one-time-protection convention")
    packet = EconomicPacket(
        packet_id=payload["packet_id"],
        packet_kind=payload["packet_kind"],
        time_unit=payload["time_unit"],
        value_unit=payload["value_unit"],
        rho=_real(payload["preferences"]["rho"], "rho"),
        varphi=_real(payload["installation"]["varphi"], "varphi"),
        delta=_real(payload["installation"]["delta"], "delta"),
        I_0=_real(tech["I_0"], "I_0"),
        I_P=_real(tech["I_P"], "I_P"),
        Z=_real(tech["Z"], "Z"),
        A_bar=_real(tech["A_bar"], "A_bar"),
        r_0_bar=_real(rates["r_0_bar"], "r_0_bar"),
        r_P_bar=_real(rates["r_P_bar"], "r_P_bar"),
        r_F_bar=_real(rates["r_F_bar"], "r_F_bar"),
        lambda_total=_real(shock["lambda_total"], "lambda_total"),
        p_P=_real(shock["p_P"], "p_P"),
        p_F=_real(shock["p_F"], "p_F"),
        lambda_P=_real(shock["lambda_P"], "lambda_P"),
        lambda_F=_real(shock["lambda_F"], "lambda_F"),
        lambda_P_star=_real(shock["lambda_P_star"], "lambda_P_star"),
        lambda_F_star=_real(shock["lambda_F_star"], "lambda_F_star"),
        K_0=_real(state["K_0"], "K_0"),
        a_0=_real(state["a_0"], "a_0"),
        public_installed_equity=_real(state["public_installed_equity"], "public_installed_equity"),
        public_safe_asset=_real(state["public_safe_asset"], "public_safe_asset"),
        public_safe_debt=_real(state["public_safe_debt"], "public_safe_debt"),
        source_tax=_real(state["source_tax"], "source_tax"),
        ak_root_interval=(
            _real(domains["ak_root_interval"][0], "q_lo"),
            _real(domains["ak_root_interval"][1], "q_hi"),
        ),
        partial_capital_interval=(
            _real(domains["partial_capital_interval"][0], "K_lo"),
            _real(domains["partial_capital_interval"][1], "K_hi"),
        ),
        diagnostic_capital_grid=tuple(
            _real(K, "diagnostic_capital_grid") for K in diagnostics["diagnostic_capital_grid"]
        ),
        baseline_capital=_real(diagnostics["baseline_capital"], "baseline_capital"),
        provenance=str(payload.get("provenance", "")),
        limits=str(payload.get("limits", "")),
    )
    _check_economic_consistency(packet)
    return packet


def load_synthetic_packet(path: str | Path) -> SyntheticPacket:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("packet_id") != SYNTHETIC_PACKET_ID:
        raise PacketError(f"expected {SYNTHETIC_PACKET_ID}, found {payload.get('packet_id')!r}")
    return SyntheticPacket(
        packet_id=payload["packet_id"],
        packet_kind=payload["packet_kind"],
        dependency_repository=payload["dependency_repository"],
        dependency_commit=payload["dependency_commit"],
        primary_fixture=payload["primary_fixture"],
        regression_fixtures=tuple(payload["regression_fixtures"]),
        provenance=str(payload.get("provenance", "")),
        limits=str(payload.get("limits", "")),
    )


__all__ = [
    "ECONOMIC_PACKET_ID",
    "ECONOMIC_PACKET_IDS",
    "SYNTHETIC_PACKET_ID",
    "TIME_UNIT",
    "VALUE_UNIT",
    "EconomicPacket",
    "PacketError",
    "SyntheticPacket",
    "load_economic_packet",
    "load_synthetic_packet",
]
