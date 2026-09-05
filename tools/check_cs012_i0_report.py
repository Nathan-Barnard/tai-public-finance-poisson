#!/usr/bin/env python3
"""Standalone independent checker for the CS012 I0 identity report.

Usage:

    uv run python tools/check_cs012_i0_report.py <report.json>

This script reconstructs every kernel, term contribution, residual sum, identity
discrepancy, projection object, weighted norm, status, status count, and reported
maximum error **from the serialized direct inputs alone**. It imports nothing from
``tai_public_finance`` and calls no production kernel, root, projection, or report
function; it uses only Python standard-library arithmetic and JSON parsing. That
is what makes disagreement informative rather than tautological.

Exit code 0 means every reconstructed value matched within the report's own
declared tolerance policy. Any mismatch prints the offending path and exits 1.
"""

from __future__ import annotations

import json
import math
import sys
from typing import Any

SCHEMA = "cs012-i0-identity-report/1"
BRANCH_FINITE = "finite_maintained_branch"
BRANCH_LITERAL_LAISSEZ_FAIRE = "literal_laissez_faire"

FINITE_MAINTAINED_BRANCH = "finite_maintained_branch"
NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE = (
    "nonfinite_fiscal_kernel_at_literal_laissez_faire"
)
UNIQUE_INTERIOR_ROOT = "unique_interior_root"
NO_INTERIOR_ROOT_BOUNDARY_LIMIT = "no_interior_root_boundary_limit"
ZERO_PAYOFF_UNIDENTIFIED = "zero_payoff_unidentified"
PROJECTION_RESOLVED = "projection_resolved"
ZERO_PAYOFF_NORM_REFUSED = "zero_payoff_norm_refused"

# Absolute floor for comparing two independently computed FP64 values of the same
# well-conditioned quantity. Normalized identity comparisons use the report's own
# declared tolerance policy instead.
VALUE_TOLERANCE = 1.0e-12

# Identity discrepancies and root residuals are pure rounding noise on the
# well-conditioned fixtures (order 1e-17), so they get a much tighter absolute
# comparison than ordinary kernel values: a report that overstates or understates
# its own discrepancy must not slip through under a 1e-12 blanket.
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
            self.messages.append(f"{where}: missing value (report {produced!r}, rebuilt {rebuilt!r})")
            return False
        gap = abs(float(produced) - float(rebuilt))
        if not (gap <= tolerance):
            self.messages.append(
                f"{where}: report {produced!r} vs independent {rebuilt!r} (gap {gap!r} > {tolerance!r})"
            )
            return False
        return True


def normalized_error(lhs: float, rhs: float, terms: list[float]) -> float:
    scale = max(1.0, math.fsum(abs(term) for term in terms))
    return abs(lhs - rhs) / scale


def weighted_norm(weights: list[float], values: list[float]) -> float:
    return math.sqrt(math.fsum(w * v * v for w, v in zip(weights, values, strict=True)))


def exposure_interval(payoffs: list[float]) -> tuple[float, float]:
    lower, upper = -math.inf, math.inf
    for jump in payoffs:
        if jump > 0.0:
            lower = max(lower, -1.0 / jump)
        elif jump < 0.0:
            upper = min(upper, -1.0 / jump)
    return lower, upper


def owner_residual(marks: list[dict[str, Any]], exposure: float) -> float:
    total = 0.0
    for mark in marks:
        lam = mark["lambda_physical"]
        lam_star = mark["lambda_risk_neutral"]
        jump = mark["payoff_jump"]
        total += lam * (1.0 / (1.0 + exposure * jump) - lam_star / lam) * jump
    return total


def _finite_branch_admissible(inputs: dict[str, Any]) -> bool:
    """Re-derive whether the fixture belongs on the finite maintained branch."""
    exposure = inputs["owner_exposure"]
    mu = inputs["government_current_marginal_value"]
    if not math.isfinite(exposure) or not math.isfinite(mu) or mu <= 0.0:
        return False
    for mark in inputs["marks"]:
        lam = mark["lambda_physical"]
        lam_star = mark["lambda_risk_neutral"]
        jump = mark["payoff_jump"]
        successor = mark["government_successor_marginal_value"]
        if not math.isfinite(lam) or lam <= 0.0:
            return False
        if not math.isfinite(lam_star) or lam_star < 0.0:
            return False
        if not math.isfinite(jump):
            return False
        if successor.get("kind") != "finite":
            return False
        value = successor.get("value")
        if value is None or not math.isfinite(value) or value <= 0.0:
            return False
        if 1.0 + exposure * jump <= 0.0:
            return False
    return True


def check_finite_fixture(entry: dict[str, Any], policy: dict[str, Any], fail: Failures) -> dict[str, Any]:
    fid = entry["fixture_id"]
    inputs = entry["inputs"]
    exposure = inputs["owner_exposure"]
    mu = inputs["government_current_marginal_value"]
    raw_marks = inputs["marks"]

    fail.check(
        entry["kernel_status"] == FINITE_MAINTAINED_BRANCH
        and _finite_branch_admissible(inputs),
        f"{fid}: kernel_status {entry['kernel_status']!r} disagrees with the "
        "independently re-derived finite-branch admissibility",
    )
    fail.check(
        [mark["mark_id"] for mark in raw_marks]
        == [mark["mark_id"] for mark in entry["marks"]],
        f"{fid}: mark ids or ordering differ between inputs and results",
    )

    weights: list[float] = []
    payoffs: list[float] = []
    gaps: list[float] = []
    terms_owner: list[float] = []
    terms_gov: list[float] = []
    terms_gov_owner: list[float] = []
    terms_rel: list[float] = []

    for raw, produced in zip(raw_marks, entry["marks"], strict=True):
        where = f"{fid}/{raw['mark_id']}"
        lam = raw["lambda_physical"]
        lam_star = raw["lambda_risk_neutral"]
        jump = raw["payoff_jump"]
        successor = raw["government_successor_marginal_value"]["value"]

        multiplier = 1.0 + exposure * jump
        k_world = lam_star / lam
        k_owner = 1.0 / multiplier
        k_government = successor / mu
        gamma = k_government / k_owner

        fail.close(f"{where}.owner_wealth_multiplier", produced["owner_wealth_multiplier"], multiplier, VALUE_TOLERANCE)
        fail.close(f"{where}.k_world", produced["k_world"], k_world, VALUE_TOLERANCE)
        fail.close(f"{where}.k_owner", produced["k_owner"], k_owner, VALUE_TOLERANCE)
        fail.close(f"{where}.k_government", produced["k_government"], k_government, VALUE_TOLERANCE)
        fail.close(f"{where}.gamma", produced["gamma"], gamma, VALUE_TOLERANCE)

        term_owner = lam * (k_owner - k_world) * jump
        term_gov = lam * (k_government - k_world) * jump
        term_gov_owner = lam * (k_government - k_owner) * jump
        term_rel = lam * k_owner * (gamma - 1.0) * jump
        fail.close(f"{where}.term_owner", produced["term_owner"], term_owner, VALUE_TOLERANCE)
        fail.close(f"{where}.term_government", produced["term_government"], term_gov, VALUE_TOLERANCE)
        fail.close(f"{where}.term_government_owner", produced["term_government_owner"], term_gov_owner, VALUE_TOLERANCE)
        fail.close(f"{where}.term_relative", produced["term_relative"], term_rel, VALUE_TOLERANCE)

        weights.append(lam)
        payoffs.append(jump)
        gaps.append(k_government - k_world)
        terms_owner.append(term_owner)
        terms_gov.append(term_gov)
        terms_gov_owner.append(term_gov_owner)
        terms_rel.append(term_rel)

    d_owner = math.fsum(terms_owner)
    d_government = math.fsum(terms_gov)
    d_government_owner = math.fsum(terms_gov_owner)
    d_relative = math.fsum(terms_rel)
    sums = entry["sums"]
    fail.close(f"{fid}.d_owner", sums["d_owner"], d_owner, VALUE_TOLERANCE)
    fail.close(f"{fid}.d_government", sums["d_government"], d_government, VALUE_TOLERANCE)
    fail.close(f"{fid}.d_government_owner", sums["d_government_owner"], d_government_owner, VALUE_TOLERANCE)
    fail.close(f"{fid}.d_relative", sums["d_relative"], d_relative, VALUE_TOLERANCE)

    decomposition_error = normalized_error(
        d_government, d_owner + d_government_owner, terms_owner + terms_gov + terms_gov_owner
    )
    relative_error = normalized_error(
        d_government_owner, d_relative, terms_gov_owner + terms_rel
    )
    identities = entry["identities"]
    fail.close(f"{fid}.decomposition_error", identities["decomposition_error"], decomposition_error, DISCREPANCY_TOLERANCE)
    fail.close(f"{fid}.relative_identity_error", identities["relative_identity_error"], relative_error, DISCREPANCY_TOLERANCE)
    fail.check(
        decomposition_error <= policy["production_identity_max"],
        f"{fid}: independent decomposition identity error {decomposition_error!r} exceeds "
        f"{policy['production_identity_max']!r}",
    )
    fail.check(
        relative_error <= policy["production_identity_max"],
        f"{fid}: independent relative-kernel identity error {relative_error!r} exceeds "
        f"{policy['production_identity_max']!r}",
    )

    # --- owner exposure interval and root ---------------------------------------
    root = entry["owner_root"]
    all_zero = all(jump == 0.0 for jump in payoffs)
    if all_zero:
        fail.check(
            root["status"] == ZERO_PAYOFF_UNIDENTIFIED,
            f"{fid}: an all-zero payoff vector must be {ZERO_PAYOFF_UNIDENTIFIED}, "
            f"not {root['status']!r}",
        )
        fail.check(
            root["exposure"] is None,
            f"{fid}: an unidentified owner portfolio must report no exposure",
        )
    else:
        lower, upper = exposure_interval(payoffs)
        interval = root["interval"]
        fail.check(interval is not None, f"{fid}: a nonzero payoff vector needs an interval")
        if interval is not None:
            fail.check(
                interval["lower_is_finite"] == math.isfinite(lower)
                and interval["upper_is_finite"] == math.isfinite(upper),
                f"{fid}: interval finiteness flags disagree with the independent interval",
            )
            if math.isfinite(lower):
                fail.close(f"{fid}.interval.lower", interval["lower"], lower, VALUE_TOLERANCE)
            if math.isfinite(upper):
                fail.close(f"{fid}.interval.upper", interval["upper"], upper, VALUE_TOLERANCE)
            fail.check(
                lower < 0.0 < upper and interval["zero_is_interior"] is True,
                f"{fid}: zero exposure must be interior to the admissible interval",
            )

        at_zero = owner_residual(raw_marks, 0.0)
        limit = -math.fsum(
            mark["lambda_risk_neutral"] * mark["payoff_jump"]
            for mark in raw_marks
            if mark["payoff_jump"] != 0.0
        )
        fail.close(f"{fid}.residual_at_zero_exposure", root["residual_at_zero_exposure"], at_zero, VALUE_TOLERANCE)
        fail.close(f"{fid}.limit_at_unbounded_end", root["limit_at_unbounded_end"], limit, VALUE_TOLERANCE)

        if root["status"] == UNIQUE_INTERIOR_ROOT:
            pi = root["exposure"]
            fail.check(pi is not None, f"{fid}: a unique interior root must report an exposure")
            if pi is not None:
                fail.check(
                    lower < pi < upper,
                    f"{fid}: the reported root {pi!r} is not strictly inside ({lower!r},{upper!r})",
                )
                residual = owner_residual(raw_marks, pi)
                scale = terms_owner + terms_gov + terms_gov_owner + terms_rel
                residual_error = normalized_error(residual, 0.0, scale)
                fail.check(
                    residual_error <= policy["owner_root_residual_max"],
                    f"{fid}: independent owner-root residual {residual_error!r} exceeds "
                    f"{policy['owner_root_residual_max']!r}",
                )
                derivative = -math.fsum(
                    mark["lambda_physical"] * mark["payoff_jump"] ** 2
                    / (1.0 + pi * mark["payoff_jump"]) ** 2
                    for mark in raw_marks
                )
                fail.check(
                    derivative < 0.0,
                    f"{fid}: the owner residual derivative must be strictly negative",
                )
                fail.close(f"{fid}.derivative_at_root", root["derivative_at_root"], derivative, VALUE_TOLERANCE)
                margin_floor = policy["owner_root_boundary_margin_min_factor"] * max(1.0, abs(pi))
                gaps_to_boundary = [
                    gap for gap, finite in ((pi - lower, math.isfinite(lower)), (upper - pi, math.isfinite(upper))) if finite
                ]
                if gaps_to_boundary:
                    fail.check(
                        min(gaps_to_boundary) >= margin_floor,
                        f"{fid}: the root sits {min(gaps_to_boundary)!r} from a finite wealth "
                        f"boundary, inside the required {margin_floor!r} margin",
                    )
                    fail.close(f"{fid}.boundary_margin", root["boundary_margin"], min(gaps_to_boundary), VALUE_TOLERANCE)
                else:
                    fail.check(
                        root["boundary_margin_is_unbounded"] is True,
                        f"{fid}: both endpoints are unbounded, so the boundary margin must be unbounded",
                    )
        elif root["status"] == NO_INTERIOR_ROOT_BOUNDARY_LIMIT:
            fail.check(
                root["exposure"] is None,
                f"{fid}: a boundary-only limiting root must report no finite exposure",
            )
            # A strictly decreasing residual with no interior zero must keep the
            # sign it has at zero exposure all the way to its unbounded limit.
            fail.check(
                (at_zero > 0.0 and limit >= 0.0) or (at_zero < 0.0 and limit <= 0.0),
                f"{fid}: residual at zero {at_zero!r} and limit {limit!r} straddle zero, "
                "so an interior root should have been found",
            )
        else:
            fail.check(
                False,
                f"{fid}: unexpected owner-root status {root['status']!r} for a nonzero payoff vector",
            )

    # --- projection --------------------------------------------------------------
    projection = entry["projection"]
    denominator = math.fsum(w * j * j for w, j in zip(weights, payoffs, strict=True))
    if denominator == 0.0:
        fail.check(
            projection["status"] == ZERO_PAYOFF_NORM_REFUSED,
            f"{fid}: a zero weighted payoff norm must be refused, not {projection['status']!r}",
        )
        fail.check(
            projection["alpha"] is None,
            f"{fid}: a refused projection must report no alpha",
        )
    else:
        fail.check(
            projection["status"] == PROJECTION_RESOLVED,
            f"{fid}: a nonzero weighted payoff norm should resolve, not {projection['status']!r}",
        )
        numerator = math.fsum(
            w * g * j for w, g, j in zip(weights, gaps, payoffs, strict=True)
        )
        alpha = numerator / denominator
        parallel = [alpha * j for j in payoffs]
        orthogonal = [g - p for g, p in zip(gaps, parallel, strict=True)]
        inner_terms = [
            w * o * j for w, o, j in zip(weights, orthogonal, payoffs, strict=True)
        ]
        inner = math.fsum(inner_terms)
        fail.close(f"{fid}.projection.denominator", projection["denominator"], denominator, VALUE_TOLERANCE)
        fail.close(f"{fid}.projection.numerator", projection["numerator"], numerator, VALUE_TOLERANCE)
        fail.close(f"{fid}.projection.alpha", projection["alpha"], alpha, VALUE_TOLERANCE)
        for component, g, p, o in zip(projection["components"], gaps, parallel, orthogonal, strict=True):
            where = f"{fid}.projection/{component['mark_id']}"
            fail.close(f"{where}.gap", component["gap"], g, VALUE_TOLERANCE)
            fail.close(f"{where}.parallel", component["parallel"], p, VALUE_TOLERANCE)
            fail.close(f"{where}.orthogonal", component["orthogonal"], o, VALUE_TOLERANCE)
        fail.close(f"{fid}.projection.weighted_norm_gap", projection["weighted_norm_gap"], weighted_norm(weights, gaps), VALUE_TOLERANCE)
        fail.close(f"{fid}.projection.weighted_norm_parallel", projection["weighted_norm_parallel"], weighted_norm(weights, parallel), VALUE_TOLERANCE)
        fail.close(f"{fid}.projection.weighted_norm_orthogonal", projection["weighted_norm_orthogonal"], weighted_norm(weights, orthogonal), VALUE_TOLERANCE)
        fail.close(f"{fid}.projection.weighted_inner_product_orthogonal_payoff", projection["weighted_inner_product_orthogonal_payoff"], inner, VALUE_TOLERANCE)
        orthogonality_error = normalized_error(inner, 0.0, inner_terms)
        fail.close(f"{fid}.projection.orthogonality_error", projection["orthogonality_error"], orthogonality_error, DISCREPANCY_TOLERANCE)
        fail.check(
            orthogonality_error <= policy["weighted_orthogonality_max"],
            f"{fid}: independent weighted orthogonality error {orthogonality_error!r} exceeds "
            f"{policy['weighted_orthogonality_max']!r}",
        )

    _check_safe_account(entry, payoffs, fail)

    return {
        "kernel_status": entry["kernel_status"],
        "root_status": root["status"],
        "projection_status": projection["status"],
        # Reported per-entry values: each was independently verified above, so the
        # summary maxima can now be recomputed from them exactly.
        "decomposition_error": identities["decomposition_error"],
        "relative_identity_error": identities["relative_identity_error"],
        "orthogonality_error": (
            projection["orthogonality_error"] if projection["status"] == PROJECTION_RESOLVED else None
        ),
        "root_residual": (
            abs(root["residual_at_root"])
            if root["status"] == UNIQUE_INTERIOR_ROOT and root["residual_at_root"] is not None
            else None
        ),
    }


def _check_safe_account(entry: dict[str, Any], payoffs: list[float], fail: Failures) -> None:
    fid = entry["fixture_id"]
    safe = entry["safe_account"]
    expected_rank = 1 if any(jump != 0.0 for jump in payoffs) else 0
    fail.check(
        all(value == 0.0 for value in safe["safe_payoff_vector"]),
        f"{fid}: the safe money-market account must have an identically zero marked payoff",
    )
    fail.check(
        safe["risky_payoff_vector"] == payoffs,
        f"{fid}: the reported risky payoff vector differs from the fixture inputs",
    )
    fail.check(
        safe["rank_risky"] == expected_rank
        and safe["rank_with_safe_account"] == expected_rank
        and safe["rank_increase"] == 0,
        f"{fid}: adding the safe account must not change the risky payoff rank "
        f"(expected {expected_rank})",
    )


def check_boundary_fixture(entry: dict[str, Any], fail: Failures) -> dict[str, Any]:
    fid = entry["fixture_id"]
    inputs = entry["inputs"]
    fail.check(
        entry["kernel_status"] == NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE,
        f"{fid}: a literal laissez-faire fixture must carry the non-finite fiscal "
        f"kernel status, not {entry['kernel_status']!r}",
    )
    fail.check(
        inputs["worker_consumption"] == 0.0,
        f"{fid}: literal laissez-faire declares zero worker consumption",
    )
    fail.check(
        entry["worker_consumption"] == {"kind": "finite", "value": 0.0},
        f"{fid}: worker consumption must be serialized as a tagged finite zero",
    )
    for raw, produced in zip(inputs["marks"], entry["boundary_marks"], strict=True):
        where = f"{fid}/{raw['mark_id']}"
        fail.check(
            raw["government_successor_marginal_value"] == {"kind": "positive_infinity", "value": None},
            f"{where}: the successor marginal value must be a tagged positive infinity "
            "with no numeric sentinel",
        )
        fail.check(
            produced["k_government"] == {"kind": "positive_infinity", "value": None},
            f"{where}: the government jump kernel must be a tagged positive infinity",
        )
        fail.check(
            produced["gamma"]["kind"] in ("positive_infinity", "undefined"),
            f"{where}: the relative jump kernel must be positive infinity or explicitly undefined",
        )
        fail.check(
            produced["k_owner"]["kind"] in ("finite", "undefined"),
            f"{where}: the owner kernel must be finite or explicitly undefined",
        )
    fail.check(
        entry["sums"] is None
        and entry["identities"] is None
        and entry["owner_root"] is None
        and entry["projection"] is None,
        f"{fid}: no finite residual arithmetic may be reported at the boundary",
    )
    _check_safe_account(
        entry, [mark["payoff_jump"] for mark in inputs["marks"]], fail
    )
    return {
        "kernel_status": entry["kernel_status"],
        "root_status": None,
        "projection_status": None,
        "decomposition_error": None,
        "relative_identity_error": None,
        "orthogonality_error": None,
        "root_residual": None,
    }


def check_report(payload: dict[str, Any]) -> Failures:
    fail = Failures()
    fail.check(payload.get("schema") == SCHEMA, f"unknown report schema {payload.get('schema')!r}")
    fail.check(
        payload.get("result_use") == "exploratory_only",
        f"result_use must remain exploratory_only, not {payload.get('result_use')!r}",
    )
    specification = payload.get("specification", {})
    fail.check(
        specification.get("specification_id") == "CS012"
        and specification.get("version") == "0.1"
        and specification.get("sha256")
        == "275cf384a6aa8f12831bd0e7b8b8ea4291e49402f3578a9c301baf91fe2930e8",
        "the report does not name CS012 v0.1 with its exact SHA-256",
    )
    policy = payload["tolerance_policy"]

    rebuilt = []
    for entry in payload["fixtures"]:
        if entry["declared_branch"] == BRANCH_LITERAL_LAISSEZ_FAIRE:
            rebuilt.append(check_boundary_fixture(entry, fail))
        else:
            rebuilt.append(check_finite_fixture(entry, policy, fail))

    summary = payload["summary"]
    fail.check(
        summary["fixture_count"] == len(payload["fixtures"]),
        "the reported fixture count disagrees with the number of fixture entries",
    )

    def counts(key: str) -> dict[str, int]:
        tally: dict[str, int] = {}
        for item in rebuilt:
            status = item[key]
            if status is not None:
                tally[status] = tally.get(status, 0) + 1
        return tally

    fail.check(
        summary["kernel_status_counts"] == counts("kernel_status"),
        f"kernel status counts differ: report {summary['kernel_status_counts']} vs "
        f"independent {counts('kernel_status')}",
    )
    fail.check(
        summary["owner_root_status_counts"] == counts("root_status"),
        f"owner-root status counts differ: report {summary['owner_root_status_counts']} vs "
        f"independent {counts('root_status')}",
    )
    fail.check(
        summary["projection_status_counts"] == counts("projection_status"),
        f"projection status counts differ: report {summary['projection_status_counts']} vs "
        f"independent {counts('projection_status')}",
    )

    refusals = summary["refusal_counts"]
    kernel_counts = counts("kernel_status")
    root_counts = counts("root_status")
    projection_counts = counts("projection_status")
    fail.check(
        refusals["kernel_non_finite_branch"]
        == len(payload["fixtures"]) - kernel_counts.get(FINITE_MAINTAINED_BRANCH, 0),
        "the non-finite kernel refusal count disagrees with the independent recount",
    )
    fail.check(
        refusals["owner_root_unidentified_or_boundary"]
        == sum(v for k, v in root_counts.items() if k != UNIQUE_INTERIOR_ROOT),
        "the owner-root refusal count disagrees with the independent recount",
    )
    fail.check(
        refusals["projection_refused"]
        == sum(v for k, v in projection_counts.items() if k != PROJECTION_RESOLVED),
        "the projection refusal count disagrees with the independent recount",
    )

    def maximum(key: str) -> float:
        values = [item[key] for item in rebuilt if item[key] is not None]
        return max(values) if values else 0.0

    # Each per-entry value above was independently reconstructed, so the summary
    # maxima must be exactly the maximum over those verified values -- an absolute
    # tolerance here would hide a summary that understates a near-zero maximum.
    for summary_key, rebuilt_key in (
        ("max_decomposition_error", "decomposition_error"),
        ("max_relative_identity_error", "relative_identity_error"),
        ("max_owner_root_residual", "root_residual"),
        ("max_orthogonality_error", "orthogonality_error"),
    ):
        recomputed = maximum(rebuilt_key)
        fail.check(
            summary[summary_key] == recomputed,
            f"summary.{summary_key}: report {summary[summary_key]!r} is not the maximum "
            f"over the independently verified per-fixture values ({recomputed!r})",
        )

    fail.check(
        summary["max_production_versus_independent_error"]
        <= policy["production_versus_independent_max"],
        "the reported production-versus-independent maximum exceeds its declared tolerance",
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
    summary = payload["summary"]
    print("OK: independent reconstruction agrees with the report")
    print(f"  fixtures                      {summary['fixture_count']}")
    print(f"  kernel statuses               {summary['kernel_status_counts']}")
    print(f"  owner-root statuses           {summary['owner_root_status_counts']}")
    print(f"  projection statuses           {summary['projection_status_counts']}")
    print(f"  refusal counts                {summary['refusal_counts']}")
    print(f"  max decomposition error       {summary['max_decomposition_error']!r}")
    print(f"  max relative-identity error   {summary['max_relative_identity_error']!r}")
    print(f"  max owner-root residual       {summary['max_owner_root_residual']!r}")
    print(f"  max orthogonality error       {summary['max_orthogonality_error']!r}")
    print(f"  max production-vs-independent {summary['max_production_versus_independent_error']!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
