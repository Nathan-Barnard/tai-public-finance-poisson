"""CS005 marked-Poisson primitive parameters, derived constants, and fingerprinting.

This package shares no primitives, equations, welfare objective, or asset
definitions with the Brownian Version 5.1 stack used by CS001-CS004 — it does
not import from ``tai_public_finance.primitives``. See
``poisson-model/complete-poisson-ramsey-model.md`` (the codex workspace) for
the frozen derivation contract this module implements the primitive layer of.

Every quantity in ``DerivedConstants`` is *computed* from ``RawPrimitives``;
none of it is re-entered by hand, per CS005's "Frozen inputs, normalizations,
and inherited state" section.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_REQUIRED_PARAMETER_FIELDS = {
    "rho",
    "g",
    "delta",
    "phi",
    "chi",
    "omega_W",
    "omega_K",
    "I_0",
    "I_L",
    "I_H",
    "lambda_intensity",
    "p_L",
    "p_H",
    "lambda_L_star",
    "lambda_H_star",
    "rbar_0",
    "rbar_L",
    "rbar_H",
    "gamma_C",
    "tau_min",
    "tau_max",
    "t_min",
    "b_min",
}

_INHERITED_STATE_CONVENTIONS = {"real_one_year_output_debt", "smoke_protected_zero_debt"}

# Domain-graph constants fixed by CS005's "Post-mark domain, boundary, and tail
# conditions" section -- not calibration inputs, so they live here rather than
# in a profile table.
U_BASE_MIN = -4.0
U_BASE_MAX = 4.0
U_DOMAIN_CAP = 8.0
U_START_OFFSET = 1.0e-6
SPECIALIZATION_MARGIN = 1.0e-6


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_of(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def Omega(task_share: float) -> float:
    """Omega(I) = I^{-I} (1-I)^{-(1-I)}, the CES-share normalization of eq. y_s(k)=Omega(I_s)k^{I_s}."""

    return task_share ** (-task_share) * (1.0 - task_share) ** (-(1.0 - task_share))


@dataclass(frozen=True)
class RawPrimitives:
    """One versioned, fingerprintable CS005 primitive vector (a profile, e.g. P-CS005-REAL-01)."""

    primitive_set_id: str
    spec_id: str
    spec_version: str
    inherited_state_convention: str

    rho: float
    g: float
    delta: float
    phi: float
    chi: float
    omega_W: float
    omega_K: float
    I_0: float
    I_L: float
    I_H: float
    lambda_intensity: float
    p_L: float
    p_H: float
    lambda_L_star: float
    lambda_H_star: float
    rbar_0: float
    rbar_L: float
    rbar_H: float
    gamma_C: float
    tau_min: float
    tau_max: float
    t_min: float
    b_min: float

    provenance: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if self.inherited_state_convention not in _INHERITED_STATE_CONVENTIONS:
            raise ValueError(f"Unknown inherited_state_convention: {self.inherited_state_convention!r}")
        if self.rho <= 0.0:
            raise ValueError("rho must be positive (A15).")
        if self.delta < 0.0:
            raise ValueError("delta must be nonnegative.")
        if self.phi <= 0.0:
            raise ValueError("phi must be positive (A17 log-installation scale).")
        if not 0.0 < self.chi < 1.0:
            raise ValueError("chi (worker mass) must lie in (0, 1).")
        if self.omega_W <= 0.0 or self.omega_K <= 0.0:
            raise ValueError("Pareto weights omega_W, omega_K must be positive (A15).")
        if not 0.0 < self.I_0 < self.I_L < self.I_H < 1.0:
            raise ValueError("Require 0 < I_0 < I_L < I_H < 1 (A18 canonical two-mark ordering).")
        if self.lambda_intensity <= 0.0:
            raise ValueError("lambda (physical arrival intensity) must be positive (A02).")
        if self.p_L <= 0.0 or self.p_H <= 0.0:
            raise ValueError("Mark probabilities p_L, p_H must be positive.")
        if abs(self.p_L + self.p_H - 1.0) > 1.0e-12:
            raise ValueError("p_L + p_H must equal 1.")
        if self.lambda_L_star <= 0.0 or self.lambda_H_star <= 0.0:
            raise ValueError("World risk-neutral intensities must be positive.")
        if self.rbar_0 <= 0.0 or self.rbar_L <= 0.0 or self.rbar_H <= 0.0:
            raise ValueError("rbar_0, rbar_L, rbar_H must be positive for this profile (H_j'(k)=q_j(k) divides by rbar_j).")
        if not 0.0 < self.gamma_C < 1.0:
            raise ValueError("gamma_C must lie in (0, 1).")
        if not 0.0 <= self.tau_min < self.tau_max <= 1.0:
            raise ValueError("Require 0 <= tau_min < tau_max <= 1 (A14, A17).")
        if self.t_min != 0.0:
            raise ValueError("t_min must be 0 (maintained transfer floor).")
        if self.b_min != 0.0:
            raise ValueError("b_min must be 0 (maintained nonnegative gross safe debt, A16).")

    @property
    def lambda_L(self) -> float:
        """Physical per-mark intensity. Never derived from lambda_L_star -- see A02 / falsification check."""

        return self.lambda_intensity * self.p_L

    @property
    def lambda_H(self) -> float:
        return self.lambda_intensity * self.p_H

    @property
    def fingerprint(self) -> str:
        return sha256_of(self.raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> RawPrimitives:
        for key in ("primitive_set_id", "spec_id", "spec_version", "inherited_state_convention", "parameters", "provenance"):
            if key not in raw:
                raise ValueError(f"Primitive table is missing required field: {key}")
        parameters = raw["parameters"]
        missing = _REQUIRED_PARAMETER_FIELDS - parameters.keys()
        if missing:
            raise ValueError(f"Primitive parameters missing: {sorted(missing)}")
        return cls(
            primitive_set_id=raw["primitive_set_id"],
            spec_id=raw["spec_id"],
            spec_version=raw["spec_version"],
            inherited_state_convention=raw["inherited_state_convention"],
            rho=float(parameters["rho"]),
            g=float(parameters["g"]),
            delta=float(parameters["delta"]),
            phi=float(parameters["phi"]),
            chi=float(parameters["chi"]),
            omega_W=float(parameters["omega_W"]),
            omega_K=float(parameters["omega_K"]),
            I_0=float(parameters["I_0"]),
            I_L=float(parameters["I_L"]),
            I_H=float(parameters["I_H"]),
            lambda_intensity=float(parameters["lambda_intensity"]),
            p_L=float(parameters["p_L"]),
            p_H=float(parameters["p_H"]),
            lambda_L_star=float(parameters["lambda_L_star"]),
            lambda_H_star=float(parameters["lambda_H_star"]),
            rbar_0=float(parameters["rbar_0"]),
            rbar_L=float(parameters["rbar_L"]),
            rbar_H=float(parameters["rbar_H"]),
            gamma_C=float(parameters["gamma_C"]),
            tau_min=float(parameters["tau_min"]),
            tau_max=float(parameters["tau_max"]),
            t_min=float(parameters["t_min"]),
            b_min=float(parameters["b_min"]),
            provenance={str(k): str(v) for k, v in raw["provenance"].items()},
            raw=raw,
        )


def load_raw_primitives(path: str | Path) -> RawPrimitives:
    text = Path(path).read_text(encoding="utf-8")
    return RawPrimitives.from_dict(json.loads(text))


@dataclass(frozen=True)
class MarkAnchor:
    """Positive production BGP anchor and stable-manifold local data for one regime (mark "0", "L", or "H")."""

    mark: str
    task_share: float
    rbar: float
    R_w: float
    k_star: float
    specialization_floor: float
    u_min: float
    u_max: float
    nu_minus: float | None = None
    nu_plus: float | None = None
    q_prime_star: float | None = None
    y_star: float | None = None
    H_star: float | None = None


def _build_mark_anchor(mark: str, task_share: float, rbar: float, q_star: float, iota_star: float, phi: float, *, post_mark: bool) -> MarkAnchor:
    R_w = rbar * q_star + iota_star
    if R_w <= 0.0:
        raise ValueError(f"World user cost R_{mark}^w = {R_w} is not positive; H_{mark}'(k)=q_{mark}(k) formula requires it.")
    k_star = (task_share * Omega(task_share) / R_w) ** (1.0 / (1.0 - task_share))
    floor = task_share / (1.0 - task_share)
    u_min = max(U_BASE_MIN, math.log((1.0 + SPECIALIZATION_MARGIN) * floor / k_star))
    u_max = U_BASE_MAX
    if not post_mark:
        return MarkAnchor(mark=mark, task_share=task_share, rbar=rbar, R_w=R_w, k_star=k_star, specialization_floor=floor, u_min=u_min, u_max=u_max)

    discriminant = rbar**2 + 4.0 * (1.0 - task_share) * R_w / (phi * q_star)
    sqrt_discriminant = math.sqrt(discriminant)
    nu_minus = (rbar - sqrt_discriminant) / 2.0
    nu_plus = (rbar + sqrt_discriminant) / 2.0
    q_prime_star = phi * q_star * nu_minus / k_star
    y_star = Omega(task_share) * k_star**task_share
    H_star = (y_star - iota_star * k_star) / rbar
    return MarkAnchor(
        mark=mark,
        task_share=task_share,
        rbar=rbar,
        R_w=R_w,
        k_star=k_star,
        specialization_floor=floor,
        u_min=u_min,
        u_max=u_max,
        nu_minus=nu_minus,
        nu_plus=nu_plus,
        q_prime_star=q_prime_star,
        y_star=y_star,
        H_star=H_star,
    )


@dataclass(frozen=True)
class InheritedState:
    """Protected date-zero balance sheet S_0, M_0=empty (one-time-protection convention)."""

    convention: str
    k_0: float
    e_0: float
    psi_0: float
    a_0: float
    theta_0: float
    b_0: float
    f_0: float


def _inherited_state(convention: str, anchor_0: MarkAnchor, q_star: float) -> InheritedState:
    k_0 = anchor_0.k_star
    if convention == "real_one_year_output_debt":
        y_0_at_k0 = Omega(anchor_0.task_share) * k_0**anchor_0.task_share
        B_0 = y_0_at_k0
        theta_0 = 0.0
        psi_0 = theta_0 - q_star * k_0
        f_0 = -B_0
        e_0 = f_0 - q_star * k_0
    elif convention == "smoke_protected_zero_debt":
        e_0 = 0.0
        psi_0 = 0.0
        theta_0 = q_star * k_0
        f_0 = theta_0
    else:  # pragma: no cover - validated in RawPrimitives.__post_init__
        raise ValueError(convention)
    a_0 = 1.0
    b_0 = psi_0 - e_0
    if abs((theta_0 - b_0) - f_0) > 1.0e-9 * max(1.0, abs(f_0)):
        raise AssertionError("Balance-sheet identity f_0 = theta_0 - b_0 failed in inherited-state construction.")
    return InheritedState(convention=convention, k_0=k_0, e_0=e_0, psi_0=psi_0, a_0=a_0, theta_0=theta_0, b_0=b_0, f_0=f_0)


@dataclass(frozen=True)
class DerivedConstants:
    """Every quantity CS005 requires to be computed rather than re-entered."""

    eta_W: float
    eta_K: float
    q_star: float
    iota_star: float
    lambda_L: float
    lambda_H: float
    Delta_0: float
    anchors: dict[str, MarkAnchor]
    inherited_state: InheritedState

    @property
    def anchor_0(self) -> MarkAnchor:
        return self.anchors["0"]

    @property
    def anchor_L(self) -> MarkAnchor:
        return self.anchors["L"]

    @property
    def anchor_H(self) -> MarkAnchor:
        return self.anchors["H"]


def compute_derived_constants(p: RawPrimitives) -> DerivedConstants:
    q_star = math.exp(p.phi * (p.delta + p.g))
    iota_star = (q_star - 1.0) / p.phi
    anchor_0 = _build_mark_anchor("0", p.I_0, p.rbar_0, q_star, iota_star, p.phi, post_mark=False)
    anchor_L = _build_mark_anchor("L", p.I_L, p.rbar_L, q_star, iota_star, p.phi, post_mark=True)
    anchor_H = _build_mark_anchor("H", p.I_H, p.rbar_H, q_star, iota_star, p.phi, post_mark=True)
    inherited = _inherited_state(p.inherited_state_convention, anchor_0, q_star)
    return DerivedConstants(
        eta_W=p.chi * p.omega_W,
        eta_K=(1.0 - p.chi) * p.omega_K,
        q_star=q_star,
        iota_star=iota_star,
        lambda_L=p.lambda_L,
        lambda_H=p.lambda_H,
        Delta_0=p.rho + p.lambda_intensity - p.rbar_0,
        anchors={"0": anchor_0, "L": anchor_L, "H": anchor_H},
        inherited_state=inherited,
    )


def run_fingerprint(primitives: RawPrimitives, tolerances: dict[str, Any], experiment_extra: dict[str, Any]) -> str:
    """Lowercase SHA-256 of the ordered UTF-8 JSON object CS005's fingerprint section specifies.

    Decimal numbers are serialized as strings so the fingerprint is stable
    across equivalent float/int JSON encodings.
    """

    def stringify_numbers(value: Any) -> Any:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return repr(value)
        if isinstance(value, dict):
            return {str(k): stringify_numbers(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [stringify_numbers(v) for v in value]
        return value

    payload = {
        "spec_id": primitives.spec_id,
        "spec_version": primitives.spec_version,
        "profile_name": primitives.primitive_set_id,
        "primitives": primitives.raw,
        "tolerances": tolerances,
        "experiment": experiment_extra,
    }
    return sha256_of(stringify_numbers(payload))
