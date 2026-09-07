#!/usr/bin/env python3
"""Standalone independent checker for the CS012 I2a report.

    uv run python tools/check_cs012_i2_report.py <identity_report.json>

Standard library only. Imports nothing from ``tai_public_finance`` or
``ak_partial_ramsey`` and calls no production calculation function.

What it rebuilds from the serialized direct inputs, unaided:

* every full-AK row from ``C = rho F`` and ``V = 1/(rho F)``, and its exact -1 elasticity;
* every partial-automation row from the serialized ``q_P``, both ``H_P`` routes, and
  ``X_P = F + H_P - q_P K``, plus its elasticity;
* the event map ``e_j^+ = F - q_j K`` and the balance-sheet signs ``Theta = 0``,
  ``B = -F``, ``tau = 0``;
* SYN-02's derived ``q_F`` and ``A_bar`` from its stated rules, and every stationary
  identity that makes it stationary-compatible;
* the tagged extended-real classification at ``F = 0``, and that ``F = 0`` never entered
  a logarithm or a finite difference; and
* packet fingerprints, the ECO-02 binding, status counts, and reported maxima.

It also enforces the honesty conditions: a successor marginal value may not be presented
as a government kernel, and if the closure audit says ``mu_e`` is unavailable then no
``k^G`` or ``gamma`` may appear anywhere.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from typing import Any

SCHEMA = "cs012-i2a-successor-prefunding-report/1"
CS012_SHA256 = "d345f07cdeaf6901fd1ea985cb2566d8c717e4b4dce5ba9fa489375b895d0498"
CS011_COMMIT = "6b457682c4eed8ad4e3bdd867d1292abac38f424"
BOUND_ECO_FINGERPRINT = "2d792f4843a8024517c267cc551f2008eb86ecf1a6e7d6fc9906b0093e100568"
LITERAL_BOUNDARY_STATUS = "nonfinite_fiscal_kernel_at_literal_laissez_faire"
MU_E_UNAVAILABLE = "unavailable_missing_optimized_pre_event_value_gradient"
FROZEN_SEQUENCE = [1.0, 0.3, 0.1, 0.03, 0.01, 0.003, 0.001]

VALUE_TOLERANCE = 1.0e-12


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


def canonical_sha256(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def elasticities(levels: list[float], values: list[float]) -> list[float]:
    for level, value in zip(levels, values, strict=True):
        if level <= 0.0 or value <= 0.0:
            raise ValueError("log-log elasticity requires strictly positive points")
    return [
        (math.log(values[i + 1]) - math.log(values[i]))
        / (math.log(levels[i + 1]) - math.log(levels[i]))
        for i in range(len(levels) - 1)
    ]


def check_boundary(boundary: dict[str, Any], fail: Failures, tag: str,
                   expect_finite_partial: bool) -> None:
    fail.check(
        boundary["status"] == LITERAL_BOUNDARY_STATUS,
        f"{tag}: the literal boundary must carry {LITERAL_BOUNDARY_STATUS}",
    )
    fail.check(boundary["prefunding_level_F"] == 0.0, f"{tag}: the boundary is F = 0")
    full = boundary["full_ak"]
    fail.check(
        full["worker_consumption"] == {"kind": "finite", "value": 0.0},
        f"{tag}: full-AK worker consumption at F = 0 must be a tagged exact zero",
    )
    fail.check(
        full["successor_marginal_value"] == {"kind": "positive_infinity", "value": None},
        f"{tag}: the full-AK successor marginal value at F = 0 must be a tagged positive "
        "infinity with no numeric sentinel",
    )
    fail.check(
        boundary["excluded_from_logarithms_and_finite_differences"] is True,
        f"{tag}: the boundary must be declared excluded from logs and finite differences",
    )
    partial = boundary["partial_automation"]["successor_marginal_value"]
    if expect_finite_partial:
        fail.check(
            partial["kind"] == "finite" and partial["value"] is not None,
            f"{tag}: the partial branch keeps positive worker resources at F = 0, so its "
            "successor marginal value must be finite",
        )
    else:
        fail.check(
            partial["kind"] in ("finite", "positive_infinity"),
            f"{tag}: unexpected partial boundary classification",
        )


def check_economic(payload: dict[str, Any], fail: Failures) -> None:
    eco = payload["economic_scenario"]
    direct = payload["configs"]
    rho = eco["rho"]
    K = eco["baseline_capital"]
    q_P = eco["prices"]["q_P"]
    q_F = eco["prices"]["q_F"]
    H_P_q = eco["productive_wealth"]["H_P_quadrature"]
    H_P_a = eco["productive_wealth"]["H_P_algebraic"]

    fail.check(
        direct["prefunding"]["packet_id"] == "P-CS012-PREFUND-01",
        "the prefunding packet id is wrong",
    )
    fail.check(
        direct["economic"]["fingerprint"] == BOUND_ECO_FINGERPRINT,
        f"the economic packet fingerprint {direct['economic']['fingerprint']!r} is not "
        f"the bound ECO-02 fingerprint",
    )
    fail.check(
        eco["prefunding_levels"] == FROZEN_SEQUENCE,
        f"the prefunding sequence {eco['prefunding_levels']} is not the frozen one",
    )
    fail.check(
        all(F > 0.0 for F in eco["prefunding_levels"]),
        "F = 0 must never appear in the finite sequence",
    )
    fail.check(
        H_P_q > q_P * K,
        "the partial branch must keep strictly positive worker resources at F = 0 for "
        "this baseline",
    )
    fail.close("H_P_route_gap", eco["productive_wealth"]["H_P_route_gap"],
               abs(H_P_q - H_P_a), VALUE_TOLERANCE)
    fail.check(
        abs(H_P_q - H_P_a) <= payload["tolerance_policy"]["H_P_route_max_absolute_gap"],
        f"the two H_P routes disagree by {abs(H_P_q - H_P_a)!r}",
    )
    fail.close("H_P_minus_qP_K", eco["productive_wealth"]["H_P_minus_qP_K"],
               H_P_q - q_P * K, VALUE_TOLERANCE)
    fail.close("H_F", eco["productive_wealth"]["H_F_equals_qF_K"], q_F * K, VALUE_TOLERANCE)

    convention = eco["balance_sheet_convention"]
    fail.check(convention["public_installed_equity_Theta"] == 0.0, "Theta must be zero")
    fail.check(convention["source_tax_tau"] == 0.0, "the source tax must be zero")
    for key, debt in convention["safe_debt_B_examples"].items():
        fail.close(f"B({key})", debt, -float(key), VALUE_TOLERANCE)
        fail.check(debt < 0.0, f"B({key}) must be negative for positive inherited wealth")

    # --- full-AK rows: X_F = F exactly -------------------------------------------------
    full_values: list[float] = []
    for row in eco["full_rows"]:
        F = row["prefunding_level_F"]
        where = f"full[F={F:g}]"
        fail.close(f"{where}.X", row["worker_resources_X"], F, VALUE_TOLERANCE)
        fail.close(f"{where}.C", row["worker_consumption_C_W"], rho * F, VALUE_TOLERANCE)
        fail.close(f"{where}.V", row["successor_marginal_value_V_e"],
                   1.0 / (rho * F), max(VALUE_TOLERANCE, 1e-12 / (rho * F)))
        fail.close(f"{where}.e_plus", row["event_wealth_coordinate_e_plus"],
                   F - q_F * K, VALUE_TOLERANCE)
        fail.check(row["worker_resources_X"] > 0.0, f"{where}: X must be positive")
        fail.check(math.isfinite(row["successor_marginal_value_V_e"]),
                   f"{where}: V must be finite")
        full_values.append(row["successor_marginal_value_V_e"])

    # --- partial rows: X_P = F + H_P - q_P K -------------------------------------------
    partial_values: list[float] = []
    for row in eco["partial_rows"]:
        F = row["prefunding_level_F"]
        where = f"partial[F={F:g}]"
        X = F + H_P_q - q_P * K
        fail.close(f"{where}.X", row["worker_resources_X"], X, VALUE_TOLERANCE)
        fail.close(f"{where}.C", row["worker_consumption_C_W"], rho * X, VALUE_TOLERANCE)
        fail.close(f"{where}.V", row["successor_marginal_value_V_e"],
                   1.0 / (rho * X), VALUE_TOLERANCE)
        fail.close(f"{where}.e_plus", row["event_wealth_coordinate_e_plus"],
                   F - q_P * K, VALUE_TOLERANCE)
        fail.check(row["worker_resources_X"] > 0.0, f"{where}: X must be positive")
        partial_values.append(row["successor_marginal_value_V_e"])

    levels = eco["prefunding_levels"]
    full_elasticities = elasticities(levels, full_values)
    partial_elasticities = elasticities(levels, partial_values)
    for index, value in enumerate(full_elasticities):
        fail.check(
            abs(value + 1.0)
            <= payload["tolerance_policy"]["full_ak_elasticity_max_absolute_error"],
            f"full-AK elasticity[{index}] = {value!r} is not -1",
        )
        fail.close(f"reported full elasticity[{index}]",
                   eco["elasticities"]["full_ak"][index], value, VALUE_TOLERANCE)
    for index, value in enumerate(partial_elasticities):
        fail.close(f"reported partial elasticity[{index}]",
                   eco["elasticities"]["partial"][index], value, VALUE_TOLERANCE)
    fail.check(
        abs(partial_elasticities[-1]) < abs(partial_elasticities[0]),
        "the partial elasticity must shrink toward zero as F decreases",
    )
    fail.check(
        abs(partial_elasticities[-1]) < 0.5,
        f"the partial elasticity {partial_elasticities[-1]!r} should approach zero, not -1",
    )

    tvc = eco["safe_position_tvc"]
    fail.check(tvc["utility_discounted_tvc_holds"] is True
               and tvc["market_discounted_tvc_holds"] is True,
               "the discounted gross safe-position TVC must hold")
    fail.close("F_growth_rate", tvc["F_growth_rate"], eco["r_F_bar"] - rho, VALUE_TOLERANCE)

    check_boundary(eco["literal_boundary"], fail, "economic", expect_finite_partial=True)

    maxima = eco["maxima"]
    fail.check(
        maxima["max_full_ak_elasticity_absolute_error"]
        == max(abs(e + 1.0) for e in eco["elasticities"]["full_ak"]),
        "the reported full-AK elasticity maximum is not the maximum over the rows",
    )


def check_syn02(payload: dict[str, Any], fail: Failures) -> None:
    syn = payload["syn02"]
    direct = syn["direct_fields"]
    fail.check(syn["packet_id"] == "P-CS012-SYN-02", "SYN-02 packet id is wrong")
    fail.check(direct["construction"] == "direct",
               "SYN-02 must declare itself directly constructed")
    fail.check(
        "two_mark" not in json.dumps(direct).lower()
        and direct["fixture_scope"] == "full_ak_pure_safe_fund_benchmark",
        "SYN-02 must not claim to be a two-mark scenario",
    )
    rho = direct["preferences"]["rho"]
    varphi = direct["installation"]["varphi"]
    delta = direct["installation"]["delta"]
    g = direct["target_growth_g"]

    r_F = rho + g
    q_F = math.exp(varphi * (g + delta))
    A_bar = q_F * (r_F - g) + (q_F - 1.0) / varphi
    fail.close("syn02.r_F_bar", syn["derived"]["r_F_bar"], r_F, VALUE_TOLERANCE)
    fail.close("syn02.q_F", syn["derived"]["q_F"], q_F, VALUE_TOLERANCE)
    fail.close("syn02.A_bar", syn["derived"]["A_bar"], A_bar, VALUE_TOLERANCE)
    stated = direct.get("analytic_expectations")
    if stated is not None:
        # Stated and derived must pin each other; either drifting is a defect.
        for label, rebuilt in (("r_F_bar", r_F), ("q_F", q_F), ("A_bar", A_bar),
                               ("implied_growth", math.log(q_F) / varphi - delta),
                               ("stationary_residual", r_F - rho - g),
                               ("productive_tvc_margin", r_F - g)):
            fail.close(f"syn02.stated.{label}", stated[label], rebuilt, VALUE_TOLERANCE)

    checks = syn["analytic_checks"]
    iota = (q_F - 1.0) / varphi
    growth = math.log(q_F) / varphi - delta
    user_cost = r_F * q_F - (A_bar - iota + q_F * growth)
    bound = payload["tolerance_policy"]["syn02_identity_max_absolute_residual"]
    fail.check(abs(user_cost) <= bound,
               f"syn02: independent user-cost residual {user_cost!r} exceeds {bound!r}")
    fail.close("syn02.user_cost_residual", checks["zero_tax_user_cost_residual"],
               user_cost, VALUE_TOLERANCE)
    fail.check(abs(growth - g) <= bound,
               f"syn02: g recovered from q_F is {growth!r}, not {g!r}")
    fail.close("syn02.growth_recovery_residual", checks["growth_recovery_residual"],
               growth - g, VALUE_TOLERANCE)
    fail.check(abs(r_F - rho - g) <= bound,
               f"syn02 is not stationary-compatible: r_F - rho - g = {r_F - rho - g!r}")
    # The reported residual must be the one the primitives actually imply, not a
    # number that merely happens to sit near zero.
    fail.close("syn02.stationary_compatibility_residual",
               checks["stationary_compatibility_residual"], r_F - rho - g, VALUE_TOLERANCE)
    fail.check(
        abs(checks["stationary_compatibility_residual"]) <= bound,
        f"syn02 reports a nonzero stationary residual "
        f"{checks['stationary_compatibility_residual']!r}",
    )
    fail.close("syn02.tvc_margin", checks["productive_tvc_margin"], r_F - g, VALUE_TOLERANCE)
    fail.check(checks["productive_tvc_margin"] > 0.0,
               "syn02 must satisfy the strict productive-value TVC")

    values = []
    for row in syn["rows"]:
        F = row["prefunding_level_F"]
        fail.check(F > 0.0, "syn02: F = 0 must not be a row")
        fail.close(f"syn02[F={F:g}].C", row["worker_consumption_C_W"], rho * F,
                   VALUE_TOLERANCE)
        fail.close(f"syn02[F={F:g}].V", row["successor_marginal_value_V_e"],
                   1.0 / (rho * F), max(VALUE_TOLERANCE, 1e-12 / (rho * F)))
        values.append(row["successor_marginal_value_V_e"])
    for index, value in enumerate(elasticities([r["prefunding_level_F"] for r in syn["rows"]],
                                               values)):
        fail.check(abs(value + 1.0) <= 1.0e-12,
                   f"syn02 elasticity[{index}] = {value!r} is not -1")
    check_boundary(syn["literal_boundary"], fail, "syn02", expect_finite_partial=False)


def check_report(payload: dict[str, Any]) -> Failures:
    fail = Failures()
    fail.check(payload.get("schema") == SCHEMA, f"unknown schema {payload.get('schema')!r}")
    fail.check(payload.get("block") == "I2a", "the report must identify itself as I2a")
    fail.check(payload.get("result_use") == "exploratory_only",
               f"result_use must be exploratory_only, not {payload.get('result_use')!r}")
    spec = payload.get("specification", {})
    fail.check(
        spec.get("specification_id") == "CS012" and spec.get("version") == "0.1"
        and spec.get("sha256") == CS012_SHA256,
        "the report does not name CS012 v0.1 with its exact SHA-256",
    )
    fail.check(
        payload["provenance"]["cs011_dependency"]["resolved"]["commit_id"] == CS011_COMMIT,
        "the resolved CS011 dependency commit is not the required pin",
    )

    for section in ("prefunding", "analytic"):
        key = {"prefunding": "prefunding", "analytic": "syn02"}[section]
        block = payload["syn02"] if key == "syn02" else None
        if block is not None:
            rebuilt = canonical_sha256(block["direct_fields"])
            fail.check(
                payload["configs"]["analytic"]["fingerprint"] == rebuilt,
                "the SYN-02 fingerprint does not match the digest of its own direct fields",
            )

    quarantine = payload["syn01_quarantine"]
    fail.check(quarantine["packet_id"] == "P-CS012-SYN-01"
               and quarantine["status"] == "quarantined",
               "P-CS012-SYN-01 must be recorded as quarantined")
    fail.check(
        "stationary" in quarantine["defect"] and "false" in quarantine["defect"].lower(),
        "the SYN-01 quarantine must name the false stationary-compatible claim",
    )
    fail.check(
        "stationary" not in quarantine["true_character"].lower(),
        "SYN-01's true character must not be described as stationary-compatible",
    )

    # --- honesty gate ------------------------------------------------------------------
    audit = payload["closure_audit"]
    government = payload["government_kernels"]
    if audit["pre_event_mu_e_status"] == MU_E_UNAVAILABLE:
        fail.check(audit["government_kernels_permitted"] is False,
                   "an unavailable mu_e must not permit government kernels")
        fail.check(government["reported"] is False,
                   "government kernels must not be reported when mu_e is unavailable")
        fail.check(government["k_government"] is None and government["gamma"] is None,
                   "k^G and gamma must be absent when mu_e is unavailable")
        text = json.dumps(payload["economic_scenario"])
        for forbidden in ("k_government", "gamma", "government_kernel", "mu_e"):
            fail.check(forbidden not in text,
                       f"the economic section must contain no {forbidden} field")
        fail.check(
            "not a government kernel" in json.dumps(payload["interpretation_limits"]).lower()
            or "NOT a government kernel" in json.dumps(payload["interpretation_limits"]),
            "the limits must state that a successor marginal value is not a government kernel",
        )
    else:
        fail.check(False,
                   f"unexpected closure status {audit['pre_event_mu_e_status']!r}; a "
                   "checker update is required before finite kernels are accepted")

    check_economic(payload, fail)
    check_syn02(payload, fail)
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
        for message in fail.messages:
            print(f"  - {message}")
        return 1
    eco = payload["economic_scenario"]
    boundary = eco["literal_boundary"]
    print("OK: independent reconstruction agrees with the CS012 I2a report")
    print(f"  closure audit            {payload['closure_audit']['pre_event_mu_e_status']}")
    print(f"  government kernels       {'REPORTED' if payload['government_kernels']['reported'] else 'absent (correct)'}")
    print(f"  prefunding sequence      {eco['prefunding_levels']}")
    print(f"  H_P - q_P K              {eco['productive_wealth']['H_P_minus_qP_K']!r}")
    print(f"  full-AK elasticities     all -1 within {payload['tolerance_policy']['full_ak_elasticity_max_absolute_error']}")
    print(f"  partial elasticity range {eco['elasticities']['partial'][0]!r} -> {eco['elasticities']['partial'][-1]!r}")
    print(f"  F = 0 full-AK            C_W = 0, V_e = {boundary['full_ak']['successor_marginal_value']['kind']}")
    print(f"  F = 0 partial            V_e = {boundary['partial_automation']['successor_marginal_value']['value']!r} (finite)")
    print(f"  SYN-01                   {payload['syn01_quarantine']['status']}")
    print(f"  SYN-02 q_F / A_bar       {payload['syn02']['derived']['q_F']!r} / {payload['syn02']['derived']['A_bar']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
