#!/usr/bin/env python3
"""Standalone independent checker for the CS012 I2b transfer-constrained report.

    uv run python tools/check_cs012_i2b_report.py <identity_report.json>

Standard library only. Imports nothing from ``tai_public_finance`` or
``ak_partial_ramsey``, and — the point of the exercise — shares no root solver, no
quadrature routine and no water-filling helper with production. It reruns the economics
from the serialized path sample using its own composite Simpson rule and its own
bisection, and then requires production to agree.

What it rebuilds unaided:

* the present-value wage, by Simpson over the serialized sample plus the analytic tail,
  against the ``H_P − q_P K`` route;
* for every row, the annuity ``A`` implied by the reported switch time through
  continuity, and independently the switch time implied by the reported ``A``;
* the present-value transfer budget by its own quadrature of the wedge;
* ``T(t) ≥ 0`` at every sample, including well off the production mesh;
* complementarity: ``T > 0`` exactly where the annuity exceeds the wage, and ``C = W``
  on the boundary arc;
* the transfer-slack threshold, ``F_min``, and the interiority margin;
* the full-AK identities and their unit elasticity;
* the one-sided ``F → 0⁺`` limit ``1/W_P(K₀)``;
* every fingerprint, count, maximum, and the absence of ``k^G``/``γ``.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from typing import Any

SCHEMA = "cs012-i2b-transfer-constrained-report/1"
CS012_SHA256 = "d345f07cdeaf6901fd1ea985cb2566d8c717e4b4dce5ba9fa489375b895d0498"
CS011_COMMIT = "6b457682c4eed8ad4e3bdd867d1292abac38f424"
MU_E_UNAVAILABLE = "unavailable_missing_optimized_pre_event_value_gradient"

#: Published operative fingerprints of the packets this block is allowed to consume.
#: Pinning them here, like the specification hash and the dependency commit, is what
#: lets the checker reject a report that silently swapped a configuration.
KNOWN_FINGERPRINTS = {
    "P-CS012-ECO-02": "2d792f4843a8024517c267cc551f2008eb86ecf1a6e7d6fc9906b0093e100568",
    "P-CS012-ECO-03": "068ed0cc5ad359b0f40e63df823d0e2b96b57f43bb1d6887bfb8848604576938",
    "P-CS012-PREFUND-01": "73a056a5786b3ce14ccdd40e2c9c6882d8ab5835b2b6a3f1a3e82ba512bb5efb",
    "P-CS012-PREFUND-02": "fddc851a26c0aff558981363597f37dd2c5ae7cca3d368fc4731ddee1825bf24",
    "P-CS012-SYN-02": "f655fd974708bcdc4ade230baa8c0c8c42f1ef56005a080cd9808beadbddbe4e",
    "P-CS012-SYN-03": "8f17afe3182bb77a34e3b46e72917fb9dbbd52b96b279a1bb5861a8c305dbfb1",
}
GLOBALLY_INTERIOR = "globally_transfer_interior"
BOUNDARY_ACTIVE = "transfer_boundary_active"

VALUE_TOLERANCE = 1.0e-12
BUDGET_TOLERANCE = 1.0e-10
ROUTE_TOLERANCE = 1.0e-8
RELATIVE_V_TOLERANCE = 1.0e-8
RESIDUAL_TOLERANCE = 1.0e-9
FULL_AK_TOLERANCE = 1.0e-12


class Failures:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def check(self, condition: bool, message: str) -> bool:
        if not condition:
            self.messages.append(message)
        return condition

    def close(self, where: str, produced: Any, rebuilt: Any, tolerance: float) -> bool:
        if produced is None or rebuilt is None:
            self.messages.append(f"{where}: missing value ({produced!r} vs {rebuilt!r})")
            return False
        gap = abs(float(produced) - float(rebuilt))
        if not (gap <= tolerance):
            self.messages.append(
                f"{where}: report {produced!r} vs independent {rebuilt!r} "
                f"(gap {gap!r} > {tolerance!r})"
            )
            return False
        return True

    def relative(self, where: str, produced: Any, rebuilt: Any, tolerance: float) -> bool:
        if produced is None or rebuilt is None:
            self.messages.append(f"{where}: missing value")
            return False
        scale = max(1.0e-300, abs(float(rebuilt)))
        gap = abs(float(produced) - float(rebuilt)) / scale
        if not (gap <= tolerance):
            self.messages.append(
                f"{where}: relative gap {gap!r} exceeds {tolerance!r} "
                f"({produced!r} vs {rebuilt!r})"
            )
            return False
        return True


def canonical_sha256(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- the checker's own numerics ---------------------------------------------------------


def simpson(values: list[float], step: float) -> float:
    """Composite Simpson on a uniform grid with an odd number of points."""
    n = len(values) - 1
    if n % 2 or n < 2:
        raise ValueError("Simpson needs an even number of intervals")
    total = values[0] + values[-1]
    total += 4.0 * sum(values[i] for i in range(1, n, 2))
    total += 2.0 * sum(values[i] for i in range(2, n - 1, 2))
    return total * step / 3.0


def interpolate(samples: list[dict[str, Any]], t: float, key: str) -> float:
    """Cubic Lagrange interpolation on the serialized sample -- not the production
    interpolant, and not the production mesh."""
    step = samples[1]["t"] - samples[0]["t"]
    index = min(max(int(t / step) - 1, 0), len(samples) - 4)
    nodes = samples[index : index + 4]
    result = 0.0
    for i, node in enumerate(nodes):
        term = node[key]
        for j, other in enumerate(nodes):
            if i != j:
                term *= (t - other["t"]) / (node["t"] - other["t"])
        result += term
    return result


def pv_wage_to(samples: list[dict[str, Any]], rate: float, t: float) -> float:
    """``int_0^t e^{-r s} W(s) ds`` by the checker's own refined Simpson rule."""
    if t <= 0.0:
        return 0.0
    n = 400
    step = t / n
    values = [
        math.exp(-rate * (step * i)) * interpolate(samples, step * i, "W")
        for i in range(n + 1)
    ]
    return simpson(values, step)


def bisect(f, lo: float, hi: float, iterations: int = 200) -> float:
    """Plain bisection: no shared root helper with production."""
    f_lo = f(lo)
    for _ in range(iterations):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if f_mid == 0.0:
            return mid
        if (f_mid > 0.0) == (f_lo > 0.0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --- checks -----------------------------------------------------------------------------


def check_path(payload: dict[str, Any], fail: Failures) -> list[dict[str, Any]]:
    block = payload["path_samples"]
    samples = block["samples"]
    path = payload["productive_path"]
    rate = path["rate_r_P"]

    fail.check(len(samples) == block["count"], "the sample count disagrees with the array")
    fail.close("W_P(0)", samples[0]["W"], path["initial_wage_W_P_0"], VALUE_TOLERANCE)
    fail.check(
        path["rest_wage_W_P_inf"] > path["initial_wage_W_P_0"] > 0.0,
        "the wage path must be positive and rising toward its rest value",
    )
    # Independent present-value wage: Simpson to the sample horizon, then the analytic
    # tail at the rest wage. Compared against the H_P - q_P K route.
    horizon = block["horizon"]
    step = horizon / (len(samples) - 1)
    integrand = [math.exp(-rate * s["t"]) * s["W"] for s in samples]
    head = simpson(integrand, step)
    tail = block["tail_wage"] * math.exp(-rate * horizon) / rate
    rebuilt = head + tail
    fail.close("pv_wage_route", path["H_P_minus_qP_K"], rebuilt, ROUTE_TOLERANCE)
    fail.check(
        abs(path["pv_wage_route_gap"]) <= ROUTE_TOLERANCE,
        f"the reported PV-wage route gap {path['pv_wage_route_gap']!r} exceeds {ROUTE_TOLERANCE!r}",
    )
    fail.check(
        block["certified_tail_beyond_integration_horizon"] < 1.0e-12,
        "the certified analytic tail is not negligible",
    )
    return samples


def check_row(
    row: dict[str, Any],
    payload: dict[str, Any],
    samples: list[dict[str, Any]],
    fail: Failures,
) -> None:
    rho = payload["configs"]["economic"].get("rho") or payload["productive_path"].get("rho")
    rate = payload["productive_path"]["rate_r_P"]
    rho = payload["rho"]
    F = row["prefunding_level_F"]
    A = row["annuity_coefficient_A"]
    tag = f"row[F={F:g}]"

    fail.check(A > 0.0, f"{tag}: the annuity coefficient must be positive")
    fail.relative(f"{tag}.V", row["successor_marginal_value_V_e"], 1.0 / A, RELATIVE_V_TOLERANCE)
    fail.check(
        row["active_set"] in (GLOBALLY_INTERIOR, BOUNDARY_ACTIVE),
        f"{tag}: unsupported active-set label {row['active_set']!r}",
    )

    switch = row["switch_time_years"]
    if row["active_set"] == GLOBALLY_INTERIOR:
        fail.check(
            switch["kind"] == "undefined" and switch["value"] is None,
            f"{tag}: a globally interior row must carry an explicit no-switch status, "
            "never a numeric sentinel",
        )
        # Interior: C = A constant (r = rho), transfers positive everywhere.
        fail.check(
            abs(rate - rho) <= VALUE_TOLERANCE,
            f"{tag}: a globally interior row requires r = rho under (16.9)",
        )
        rebuilt_A = rho * (F + payload["productive_path"]["H_P_minus_qP_K"])
        fail.relative(f"{tag}.A_interior", A, rebuilt_A, RELATIVE_V_TOLERANCE)
        # Budget in one resource measure.
        fail.close(f"{tag}.budget", A / rate - payload["productive_path"]["H_P_minus_qP_K"] - F,
                   0.0, BUDGET_TOLERANCE)
        floor = max(payload["productive_path"]["initial_wage_W_P_0"],
                    payload["productive_path"]["rest_wage_W_P_inf"])
        fail.close(f"{tag}.margin", row["minimum_transfer_margin"], A - floor, VALUE_TOLERANCE)
        fail.check(row["minimum_transfer_margin"] > 0.0,
                   f"{tag}: a globally interior row needs a strictly positive margin")
        # Off-mesh nonnegativity across the whole sample.
        for sample in samples:
            fail.check(A - sample["W"] >= -RESIDUAL_TOLERANCE,
                       f"{tag}: transfer negative at t = {sample['t']!r}")
        return

    fail.check(
        switch["kind"] == "finite" and switch["value"] is not None,
        f"{tag}: a boundary-active row must report a finite switch time",
    )
    t_star = switch["value"]
    fail.check(t_star > 0.0, f"{tag}: the switch time must be positive")

    # Continuity at the switch pins A, independently of how production found it.
    W_star = interpolate(samples, t_star, "W")
    rebuilt_A = W_star * math.exp((rho - rate) * t_star)
    fail.relative(f"{tag}.A_from_switch", A, rebuilt_A, 1.0e-6)
    switching_residual = A * math.exp((rate - rho) * t_star) - W_star
    fail.check(
        abs(switching_residual) <= 1.0e-6,
        f"{tag}: switching residual {switching_residual!r} is too large",
    )

    # The switch time implied by the reported A, found by the checker's own bisection.
    def gap(t: float) -> float:
        return A * math.exp((rate - rho) * t) - interpolate(samples, t, "W")

    if gap(1.0e-9) > 0.0 and gap(samples[-1]["t"]) < 0.0:
        rebuilt_switch = bisect(gap, 1.0e-9, samples[-1]["t"])
        fail.relative(f"{tag}.switch_from_A", t_star, rebuilt_switch, 1.0e-5)

    # Independent present-value transfer budget on [0, t*].
    annuity_pv = A * (1.0 - math.exp(-rho * t_star)) / rho
    rebuilt_budget = annuity_pv - pv_wage_to(samples, rate, t_star)
    fail.close(f"{tag}.budget", rebuilt_budget, F, 1.0e-6)
    fail.check(
        abs(row["pv_transfer_budget_residual"]) <= BUDGET_TOLERANCE,
        f"{tag}: reported budget residual {row['pv_transfer_budget_residual']!r} exceeds "
        f"{BUDGET_TOLERANCE!r}",
    )
    fail.check(
        row["minimum_transfer_margin"] is None,
        f"{tag}: a boundary-active row has no interior margin",
    )

    # Complementarity and nonnegativity, off the production mesh.
    for sample in samples:
        t, W = sample["t"], sample["W"]
        C = max(W, A * math.exp((rate - rho) * t))
        T = C - W
        fail.check(T >= -RESIDUAL_TOLERANCE, f"{tag}: transfer negative at t = {t!r}")
        if t > t_star * 1.05:
            fail.check(
                abs(C - W) <= max(RESIDUAL_TOLERANCE, 1.0e-9 * W),
                f"{tag}: consumption must equal the wage on the boundary arc, t = {t!r}",
            )
        elif t < t_star * 0.95:
            fail.check(T > 0.0, f"{tag}: transfer must be strictly positive before the switch")


def check_report(payload: dict[str, Any]) -> Failures:
    fail = Failures()
    fail.check(payload.get("schema") == SCHEMA, f"unknown schema {payload.get('schema')!r}")
    fail.check(payload.get("block") == "I2b", "the report must identify itself as I2b")
    fail.check(payload.get("result_use") == "exploratory_only", "result_use must be exploratory_only")
    spec = payload.get("specification", {})
    fail.check(
        spec.get("specification_id") == "CS012" and spec.get("sha256") == CS012_SHA256,
        "the report does not name CS012 v0.1 with its exact SHA-256",
    )
    fail.check(
        payload["provenance"]["cs011_dependency"]["resolved"]["commit_id"] == CS011_COMMIT,
        "the resolved CS011 dependency commit is not the required pin",
    )

    for role, block in payload["configs"].items():
        packet_id = block["packet_id"]
        fail.check(
            packet_id in KNOWN_FINGERPRINTS,
            f"{role}: unrecognized packet id {packet_id!r}",
        )
        expected = KNOWN_FINGERPRINTS.get(packet_id)
        if expected is not None:
            fail.check(
                block["fingerprint"] == expected,
                f"{role}: packet {packet_id} carries fingerprint "
                f"{block['fingerprint']!r}, not the published {expected!r}",
            )
        else:
            fail.check(
                isinstance(block["fingerprint"], str) and len(block["fingerprint"]) == 64,
                f"{role}: packet {packet_id} has no well-formed fingerprint",
            )

    obj = payload["economic_object"]
    fail.check(obj["source_tax_tau"] == 0.0 and obj["public_installed_equity_Theta"] == 0.0,
               "the maintained reference fixes tau = 0 and Theta = 0")

    # --- honesty gate ------------------------------------------------------------------
    audit = payload["closure_audit"]
    government = payload["government_kernels"]
    fail.check(audit["pre_event_mu_e_status"] == MU_E_UNAVAILABLE,
               f"unexpected closure status {audit['pre_event_mu_e_status']!r}")
    fail.check(government["reported"] is False and government["k_government"] is None
               and government["gamma"] is None,
               "no government kernel may be reported while mu_e is unavailable")
    for section in ("constrained_rows", "full_ak_rows", "literal_boundary", "transfer_slack"):
        text = json.dumps(payload[section])
        for forbidden in ("k_government", "gamma", "government_kernel", "mu_e"):
            fail.check(forbidden not in text, f"{section} must contain no {forbidden} field")

    i2a = payload["i2a_quarantine"]
    fail.check(i2a["status"] == "partially_quarantined", "the I2a defect must be recorded")
    fail.check(
        any("V_{P,e}" in item or "partial" in item for item in i2a["quarantined_scope"]),
        "the I2a quarantine must name the partial rows",
    )
    fail.check(
        any("full-AK" in item for item in i2a["retained_scope"]),
        "the I2a full-AK identities remain usable and must be recorded as retained",
    )

    samples = check_path(payload, fail)

    rows = payload["constrained_rows"]
    for row in rows:
        check_row(row, payload, samples, fail)

    counts = payload["active_set_counts"]
    rebuilt_counts = {
        GLOBALLY_INTERIOR: sum(1 for r in rows if r["active_set"] == GLOBALLY_INTERIOR),
        BOUNDARY_ACTIVE: sum(1 for r in rows if r["active_set"] == BOUNDARY_ACTIVE),
    }
    fail.check(counts == rebuilt_counts,
               f"active-set counts {counts} disagree with the independent recount {rebuilt_counts}")

    # --- transfer-slack threshold and F_min --------------------------------------------
    slack = payload["transfer_slack"]
    path = payload["productive_path"]
    rho, rate = payload["rho"], path["rate_r_P"]
    threshold = slack["threshold_underline_X"]
    if rate < rho:
        fail.check(threshold["kind"] == "positive_infinity",
                   "r < rho must give an infinite transfer-slack threshold (16.8)")
        fail.check(slack["F_min"] is None, "an infinite threshold has no finite F_min")
        fail.check(rebuilt_counts[GLOBALLY_INTERIOR] == 0,
                   "no row can be globally interior when the threshold is infinite")
    elif rate == rho:
        floor = max(path["initial_wage_W_P_0"], path["rest_wage_W_P_inf"])
        rebuilt_threshold = floor / rho
        fail.close("underline_X", threshold["value"], rebuilt_threshold, VALUE_TOLERANCE)
        rebuilt_F_min = rebuilt_threshold - path["H_P_minus_qP_K"]
        fail.close("F_min", slack["F_min"], rebuilt_F_min, ROUTE_TOLERANCE)
        for row in rows:
            expected = (GLOBALLY_INTERIOR if row["prefunding_level_F"] >= rebuilt_F_min
                        else BOUNDARY_ACTIVE)
            fail.check(row["active_set"] == expected,
                       f"row F={row['prefunding_level_F']!r} classified {row['active_set']!r}, "
                       f"independently {expected!r} against F_min {rebuilt_F_min!r}")
    else:
        fail.check(False, "r > rho is not a supported geometry for this block")

    reference = payload["main_interior_reference"]
    if reference is not None:
        row = next(r for r in rows if r["prefunding_level_F"] == reference["prefunding_level_F"])
        fail.close("reference.margin", reference["minimum_transfer_margin"],
                   row["minimum_transfer_margin"], VALUE_TOLERANCE)
        margin, requirement = reference["minimum_transfer_margin"], reference["requirement"]
        error = reference["credible_error"]
        expected = ("robustly_interior" if margin - error > requirement
                    else "below_requirement" if margin + error < requirement
                    else "indistinguishable")
        fail.check(reference["verdict"] == expected,
                   f"the interiority verdict {reference['verdict']!r} disagrees with the "
                   f"independent classification {expected!r}")

    # --- full AK ------------------------------------------------------------------------
    full = payload["full_ak_rows"]
    values = []
    for row in full:
        F = row["prefunding_level_F"]
        fail.check(row["wage_floor"] == 0.0, "the full-AK wage floor must be exactly zero")
        fail.relative(f"full[F={F:g}].C", row["worker_consumption_C_0"], rho * F, FULL_AK_TOLERANCE)
        fail.relative(f"full[F={F:g}].V", row["successor_marginal_value_V_e"],
                      1.0 / (rho * F), FULL_AK_TOLERANCE)
        values.append(row["successor_marginal_value_V_e"])
    levels = [row["prefunding_level_F"] for row in full]
    for i in range(len(levels) - 1):
        elasticity = (math.log(values[i + 1]) - math.log(values[i])) / (
            math.log(levels[i + 1]) - math.log(levels[i])
        )
        fail.check(abs(elasticity + 1.0) <= FULL_AK_TOLERANCE,
                   f"full-AK elasticity[{i}] = {elasticity!r} is not -1")
        fail.close(f"reported full elasticity[{i}]", payload["full_ak_elasticities"][i],
                   elasticity, VALUE_TOLERANCE)

    # --- boundary -----------------------------------------------------------------------
    boundary = payload["literal_boundary"]
    fail.check(boundary["status"] == "nonfinite_fiscal_kernel_at_literal_laissez_faire",
               "the literal boundary status is wrong")
    fail.check(boundary["full_ak"]["successor_marginal_value"]
               == {"kind": "positive_infinity", "value": None},
               "the full-AK boundary must be a tagged positive infinity")
    fail.check(boundary["full_ak"]["worker_consumption"] == {"kind": "finite", "value": 0.0},
               "full-AK worker consumption at F = 0 must be exactly zero")
    partial_limit = boundary["partial_automation"]["one_sided_limit_V_e"]
    fail.check(partial_limit["kind"] == "finite",
               "the partial one-sided limit must be finite when the wage floor is positive")
    fail.close("partial one-sided limit", partial_limit["value"],
               1.0 / path["initial_wage_W_P_0"], VALUE_TOLERANCE)

    maxima = payload["maxima"]
    fail.check(maxima["max_pv_transfer_budget_error"]
               == max(abs(r["pv_transfer_budget_residual"]) for r in rows),
               "the reported budget maximum is not the maximum over the rows")
    fail.check(maxima["max_pv_transfer_budget_error"] <= BUDGET_TOLERANCE,
               "the budget maximum exceeds its tolerance")
    fail.check(maxima["max_pv_wage_route_gap"] <= ROUTE_TOLERANCE,
               "the PV-wage route maximum exceeds its tolerance")
    return fail


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as handle:
        payload = json.load(handle, parse_constant=lambda c: (_ for _ in ()).throw(
            ValueError(f"non-standard JSON token: {c}")))
    fail = check_report(payload)
    if fail.messages:
        print(f"FAILED: {len(fail.messages)} independent reconstruction mismatch(es)")
        for message in fail.messages[:40]:
            print(f"  - {message}")
        if len(fail.messages) > 40:
            print(f"  ... and {len(fail.messages) - 40} more")
        return 1
    rows = payload["constrained_rows"]
    print("OK: independent reconstruction agrees with the CS012 I2b report")
    print(f"  scenario                 {payload['configs']['economic']['packet_id']}")
    print(f"  rho / r_P                {payload['rho']} / {payload['productive_path']['rate_r_P']}")
    print(f"  active-set counts        {payload['active_set_counts']}")
    print(f"  F_min                    {payload['transfer_slack']['F_min']}")
    print(f"  V_Pe range               {rows[0]['successor_marginal_value_V_e']!r} -> {rows[-1]['successor_marginal_value_V_e']!r}")
    print(f"  max budget error         {payload['maxima']['max_pv_transfer_budget_error']!r}")
    print(f"  max PV-wage route gap    {payload['maxima']['max_pv_wage_route_gap']!r}")
    print(f"  F -> 0+ partial limit    {payload['literal_boundary']['partial_automation']['one_sided_limit_V_e']['value']!r}")
    reference = payload["main_interior_reference"]
    print(f"  main reference           {'none' if reference is None else reference['verdict']}")
    print(f"  government kernels       absent (correct)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
