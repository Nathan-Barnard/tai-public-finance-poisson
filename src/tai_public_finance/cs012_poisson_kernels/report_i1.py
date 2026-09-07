"""Generate the immutable CS012 I1 owner-side report.

    uv run python -m tai_public_finance.cs012_poisson_kernels.report_i1 \
        --synthetic-config configs/cs012/P-CS012-SYN-01.json \
        --economic-config  configs/cs012/P-CS012-ECO-01.json \
        --output-dir outputs/cs012-i1-...

Writes ``identity_report.json`` and ``summary.md`` into a new directory and refuses to
touch an existing one. Result use is ``exploratory_only`` and the block produces no
government kernel, prefunding path, time path, portfolio direction, welfare number,
equilibrium claim, or optimal policy.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ak_partial_ramsey.tolerances import SolverTolerances

from .extended import sha256_of_bytes, sha256_of_object
from .i1_owner_branch import (
    OwnerBranchError,
    build_payoffs,
    owner_branch_payload,
    solve_owner_branch,
)
from .i1_packets import (
    EconomicPacket,
    SyntheticPacket,
    load_economic_packet,
    load_synthetic_packet,
)
from .i1_successors import (
    MARK_F,
    MARK_ORDER,
    MARK_P,
    ak_root_report,
    dependency_provenance,
    model_parameters,
    partial_manifold_report,
    solve_successors,
    synthetic_fixture_provenance,
)
from .report import SPECIFICATION, git_provenance
from .statuses import RESULT_USE

SCHEMA = "cs012-i1-owner-branch-report/1"

TOLERANCE_POLICY = {
    "normalized_error": "abs(lhs-rhs)/max(1, sum(abs(term)))",
    "owner_root_residual_max": 1.0e-10,
    "production_versus_independent_max": 1.0e-10,
    "min_abs_payoff": 1.0e-3,
}

DEVIATION_01 = {
    "id": "DEV-01",
    "standard_path_varied": (
        "CS012 v0.1 states that I1 waits for the complete I1-I3 parameter packet. This "
        "run executes I1 before the public-prefunding sequence, continuation horizon, "
        "terminal condition, and government-kernel thresholds are frozen."
    ),
    "reason": (
        "None of those objects enters the I1 successor or owner-side calculation. The "
        "owner residual depends only on the physical and risk-neutral intensities, the "
        "marked payoff jumps, and owner wealth; the successors depend only on the "
        "technology, installation, and world-rate primitives."
    ),
    "compensating_restriction": (
        "No government kernel, time path, portfolio direction, welfare, equilibrium, or "
        "optimal-policy result is produced. Government fields are absent by "
        "construction, not merely unreported."
    ),
    "result_use_ceiling": "exploratory_only",
    "owner": "Nathan",
    "independent_reviewer": "Codex",
    "expiry": "before any I2 implementation or result run",
}


@dataclass(frozen=True, slots=True)
class RowFlags:
    """Per-row validity, branch, interpolation, and reliable-domain flags."""

    valid: bool
    quarantined: bool
    branch: str
    inside_certified_domain: bool
    interpolated: bool
    reliable_domain: bool
    note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "quarantined": self.quarantined,
            "branch": self.branch,
            "inside_certified_domain": self.inside_certified_domain,
            "interpolated": self.interpolated,
            "reliable_domain": self.reliable_domain,
            "note": self.note,
        }


def _economic_scenario(
    packet: EconomicPacket, tolerances: SolverTolerances
) -> dict[str, Any]:
    params = model_parameters(packet)
    services = solve_successors(
        params,
        packet.ak_root_interval,
        packet.partial_capital_interval,
        tolerances,
    )
    q_0 = packet.q_0
    intensities = {
        MARK_P: (packet.lambda_P, packet.lambda_P_star),
        MARK_F: (packet.lambda_F, packet.lambda_F_star),
    }

    def branch_at(K: float, label: str, enforce_floor: bool = True):
        prices = ((MARK_P, services.q_P(K)), (MARK_F, services.q_F()))
        payoffs = build_payoffs(q_0, prices, intensities)
        return payoffs, solve_owner_branch(
            label, K, q_0, payoffs, packet.a_0, enforce_payoff_floor=enforce_floor
        )

    # --- baseline, at the declared K_0. A failure here stops the run. --------------
    _, baseline = branch_at(packet.baseline_capital, "baseline_K0")

    # --- diagnostic capital grid. A single failing row is quarantined, not aggregated.
    rows: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    lo, hi = services.certified_domain
    for K in packet.diagnostic_capital_grid:
        inside = lo <= K <= hi
        is_baseline = K == packet.baseline_capital
        try:
            if not inside:
                raise OwnerBranchError(
                    f"K = {K!r} lies outside the certified partial domain [{lo!r},{hi!r}]"
                )
            _, branch = branch_at(K, f"grid_K={K}")
        except (OwnerBranchError, Exception) as failure:  # noqa: BLE001 - recorded, not swallowed
            flags = RowFlags(
                valid=False,
                quarantined=True,
                branch=services.ak.branch,
                inside_certified_domain=inside,
                interpolated=inside,
                reliable_domain=False,
                note=f"{type(failure).__name__}: {failure}",
            )
            row = {
                "capital": K,
                "is_baseline": is_baseline,
                "flags": flags.as_dict(),
                "owner": None,
            }
            rows.append(row)
            quarantined.append({"capital": K, "reason": flags.note})
            continue
        flags = RowFlags(
            valid=True,
            quarantined=False,
            branch=services.ak.branch,
            inside_certified_domain=True,
            # q_P and H_P come from shape-preserving interpolants over the certified
            # domain; q_F is the exact selected AK root and is not interpolated.
            interpolated=True,
            reliable_domain=True,
            note="inside the certified partial-successor domain",
        )
        rows.append(
            {
                "capital": K,
                "is_baseline": is_baseline,
                "q_P": services.q_P(K),
                "q_P_derivative": services.q_P_derivative(K),
                "q_F": services.q_F(),
                "J_P": branch.marks[0].payoff_jump,
                "J_F": branch.marks[1].payoff_jump,
                "exposure": branch.exposure,
                "wealth_multiplier_P": branch.marks[0].wealth_multiplier,
                "wealth_multiplier_F": branch.marks[1].wealth_multiplier,
                "k_world_P": branch.marks[0].k_world,
                "k_world_F": branch.marks[1].k_world,
                "k_owner_P": branch.marks[0].k_owner,
                "k_owner_F": branch.marks[1].k_owner,
                "d_owner": branch.d_owner,
                "residual_at_root": branch.residual_at_root,
                "lower_boundary_distance": (
                    branch.lower_boundary_distance
                    if branch.interval.lower_is_finite
                    else None
                ),
                "upper_boundary_distance": (
                    branch.upper_boundary_distance
                    if branch.interval.upper_is_finite
                    else None
                ),
                "payoff_signs": {
                    m.mark_id: ("positive" if m.payoff_jump > 0 else "negative")
                    for m in branch.marks
                },
                "flags": flags.as_dict(),
                "owner": owner_branch_payload(branch),
            }
        )

    valid_rows = [r for r in rows if r["flags"]["valid"]]
    return {
        "packet": {
            "packet_id": packet.packet_id,
            "packet_kind": packet.packet_kind,
            "time_unit": packet.time_unit,
            "value_unit": packet.value_unit,
            "fingerprint": packet.fingerprint,
            "direct_fields": packet.direct_fields(),
            "provenance": packet.provenance,
            "limits": packet.limits,
        },
        "q_0": q_0,
        "ak_successor": ak_root_report(services),
        "partial_successor": partial_manifold_report(services),
        "baseline": owner_branch_payload(baseline),
        "diagnostic_grid": rows,
        "quarantined_rows": quarantined,
        "maxima": {
            "max_owner_root_residual": max(
                (abs(r["residual_at_root"]) for r in valid_rows), default=0.0
            ),
            "max_independent_exposure_residual": max(
                (r["owner"]["independent"]["exposure_residual_normalized"] for r in valid_rows),
                default=0.0,
            ),
            "max_independent_kernel_error": max(
                (r["owner"]["independent"]["kernel_max_absolute_error"] for r in valid_rows),
                default=0.0,
            ),
            "max_independent_d_owner_error": max(
                (r["owner"]["independent"]["d_owner_normalized_error"] for r in valid_rows),
                default=0.0,
            ),
        },
        "counts": {
            "grid_rows": len(rows),
            "valid_rows": len(valid_rows),
            "quarantined_rows": len(quarantined),
            "ak_roots_enumerated": len(services.ak.candidates),
            "ak_roots_accepted": sum(1 for c in services.ak.candidates if c.accepted),
        },
        "government_objects_present": False,
    }


def _synthetic_regressions(
    packet: SyntheticPacket, tolerances: SolverTolerances
) -> dict[str, Any]:
    """Run the pinned dependency's own fixtures as regressions of the pinned commit."""
    from ak_partial_ramsey.fixtures import get_fixture
    from ak_partial_ramsey.params import AkRootInterval, PartialCapitalInterval
    from ak_partial_ramsey.successors.ak import solve_ak_successor
    from ak_partial_ramsey.successors.partial import solve_partial_successor

    results: list[dict[str, Any]] = []
    for name in packet.regression_fixtures:
        fixture = get_fixture(name)
        entry: dict[str, Any] = {
            "fixture": synthetic_fixture_provenance(name),
            "is_primary": name == packet.primary_fixture,
        }
        interval = fixture.partial_capital_interval
        # A fixture that declares no partial capital window exercises the AK block
        # alone; that is a property of the fixture, not a failure to solve.
        entry["scope"] = "ak_and_partial" if interval is not None else "ak_only"
        try:
            ak = solve_ak_successor(
                fixture.params,
                AkRootInterval(
                    q_lo=fixture.ak_root_interval.q_lo, q_hi=fixture.ak_root_interval.q_hi
                ),
                tolerances,
            )
            partial = None
            if interval is not None:
                partial = solve_partial_successor(
                    fixture.params,
                    PartialCapitalInterval(K_lo=interval.K_lo, K_hi=interval.K_hi),
                    tolerances,
                )
        except Exception as failure:  # noqa: BLE001 - reported as a regression outcome
            entry["status"] = "refused"
            entry["detail"] = f"{type(failure).__name__}: {failure}"
            results.append(entry)
            continue
        entry["status"] = "reproduced"
        entry["ak"] = {
            "selected_q_F": ak.q_F,
            "selected_branch": ak.branch,
            "tvc_margin": ak.tvc_margin,
            "n_roots_enumerated": len(ak.candidates),
            "n_accepted": sum(1 for c in ak.candidates if c.accepted),
            "candidates": [
                {"q": c.q, "branch": c.branch, "accepted": c.accepted, "reason": c.reason}
                for c in ak.candidates
            ],
        }
        entry["partial"] = (
            None
            if partial is None
            else {
                "certified_domain": list(partial.certified_domain),
                "K_P_star": partial.point.K_star,
                "max_ivp_bvp_difference": partial.diagnostics.get("max_ivp_bvp_difference"),
                "wealth_route_max_gap": partial.diagnostics.get("wealth_route_max_gap"),
            }
        )
        results.append(entry)
    return {
        "packet": {
            "packet_id": packet.packet_id,
            "packet_kind": packet.packet_kind,
            "fingerprint": packet.fingerprint,
            "direct_fields": packet.direct_fields(),
            "provenance": packet.provenance,
            "limits": packet.limits,
        },
        "regressions": results,
        "counts": {
            "fixtures_run": len(results),
            "reproduced": sum(1 for r in results if r["status"] == "reproduced"),
            "refused": sum(1 for r in results if r["status"] == "refused"),
        },
    }


def build_i1_report(
    synthetic_path: Path,
    economic_path: Path,
    provenance: Any,
    machine_runtime_seconds: float,
) -> dict[str, Any]:
    tolerances = SolverTolerances()
    synthetic = load_synthetic_packet(synthetic_path)
    economic = load_economic_packet(economic_path)
    dependency = dependency_provenance()
    if dependency["resolved"].get("commit_id") != synthetic.dependency_commit:
        raise RuntimeError(
            "the installed CS011 dependency commit "
            f"{dependency['resolved'].get('commit_id')!r} does not match the packet's "
            f"pinned {synthetic.dependency_commit!r}"
        )
    repository = Path(__file__).resolve().parents[3]
    return {
        "schema": SCHEMA,
        "block": "I1",
        "specification": SPECIFICATION,
        "tolerance_policy": TOLERANCE_POLICY,
        "result_use": RESULT_USE,
        "deviations": [DEVIATION_01],
        "interpretation_limits": [
            "owner-side pricing objects only: successor prices, marked payoff jumps, "
            "world and owner kernels, owner exposure, and the owner residual D_K",
            "no government kernel, fiscal marginal value, prefunding path, time path, "
            "public-portfolio direction, welfare number, equilibrium claim, or optimal policy",
            "the economic packet is provisional and illustrative, not an estimate or a "
            "country calibration",
            "the inherited state is a named provisional state, not a solved pre-arrival "
            "equilibrium",
            "the diagnostic capital grid is sensitivity only; K_0 remains the baseline",
            "CS012 v0.1 is a draft and is neither review-ready nor approved",
        ],
        "provenance": {
            "repository_url": provenance.repository_url,
            "code_commit": provenance.code_commit,
            "branch": provenance.branch,
            "clean_start": provenance.clean_start,
            "python_version": provenance.python_version,
            "scipy_version": provenance.scipy_version,
            "numpy_version": provenance.numpy_version,
            "platform": provenance.platform,
            "machine": provenance.machine,
            "dependency_lock_path": "uv.lock",
            "dependency_lock_sha256": sha256_of_bytes(
                (repository / "uv.lock").read_bytes()
            ),
            "cs011_dependency": dependency,
        },
        "configs": {
            "synthetic": {
                "path": str(synthetic_path),
                "sha256": sha256_of_bytes(synthetic_path.read_bytes()),
            },
            "economic": {
                "path": str(economic_path),
                "sha256": sha256_of_bytes(economic_path.read_bytes()),
            },
        },
        "synthetic": _synthetic_regressions(synthetic, tolerances),
        "economic": _economic_scenario(economic, tolerances),
        "machine_runtime_seconds": machine_runtime_seconds,
    }


def _summary_markdown(payload: dict[str, Any]) -> str:
    eco = payload["economic"]
    base = eco["baseline"]
    marks = {m["mark_id"]: m for m in base["marks"]}
    P, F = marks["P"], marks["F"]
    ak = eco["ak_successor"]
    interval = base["exposure_interval"]

    def endpoint(value: float | None, unbounded_text: str) -> str:
        """Render an interval endpoint. An unbounded side has no number to print."""
        return unbounded_text if value is None else f"{value:.9f}"

    interval_text = (
        f"({endpoint(interval['lower'], '-inf')}, {endpoint(interval['upper'], '+inf')})"
    )
    direction = "short" if base["exposure"] < 0.0 else "long"
    sign_note = (
        "the two marks move installed-equity value in *opposite* directions here"
        if P["payoff_jump"] * F["payoff_jump"] < 0.0
        else "both marks raise installed-equity value here"
    )
    return f"""# CS012 I1 — laissez-faire owner branch under {eco["packet"]["packet_id"]}

**Result use: `exploratory_only`. Not an equilibrium, not a welfare result, not a
government portfolio.** CS012 v0.1 is a draft; this run neither promotes it nor makes it
review-ready.

## What was computed

At the named provisional pre-arrival state (`K_0 = {base["capital"]}`, `q_0 =
{base["q_0"]:.10f}`, owner wealth `a_0 = {P["owner_wealth_before"]}`), with two labelled
automation marks:

| | partial `P` | full-AK `F` |
|---|---:|---:|
| successor price `q_j` | {eco["diagnostic_grid"][1]["q_P"]:.10f} | {ak["selected_q_F"]:.10f} |
| payoff jump `J_j = q_j/q_0 − 1` | {P["payoff_jump"]:+.11f} | {F["payoff_jump"]:+.11f} |
| physical intensity `λ_j` | {P["lambda_physical"]} | {F["lambda_physical"]} |
| risk-neutral intensity `λ*_j` | {P["lambda_risk_neutral"]} | {F["lambda_risk_neutral"]} |
| world kernel `k^w_j = λ*_j/λ_j` | {P["k_world"]:.10f} | {F["k_world"]:.10f} |
| owner wealth multiplier `X^K_j` | {P["wealth_multiplier"]:.10f} | {F["wealth_multiplier"]:.10f} |
| owner kernel `k^K_j = 1/X^K_j` | {P["k_owner"]:.10f} | {F["k_owner"]:.10f} |
| owner wealth after `a_0 X^K_j` | {P["owner_wealth_after"]:.10f} | {F["owner_wealth_after"]:.10f} |
| contribution to `D_K` | {P["d_owner_contribution"]:+.6e} | {F["d_owner_contribution"]:+.6e} |

Owner exposure `π = {base["exposure"]:.9f}`, solving the unmultiplied
`D_K(π) = Σ_j λ_j (1/(1+πJ_j) − λ*_j/λ_j) J_j = 0` on the open positive-wealth interval
`{interval_text}`,
with residual `{base["residual_at_root"]:+.3e}` and a strictly negative slope
`{base["derivative_at_root"]:.6e}`.

## Economic content

The world prices the full-AK mark far more heavily than its physical frequency warrants
(`k^w_F = {F["k_world"]:.4f}` against `k^w_P = {P["k_world"]:.4f}`): the risk-neutral law is
tilted toward the mark the domestic owner least wants. Given that, and given that
{sign_note}, the owner's optimal exposure is a **{direction}** position of
`{base["exposure"]:.6f}` times wealth. Owner wealth moves to
`{P["wealth_multiplier"]:.4f}` times its pre-arrival level on a partial arrival and
`{F["wealth_multiplier"]:.4f}` times it on a full-AK arrival.

That asymmetry is the whole point of the block: it is the owner-side input the government
comparison will later be made against. It says nothing yet about what a government would
want, because no government object exists at I1.

## Limits

{chr(10).join("- " + line for line in payload["interpretation_limits"])}

The public installed-equity, safe-asset, and safe-debt positions are all zero here. That
is the I1 owner-side state only and must never be used to form a finite government
kernel; the strictly positive prefunding family is frozen separately before I2.

## Deviation

`DEV-01` — I1 executed before the public-prefunding sequence, continuation horizon,
terminal condition, and government-kernel thresholds are frozen. None enters this
calculation. Owner: Nathan. Independent reviewer: Codex. Expires before any I2
implementation or result run.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the CS012 I1 owner-branch report.")
    parser.add_argument("--synthetic-config", required=True)
    parser.add_argument("--economic-config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)

    repository = Path(__file__).resolve().parents[3]
    provenance = git_provenance(repository)
    if not provenance.clean_start and not args.allow_dirty:
        print(
            "refused: the working tree is dirty. Evidence is generated from a clean "
            "implementation commit; pass --allow-dirty only for scratch runs.",
            file=sys.stderr,
        )
        return 2

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        print(
            f"refused: {output_dir} already exists; immutable outputs are never "
            "overwritten. Reproduce into a scratch path and compare hashes.",
            file=sys.stderr,
        )
        return 2

    started = time.perf_counter()
    payload = build_i1_report(
        Path(args.synthetic_config).resolve(),
        Path(args.economic_config).resolve(),
        provenance,
        0.0,
    )
    payload["machine_runtime_seconds"] = time.perf_counter() - started

    output_dir.mkdir(parents=True)
    report_path = output_dir / "identity_report.json"
    # allow_nan=False makes a non-standard Infinity/NaN token a hard failure rather
    # than an unparseable artefact.
    report_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    summary_path = output_dir / "summary.md"
    summary_path.write_text(_summary_markdown(payload), encoding="utf-8")

    print(f"wrote {report_path}")
    print(f"report sha256 {sha256_of_bytes(report_path.read_bytes())}")
    print(f"report bytes {report_path.stat().st_size}")
    print(f"wrote {summary_path}")
    print(f"summary sha256 {sha256_of_bytes(summary_path.read_bytes())}")
    print(f"dependency commit {payload['provenance']['cs011_dependency']['resolved']['commit_id']}")
    print(f"economic fingerprint {payload['economic']['packet']['fingerprint']}")
    print(f"synthetic fingerprint {payload['synthetic']['packet']['fingerprint']}")
    print(f"result_use {payload['result_use']}")
    eco = payload["economic"]
    print(
        json.dumps(
            {"counts": eco["counts"], "maxima": eco["maxima"],
             "quarantined": eco["quarantined_rows"]},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
