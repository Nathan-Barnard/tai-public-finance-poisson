#!/usr/bin/env python3
"""Standalone independent checker for the CS012 I1 owner-branch report.

    uv run python tools/check_cs012_i1_report.py <identity_report.json>

Imports nothing from ``tai_public_finance`` and nothing from ``ak_partial_ramsey``, and
calls no production I1 report, root, or kernel function. Standard-library arithmetic and
JSON parsing only.

**Scope of the independence claim, stated honestly.** From the serialized direct fields
this script rebuilds, without help:

* ``q_0 = exp(varphi*delta)`` from the installation primitives;
* each ``J_j = q_j/q_0 - 1`` from the serialized successor prices;
* each world kernel ``k^w_j = lambda*_j/lambda_j``;
* each owner kernel ``k^K_j`` from the reported before/after owner wealth;
* every ``D_K`` contribution, the aggregate, and the residual at the reported exposure;
* positive wealth multipliers and both distances to the exposure boundary;
* the AK level-equation residual and the strict-TVC branch classification of *every*
  enumerated root, accepted or rejected; and
* identifiers, packet fingerprints, status counts and reported maxima.

It does **not** re-derive the partial-automation stable manifold. ``q_P(K)`` and
``H_P(K)`` are treated as serialized data. Manifold construction is evidenced by the
pinned CS011 dependency's own IVP-versus-collocation and quadrature-versus-algebraic
comparisons, which this script checks are present and within their reported bounds, and
by that dependency's own test suite at the pinned commit -- not by this script. Calling
this a second manifold route would be false.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from typing import Any

SCHEMA = "cs012-i1-owner-branch-report/1"
CS012_SHA256 = "d345f07cdeaf6901fd1ea985cb2566d8c717e4b4dce5ba9fa489375b895d0498"
CS011_COMMIT = "6b457682c4eed8ad4e3bdd867d1292abac38f424"

VALUE_TOLERANCE = 1.0e-12
DISCREPANCY_TOLERANCE = 1.0e-14


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


def normalized_error(lhs: float, rhs: float, terms: list[float]) -> float:
    return abs(lhs - rhs) / max(1.0, math.fsum(abs(t) for t in terms))


def canonical_sha256(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def check_ak(entry: dict[str, Any], direct: dict[str, Any], fail: Failures, tag: str) -> None:
    """Re-derive the AK level equation and the strict-TVC classification of every root."""
    varphi = direct["installation"]["varphi"]
    delta = direct["installation"]["delta"]
    A_bar = direct["technology"]["A_bar"]
    rF = direct["world_rates"]["r_F_bar"]

    def iota(q: float) -> float:
        return (q - 1.0) / varphi

    def growth(q: float) -> float:
        return math.log(q) / varphi - delta

    u = varphi * (rF + delta)
    a_coefficient = 1.0 + varphi * A_bar
    q_minimiser = math.exp(u)

    accepted = []
    for candidate in entry["candidates"]:
        q = candidate["q"]
        where = f"{tag}.ak[q={q!r}]"
        # r_F_bar q = A_bar - iota(q) + q g(q)
        level = rF * q - (A_bar - iota(q) + q * growth(q))
        polynomial = q * math.log(q) - (1.0 + u) * q + a_coefficient
        fail.check(
            abs(level) <= 1.0e-9,
            f"{where}: independent AK level residual {level!r} is not zero",
        )
        fail.close(f"{where}.residual_polynomial", candidate["residual_polynomial"], polynomial, 1.0e-9)
        tvc = rF - growth(q)
        fail.close(f"{where}.tvc_margin", candidate["tvc_margin"], tvc, VALUE_TOLERANCE)
        # Branch identity is position relative to the analytic minimiser, and
        # acceptance is the strict productive-value TVC on the lower branch alone.
        relative = (q - q_minimiser) / q_minimiser
        if abs(relative) <= 1e-10:
            expected_branch, expected_accept = "double_root_zero_tvc_margin", False
        elif q < q_minimiser:
            expected_branch, expected_accept = "lower_strict_tvc", tvc > 0.0
        else:
            expected_branch, expected_accept = "upper_tvc_violating", False
        fail.check(
            candidate["branch"] == expected_branch,
            f"{where}: branch {candidate['branch']!r} disagrees with the independent "
            f"classification {expected_branch!r} against q_m = {q_minimiser!r}",
        )
        fail.check(
            candidate["accepted"] is expected_accept,
            f"{where}: acceptance {candidate['accepted']!r} disagrees with the "
            f"independent strict-TVC verdict {expected_accept!r}",
        )
        if expected_accept:
            accepted.append(q)

    fail.check(
        len(accepted) == 1,
        f"{tag}.ak: exactly one root must pass the strict productive-value TVC; "
        f"independently found {len(accepted)}",
    )
    if accepted:
        fail.close(f"{tag}.ak.selected_q_F", entry["selected_q_F"], accepted[0], VALUE_TOLERANCE)
    fail.check(
        entry["n_roots_enumerated"] == len(entry["candidates"]),
        f"{tag}.ak: the enumerated-root count disagrees with the retained candidates",
    )
    fail.check(
        entry["n_accepted"] == len(accepted),
        f"{tag}.ak: the accepted count disagrees with the independent recount",
    )


def check_owner(owner: dict[str, Any], direct: dict[str, Any], fail: Failures, tag: str) -> dict:
    """Rebuild every owner-side quantity from the serialized fields."""
    varphi = direct["installation"]["varphi"]
    delta = direct["installation"]["delta"]
    q_0 = math.exp(varphi * delta)
    fail.close(f"{tag}.q_0", owner["q_0"], q_0, VALUE_TOLERANCE)

    shock = direct["shock_law"]
    intensities = {
        "P": (shock["lambda_P"], shock["lambda_P_star"]),
        "F": (shock["lambda_F"], shock["lambda_F_star"]),
    }
    fail.check(
        [m["mark_id"] for m in owner["marks"]] == ["P", "F"],
        f"{tag}: mark labels or order differ from the declared (P, F)",
    )
    # The physical split is an identity of the marked-Poisson law; the risk-neutral
    # intensities are separate direct fields and are never inferred from it.
    for label, probability in (("P", shock["p_P"]), ("F", shock["p_F"])):
        fail.close(
            f"{tag}.lambda_{label}",
            intensities[label][0],
            shock["lambda_total"] * probability,
            VALUE_TOLERANCE,
        )

    # A reported exposure is only meaningful under a unique interior root. Any other
    # status alongside a numeric exposure is a contradiction, not a weaker claim.
    fail.check(
        owner["root_status"] == "unique_interior_root",
        f"{tag}: root_status {owner['root_status']!r} contradicts a reported owner "
        "exposure; I1 accepts only unique_interior_root",
    )
    fail.check(
        owner["exposure"] is not None and math.isfinite(owner["exposure"]),
        f"{tag}: a unique interior root must report a finite exposure",
    )

    pi = owner["exposure"]
    contributions: list[float] = []
    residual_terms: list[float] = []
    for mark in owner["marks"]:
        label = mark["mark_id"]
        where = f"{tag}/{label}"
        lam, lam_star = intensities[label]
        fail.close(f"{where}.lambda_physical", mark["lambda_physical"], lam, VALUE_TOLERANCE)
        fail.close(f"{where}.lambda_risk_neutral", mark["lambda_risk_neutral"], lam_star, VALUE_TOLERANCE)

        k_world = lam_star / lam
        fail.close(f"{where}.k_world", mark["k_world"], k_world, VALUE_TOLERANCE)

        multiplier = 1.0 + pi * mark["payoff_jump"]
        fail.close(f"{where}.wealth_multiplier", mark["wealth_multiplier"], multiplier, VALUE_TOLERANCE)
        fail.check(
            mark["wealth_multiplier"] > 0.0,
            f"{where}: owner wealth multiplier {mark['wealth_multiplier']!r} is not "
            "strictly positive; this is an inadmissible private portfolio",
        )
        fail.check(
            abs(mark["payoff_jump"]) >= 1.0e-3,
            f"{where}: |J| = {abs(mark['payoff_jump'])!r} is below the declared 1e-3 "
            "floor, so the owner exposure is weakly identified",
        )

        # Owner kernel from the reported before/after wealth: k^K = C^{K,-}/C^{K,+}.
        before, after = mark["owner_wealth_before"], mark["owner_wealth_after"]
        fail.check(before > 0.0 and after > 0.0, f"{where}: owner wealth must stay positive")
        fail.close(f"{where}.owner_wealth_after", after, before * multiplier, VALUE_TOLERANCE)
        fail.close(f"{where}.k_owner_from_wealth_ratio", mark["k_owner"], before / after, VALUE_TOLERANCE)

        contribution = lam * (before / after - k_world) * mark["payoff_jump"]
        fail.close(f"{where}.d_owner_contribution", mark["d_owner_contribution"], contribution, VALUE_TOLERANCE)
        contributions.append(contribution)
        residual_terms.append(lam * (1.0 / multiplier - k_world) * mark["payoff_jump"])

    d_owner = math.fsum(contributions)
    fail.close(f"{tag}.d_owner", owner["d_owner"], d_owner, VALUE_TOLERANCE)
    residual = math.fsum(residual_terms)
    residual_normalized = normalized_error(residual, 0.0, contributions)
    fail.check(
        residual_normalized <= 1.0e-10,
        f"{tag}: independent owner-root normalized residual {residual_normalized!r} "
        "exceeds 1e-10; the reported exposure does not solve the pricing equation",
    )

    # Exposure interval, independently: the open intersection of 1 + pi J_j > 0.
    lower, upper = -math.inf, math.inf
    for mark in owner["marks"]:
        jump = mark["payoff_jump"]
        if jump > 0.0:
            lower = max(lower, -1.0 / jump)
        elif jump < 0.0:
            upper = min(upper, -1.0 / jump)
    interval = owner["exposure_interval"]
    fail.check(
        lower < 0.0 < upper and interval["zero_is_interior"] is True,
        f"{tag}: zero exposure must be interior to the admissible interval",
    )
    fail.check(lower < pi < upper, f"{tag}: the reported exposure {pi!r} is not interior")
    # An endpoint is unbounded exactly when no payoff component pushes that way. The
    # report must then carry null plus a flag, never a token or a sentinel.
    fail.check(
        interval["lower_is_finite"] == math.isfinite(lower)
        and interval["upper_is_finite"] == math.isfinite(upper),
        f"{tag}: interval finiteness flags disagree with the independent interval",
    )
    if math.isfinite(lower):
        fail.close(f"{tag}.interval.lower", interval["lower"], lower, VALUE_TOLERANCE)
        fail.close(f"{tag}.lower_boundary_distance", owner["lower_boundary_distance"], pi - lower, VALUE_TOLERANCE)
        fail.check(owner.get("lower_boundary_is_unbounded") is False,
                   f"{tag}: a finite lower endpoint must not be flagged unbounded")
    else:
        fail.check(
            owner["lower_boundary_distance"] is None
            and owner.get("lower_boundary_is_unbounded") is True,
            f"{tag}: an unbounded lower endpoint must serialize as null plus a flag",
        )
    if math.isfinite(upper):
        fail.close(f"{tag}.interval.upper", interval["upper"], upper, VALUE_TOLERANCE)
        fail.close(f"{tag}.upper_boundary_distance", owner["upper_boundary_distance"], upper - pi, VALUE_TOLERANCE)
        fail.check(owner.get("upper_boundary_is_unbounded") is False,
                   f"{tag}: a finite upper endpoint must not be flagged unbounded")
    else:
        fail.check(
            owner["upper_boundary_distance"] is None
            and owner.get("upper_boundary_is_unbounded") is True,
            f"{tag}: an unbounded upper endpoint must serialize as null plus a flag",
        )

    derivative = -math.fsum(
        m["lambda_physical"] * m["payoff_jump"] ** 2 / (1.0 + pi * m["payoff_jump"]) ** 2
        for m in owner["marks"]
    )
    fail.check(derivative < 0.0, f"{tag}: the owner residual derivative must be strictly negative")
    fail.close(f"{tag}.derivative_at_root", owner["derivative_at_root"], derivative, VALUE_TOLERANCE)

    for mark in owner["marks"]:
        for name in ("payoff_jump", "k_world", "k_owner", "wealth_multiplier", "d_owner_contribution"):
            fail.check(
                math.isfinite(mark[name]),
                f"{tag}/{mark['mark_id']}: {name} is not finite on the I1 finite branch",
            )
    fail.check(
        "k_government" not in json.dumps(owner) and "gamma" not in json.dumps(owner),
        f"{tag}: a government kernel field is present; I1 produces no government object",
    )
    return {"residual_normalized": residual_normalized, "d_owner": d_owner}


def check_report(payload: dict[str, Any]) -> Failures:
    fail = Failures()
    fail.check(payload.get("schema") == SCHEMA, f"unknown schema {payload.get('schema')!r}")
    fail.check(payload.get("block") == "I1", "the report does not identify itself as block I1")
    fail.check(
        payload.get("result_use") == "exploratory_only",
        f"result_use must be exploratory_only, not {payload.get('result_use')!r}",
    )
    spec = payload.get("specification", {})
    fail.check(
        spec.get("specification_id") == "CS012"
        and spec.get("version") == "0.1"
        and spec.get("sha256") == CS012_SHA256,
        "the report does not name CS012 v0.1 with its exact SHA-256",
    )
    deviations = payload.get("deviations", [])
    fail.check(
        any(d.get("id") == "DEV-01" and d.get("result_use_ceiling") == "exploratory_only"
            for d in deviations),
        "DEV-01 is missing or does not carry the exploratory_only ceiling",
    )

    dependency = payload["provenance"]["cs011_dependency"]["resolved"]
    fail.check(
        dependency.get("commit_id") == CS011_COMMIT,
        f"the resolved CS011 dependency commit {dependency.get('commit_id')!r} is not "
        f"the required {CS011_COMMIT}",
    )

    # --- packet fingerprints -------------------------------------------------------
    for section in ("synthetic", "economic"):
        packet = payload[section]["packet"]
        rebuilt = canonical_sha256(packet["direct_fields"])
        fail.check(
            packet["fingerprint"] == rebuilt,
            f"{section} packet fingerprint {packet['fingerprint']!r} does not match the "
            f"independent digest {rebuilt!r} of its own direct fields",
        )
    fail.check(
        payload["synthetic"]["packet"]["direct_fields"]["dependency_commit"] == CS011_COMMIT,
        "the synthetic packet does not pin the required dependency commit",
    )
    fail.check(
        payload["economic"]["packet"]["packet_kind"] == "provisional_illustrative_economic_scenario",
        "the economic packet must declare itself provisional and illustrative",
    )

    # --- synthetic regressions -----------------------------------------------------
    synthetic = payload["synthetic"]
    reproduced = sum(1 for r in synthetic["regressions"] if r["status"] == "reproduced")
    fail.check(
        synthetic["counts"]["reproduced"] == reproduced
        and synthetic["counts"]["fixtures_run"] == len(synthetic["regressions"]),
        "the synthetic regression counts disagree with the independent recount",
    )
    for regression in synthetic["regressions"]:
        fixture = regression["fixture"]
        if fixture["provenance"] == "manufactured":
            fail.check(
                "None." in fixture["economic_interpretation"],
                f"manufactured fixture {fixture['name']!r} no longer states that it has "
                "no economic interpretation",
            )

    # --- economic scenario ---------------------------------------------------------
    economic = payload["economic"]
    direct = economic["packet"]["direct_fields"]
    fail.check(
        economic.get("government_objects_present") is False,
        "the economic section does not declare the absence of government objects",
    )
    check_ak(economic["ak_successor"], direct, fail, "economic")

    partial = economic["partial_successor"]
    declared = direct["successor_domains"]["partial_capital_interval"]
    fail.check(
        partial["certified_domain"][0] <= declared[0] and partial["certified_domain"][1] >= declared[1],
        f"the certified partial domain {partial['certified_domain']} does not cover the "
        f"declared interval {declared}",
    )
    fail.check(partial["covers_declared_interval"] is True, "the partial manifold does not cover its declared interval")
    routes = partial["independent_route_diagnostics"]
    for name, bound in (
        ("max_ivp_bvp_difference", 1.0e-6),
        ("wealth_route_max_gap", 1.0e-6),
        ("manifold_invariance_max_residual", 1.0e-5),
        ("rest_point_slope_gap", 1.0e-6),
    ):
        value = routes.get(name)
        fail.check(
            value is not None and abs(value) <= bound,
            f"partial successor: dependency diagnostic {name} = {value!r} is missing or "
            f"exceeds {bound!r}",
        )

    baseline = check_owner(economic["baseline"], direct, fail, "baseline")
    fail.close(
        "baseline.capital",
        economic["baseline"]["capital"],
        direct["diagnostics"]["baseline_capital"],
        VALUE_TOLERANCE,
    )

    residuals = [baseline["residual_normalized"]]
    valid = 0
    quarantined = 0
    grid_points = [row["capital"] for row in economic["diagnostic_grid"]]
    fail.check(
        grid_points == direct["diagnostics"]["diagnostic_capital_grid"],
        f"the reported grid {grid_points} differs from the declared grid "
        f"{direct['diagnostics']['diagnostic_capital_grid']}",
    )
    lo, hi = partial["certified_domain"]
    for row in economic["diagnostic_grid"]:
        K = row["capital"]
        flags = row["flags"]
        inside = lo <= K <= hi
        fail.check(
            flags["inside_certified_domain"] == inside,
            f"grid K={K!r}: the certified-domain flag disagrees with the reported domain",
        )
        if flags["valid"]:
            valid += 1
            fail.check(not flags["quarantined"], f"grid K={K!r}: a valid row is flagged quarantined")
            fail.check(flags["reliable_domain"] and inside, f"grid K={K!r}: a valid row must sit inside the certified domain")
            result = check_owner(row["owner"], direct, fail, f"grid[K={K!r}]")
            residuals.append(result["residual_normalized"])
            fail.close(f"grid[K={K!r}].d_owner", row["d_owner"], result["d_owner"], VALUE_TOLERANCE)
        else:
            quarantined += 1
            fail.check(flags["quarantined"], f"grid K={K!r}: an invalid row must be quarantined")
            fail.check(row["owner"] is None, f"grid K={K!r}: a quarantined row must carry no owner result")
    fail.check(
        economic["counts"]["valid_rows"] == valid
        and economic["counts"]["quarantined_rows"] == quarantined
        and economic["counts"]["grid_rows"] == len(economic["diagnostic_grid"]),
        "the grid row counts disagree with the independent recount",
    )
    fail.check(
        len(economic["quarantined_rows"]) == quarantined,
        "the quarantined-row list disagrees with the independent recount",
    )

    maxima = economic["maxima"]
    reported_residuals = [
        abs(row["residual_at_root"]) for row in economic["diagnostic_grid"] if row["flags"]["valid"]
    ]
    fail.check(
        maxima["max_owner_root_residual"] == max(reported_residuals, default=0.0),
        "summary.max_owner_root_residual is not the maximum over the verified rows",
    )
    fail.check(
        max(residuals) <= 1.0e-10,
        f"the largest independent owner-root residual {max(residuals)!r} exceeds 1e-10",
    )
    for name in (
        "max_independent_exposure_residual",
        "max_independent_kernel_error",
        "max_independent_d_owner_error",
    ):
        fail.check(
            maxima[name] <= 1.0e-10,
            f"reported {name} = {maxima[name]!r} exceeds 1e-10",
        )
    return fail


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as handle:
        payload = json.load(handle)
    fail = check_report(payload)
    if fail.messages:
        print(f"FAILED: {len(fail.messages)} independent reconstruction mismatch(es)")
        for message in fail.messages:
            print(f"  - {message}")
        return 1
    economic = payload["economic"]
    baseline = economic["baseline"]
    marks = {m["mark_id"]: m for m in baseline["marks"]}
    print("OK: independent reconstruction agrees with the CS012 I1 report")
    print(f"  CS011 dependency commit  {payload['provenance']['cs011_dependency']['resolved']['commit_id']}")
    print(f"  economic packet          {economic['packet']['packet_id']} / {economic['packet']['fingerprint'][:16]}")
    print(f"  q_0                      {baseline['q_0']!r}")
    print(f"  q_F (selected, lower)    {economic['ak_successor']['selected_q_F']!r}")
    print(f"  AK roots enum/accepted   {economic['counts']['ak_roots_enumerated']}/{economic['counts']['ak_roots_accepted']}")
    print(f"  J_P / J_F                {marks['P']['payoff_jump']!r} / {marks['F']['payoff_jump']!r}")
    print(f"  owner exposure pi        {baseline['exposure']!r}")
    print(f"  X^K_P / X^K_F            {marks['P']['wealth_multiplier']!r} / {marks['F']['wealth_multiplier']!r}")
    print(f"  k^w_P / k^w_F            {marks['P']['k_world']!r} / {marks['F']['k_world']!r}")
    print(f"  k^K_P / k^K_F            {marks['P']['k_owner']!r} / {marks['F']['k_owner']!r}")
    print(f"  D_K                      {baseline['d_owner']!r}")
    print(f"  grid valid/quarantined   {economic['counts']['valid_rows']}/{economic['counts']['quarantined_rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
