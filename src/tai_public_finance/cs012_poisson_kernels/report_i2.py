"""Generate the immutable CS012 I2a successor-boundary and prefunding report.

    uv run python -m tai_public_finance.cs012_poisson_kernels.report_i2 \
        --economic-config   configs/cs012/P-CS012-ECO-02.json \
        --prefunding-config configs/cs012/P-CS012-PREFUND-01.json \
        --analytic-config   configs/cs012/P-CS012-SYN-02.json \
        --output-dir outputs/cs012-i2a-successor-prefunding-eco02

The block is I2a: the successor side of I2. Whether normalized government kernels are
reported at all is decided by the pre-event ``mu_e`` closure audit, not by a flag.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from .extended import sha256_of_bytes
from .i1_packets import load_economic_packet
from .i1_successors import dependency_provenance, model_parameters, solve_successors
from .i2_packets import (
    SYN01_QUARANTINE,
    load_analytic_fixture,
    load_prefunding_packet,
)
from .i2_prefunding import (
    adjacent_log_log_elasticities,
    audit_mu_e_closure,
    literal_boundary,
    safe_position_tvc,
    unrestricted_upper_relaxation_row,
)
from .report import SPECIFICATION, git_provenance
from .statuses import RESULT_USE

SCHEMA = "cs012-i2a-successor-prefunding-report/1"

TOLERANCE_POLICY = {
    "full_ak_level_max_relative_error": 1.0e-12,
    "full_ak_elasticity_max_absolute_error": 1.0e-12,
    "H_P_route_max_absolute_gap": 1.0e-8,
    "syn02_identity_max_absolute_residual": 1.0e-12,
}

INTERPRETATION_LIMITS = [
    "successor-side boundary and prefunding evidence only",
    "a successor marginal value V_{j,e} is NOT a government kernel and is never relabelled as one",
    "no normalized government kernel k^G, no relative kernel gamma, no portfolio direction",
    "no welfare statement, no equilibrium claim, no optimal policy, no dynamic Ramsey solve",
    "the prefunding rows are different inherited public-wealth continuations, not free "
    "endowments and not a common-(S_0,M_0) welfare comparison",
    "the economic packet is provisional and illustrative, not an estimate or a country calibration",
    "P-CS012-SYN-01 is quarantined; its 'stationary-compatible' label was false",
    "CS012 v0.1 is a draft and is neither review-ready nor approved",
]


def _partial_wage_floor(services: Any, K: float) -> float:
    """The partial successor's wage at the reference capital.

    Strictly positive, which is exactly why the partial unrestricted-annuity rows below
    are an upper relaxation rather than a constrained successor value.
    """
    from ak_partial_ramsey.primitives import task_wage

    return task_wage(K, services.params.partial_technology)


def _syn02_section(fixture) -> dict[str, Any]:
    """SYN-02's analytic identities, each recomputed from its primitives."""
    rho, F_seq = fixture.rho, tuple(fixture.prefunding_ratios)
    consumption = tuple(rho * F for F in F_seq)
    marginal = tuple(1.0 / (rho * F) for F in F_seq)
    return {
        "packet_id": fixture.packet_id,
        "packet_kind": fixture.packet_kind,
        "fixture_scope": fixture.fixture_scope,
        "construction": "direct",
        "fingerprint": fixture.fingerprint,
        "direct_fields": fixture.direct_fields(),
        "derived": {
            "r_F_bar": fixture.r_F_bar,
            "q_F": fixture.q_F,
            "A_bar": fixture.A_bar,
            "implied_growth_from_price": fixture.implied_growth,
        },
        "analytic_checks": {
            "zero_tax_user_cost_residual": fixture.user_cost_residual(),
            "growth_recovery_residual": fixture.implied_growth - fixture.target_growth,
            "stationary_compatibility_residual": fixture.stationary_residual,
            "productive_tvc_margin": fixture.tvc_margin,
        },
        "rows": [
            {
                "prefunding_level_F": F,
                "worker_consumption_C_W": C,
                "successor_marginal_value_V_e": V,
                "consumption_identity_residual": C - rho * F,
                "marginal_value_identity_residual": V - 1.0 / (rho * F),
            }
            for F, C, V in zip(F_seq, consumption, marginal, strict=True)
        ],
        "elasticities": list(adjacent_log_log_elasticities(F_seq, marginal)),
        "safe_position_tvc": safe_position_tvc(rho, fixture.r_F_bar),
        "literal_boundary": literal_boundary(rho, 0.0).as_dict(),
        "provenance": fixture.provenance,
        "limits": fixture.limits,
    }


def build_i2_report(
    economic_path: Path,
    prefunding_path: Path,
    analytic_path: Path,
    provenance: Any,
    machine_runtime_seconds: float,
) -> dict[str, Any]:
    economic = load_economic_packet(economic_path)
    prefunding = load_prefunding_packet(prefunding_path)
    analytic = load_analytic_fixture(analytic_path)

    if prefunding.bound_packet_id != economic.packet_id:
        raise RuntimeError(
            f"the prefunding packet is bound to {prefunding.bound_packet_id!r} but "
            f"{economic.packet_id!r} was supplied"
        )
    if prefunding.bound_packet_fingerprint != economic.fingerprint:
        raise RuntimeError(
            "the prefunding packet's bound fingerprint does not match the supplied "
            f"economic packet: {prefunding.bound_packet_fingerprint!r} vs "
            f"{economic.fingerprint!r}"
        )

    audit = audit_mu_e_closure()

    services = solve_successors(
        model_parameters(economic),
        economic.ak_root_interval,
        economic.partial_capital_interval,
    )
    K = prefunding.baseline_capital
    rho = economic.rho
    q_P = services.q_P(K)
    q_F = services.q_F()
    H_P_quadrature = services.partial.H_P(K)
    H_P_algebraic = services.partial.H_P_algebraic(K)
    # Full AK: productive human wealth exactly offsets installed-capital value, so the
    # residual is zero by construction rather than by cancellation of two big numbers.
    H_F = q_F * K

    partial_residual = H_P_quadrature - q_P * K

    levels = prefunding.levels()
    # The partial rows are an UPPER RELAXATION at ECO-02: the wage floor is strictly
    # positive and r_P < rho, so the unrestricted annuity is not transfer-feasible.
    # They are labelled as such here and superseded by the I2b constrained solver.
    partial_rows = [
        unrestricted_upper_relaxation_row(
            "P", F, rho, H_P_quadrature, q_P * K, wage_floor=_partial_wage_floor(services, K)
        )
        for F in levels
    ]
    full_rows = [
        unrestricted_upper_relaxation_row("F", F, rho, H_F, q_F * K, wage_floor=0.0)
        for F in levels
    ]

    partial_values = tuple(r.successor_marginal_value for r in partial_rows)
    full_values = tuple(r.successor_marginal_value for r in full_rows)
    partial_elasticities = adjacent_log_log_elasticities(levels, partial_values)
    full_elasticities = adjacent_log_log_elasticities(levels, full_values)

    full_level_errors = [
        max(
            abs(r.worker_consumption - rho * r.prefunding_level)
            / max(1.0, abs(rho * r.prefunding_level)),
            abs(r.successor_marginal_value - 1.0 / (rho * r.prefunding_level))
            / max(1.0, abs(1.0 / (rho * r.prefunding_level))),
        )
        for r in full_rows
    ]

    return {
        "schema": SCHEMA,
        "block": "I2a",
        "block_scope": (
            "successor boundary and positive prefunding; normalized government kernels "
            "are gated on the pre-event mu_e closure audit"
        ),
        "specification": SPECIFICATION,
        "tolerance_policy": TOLERANCE_POLICY,
        "result_use": RESULT_USE,
        "interpretation_limits": INTERPRETATION_LIMITS,
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
                (Path(__file__).resolve().parents[3] / "uv.lock").read_bytes()
            ),
            "cs011_dependency": dependency_provenance(),
        },
        "configs": {
            "economic": {
                "path": str(economic_path),
                "sha256": sha256_of_bytes(economic_path.read_bytes()),
                "packet_id": economic.packet_id,
                "fingerprint": economic.fingerprint,
            },
            "prefunding": {
                "path": str(prefunding_path),
                "sha256": sha256_of_bytes(prefunding_path.read_bytes()),
                "packet_id": prefunding.packet_id,
                "fingerprint": prefunding.fingerprint,
            },
            "analytic": {
                "path": str(analytic_path),
                "sha256": sha256_of_bytes(analytic_path.read_bytes()),
                "packet_id": analytic.packet_id,
                "fingerprint": analytic.fingerprint,
            },
        },
        "syn01_quarantine": SYN01_QUARANTINE,
        "closure_audit": audit.as_dict(),
        "government_kernels": {
            "reported": False,
            "reason": audit.status,
            "k_government": None,
            "gamma": None,
            "note": (
                "Not computed and not approximated. k^G_j = V_{j,e}/mu_e requires the "
                "pre-event optimized government marginal value, which the closure audit "
                "did not find at the pinned commits. The successor marginal values below "
                "are numerators only."
            ),
        },
        "economic_scenario": {
            "packet_id": economic.packet_id,
            "packet_fingerprint": economic.fingerprint,
            "baseline_capital": K,
            "rho": rho,
            "r_F_bar": economic.r_F_bar,
            "r_P_bar": economic.r_P_bar,
            "prices": {"q_0": economic.q_0, "q_P": q_P, "q_F": q_F},
            "productive_wealth": {
                "H_P_quadrature": H_P_quadrature,
                "H_P_algebraic": H_P_algebraic,
                "H_P_route_gap": abs(H_P_quadrature - H_P_algebraic),
                "H_P_minus_qP_K": partial_residual,
                "H_F_equals_qF_K": H_F,
                "full_ak_residual_wealth": 0.0,
                "note": (
                    "On the full-AK branch productive human wealth exactly offsets "
                    "installed-capital value, so X_F = F identically. The partial branch "
                    "keeps a strictly positive residual at this baseline."
                ),
            },
            "balance_sheet_convention": {
                "public_installed_equity_Theta": prefunding.public_installed_equity,
                "source_tax_tau": prefunding.source_tax,
                "safe_debt_B_examples": {
                    str(F): prefunding.safe_debt(F) for F in levels
                },
            },
            "prefunding_levels": list(levels),
            "partial_rows": [r.as_dict() for r in partial_rows],
            "full_rows": [r.as_dict() for r in full_rows],
            "elasticities": {
                "partial": list(partial_elasticities),
                "full_ak": list(full_elasticities),
                "full_ak_expected": -1.0,
                "partial_limit_expected": "approaches zero, not minus one",
            },
            "safe_position_tvc": safe_position_tvc(rho, economic.r_F_bar),
            "literal_boundary": literal_boundary(rho, partial_residual).as_dict(),
            "maxima": {
                "max_full_ak_level_relative_error": max(full_level_errors),
                "max_full_ak_elasticity_absolute_error": max(
                    abs(e + 1.0) for e in full_elasticities
                ),
                "H_P_route_gap": abs(H_P_quadrature - H_P_algebraic),
                "max_partial_elasticity_magnitude": max(
                    abs(e) for e in partial_elasticities
                ),
            },
        },
        "syn02": _syn02_section(analytic),
        "machine_runtime_seconds": machine_runtime_seconds,
    }


def _summary_markdown(payload: dict[str, Any]) -> str:
    eco = payload["economic_scenario"]
    boundary = eco["literal_boundary"]
    partial_rows = eco["partial_rows"]
    full_rows = eco["full_rows"]
    audit = payload["closure_audit"]
    rows = "\n".join(
        f"| {p['prefunding_level_F']:g} | {p['worker_resources_X']:.9f} | "
        f"{p['successor_marginal_value_V_e']:.9f} | {f['worker_resources_X']:g} | "
        f"{f['successor_marginal_value_V_e']:.6f} |"
        for p, f in zip(partial_rows, full_rows, strict=True)
    )
    return f"""# CS012 I2a — successor boundary and public prefunding under {eco["packet_id"]}

**Result use: `exploratory_only`.** Successor-side evidence only. No government kernel,
welfare result, equilibrium claim, or optimal portfolio. CS012 v0.1 is a draft.

## The contrast this block establishes

Full automation eliminates worker human wealth. On the full-AK branch productive human
wealth exactly offsets installed-capital value, so worker resources are just the
inherited public safe buffer, `X_F = F`. Worker consumption is `ρF` and the successor
marginal value is `1/(ρF)`, which **diverges like 1/F** as the buffer vanishes. At
`F = 0` exactly, worker consumption is zero and the successor marginal value is positive
infinity — a structural boundary, returned as a tagged extended real and kept out of
every logarithm and finite difference.

Partial automation does not do this. It retains positive worker human wealth net of
installed-capital value — `H_P(K₀) − q_P(K₀)K₀ = {eco["productive_wealth"]["H_P_minus_qP_K"]:.9f}` —
so `X_P = F + {eco["productive_wealth"]["H_P_minus_qP_K"]:.9f}` stays bounded away from
zero and its successor marginal value has a **finite limit** of about
{boundary["partial_automation"]["successor_marginal_value"]["value"]:.6f}.

| F | X_P | V_{{P,e}} | X_F | V_{{F,e}} |
|---:|---:|---:|---:|---:|
{rows}

The log–log elasticities make the same point sharply. The full-AK elasticity is exactly
−1 at every adjacent pair; the partial elasticity runs
{eco["elasticities"]["partial"][0]:.6f} → {eco["elasticities"]["partial"][-1]:.6f},
approaching zero rather than −1.

## What this is not

It is not evidence about an optimal government portfolio, and not yet a government
kernel of any kind. The normalized kernel `k^G_j = V_{{j,e}}/μ_e` needs the pre-event
optimized government marginal value in the denominator. The closure audit reports:

```
pre_event_mu_e_status: {audit["pre_event_mu_e_status"]}
```

The pre-arrival costate system exists at the pinned commit only as *equations* — solving
it is CS011 block N4, which is not implemented there — and the one candidate, `μ_e = 1/C`
from the interior consumption condition, would need `C` from a solved optimized
continuation. Supplying `C` by hand would make it a fixed-policy derivative, which CS012
explicitly excludes. So no `k^G` and no `γ` are reported here, rather than being
approximated.

The values above are numerators. They are informative about the boundary's structure and
about which branch is fragile as public wealth vanishes, and about nothing else yet.

## SYN-02

`P-CS012-SYN-02` is a directly constructed analytic fixture replacing the false
"stationary-compatible" label carried by `P-CS012-SYN-01`, which is quarantined and
unmodified. It is stationary-compatible by construction: `r_F − ρ − g = 0` exactly, with
`q_F = exp[φ(g+δ)]` and `A_bar` inverted from the zero-tax user-cost equation. It has no
economic interpretation and is not a two-mark scenario.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the CS012 I2a report.")
    parser.add_argument("--economic-config", required=True)
    parser.add_argument("--prefunding-config", required=True)
    parser.add_argument("--analytic-config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)

    repository = Path(__file__).resolve().parents[3]
    provenance = git_provenance(repository)
    if not provenance.clean_start and not args.allow_dirty:
        print(
            "refused: the working tree is dirty. Evidence is generated from a clean "
            "implementation commit.",
            file=sys.stderr,
        )
        return 2

    output_dir = Path(args.output_dir)
    if output_dir.exists():
        print(
            f"refused: {output_dir} already exists; immutable outputs are never "
            "overwritten.",
            file=sys.stderr,
        )
        return 2

    started = time.perf_counter()
    payload = build_i2_report(
        Path(args.economic_config).resolve(),
        Path(args.prefunding_config).resolve(),
        Path(args.analytic_config).resolve(),
        provenance,
        0.0,
    )
    payload["machine_runtime_seconds"] = time.perf_counter() - started

    output_dir.mkdir(parents=True)
    report_path = output_dir / "identity_report.json"
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
    print(f"closure {payload['closure_audit']['pre_event_mu_e_status']}")
    print(f"government kernels reported: {payload['government_kernels']['reported']}")
    print(f"prefunding fingerprint {payload['configs']['prefunding']['fingerprint']}")
    print(f"syn02 fingerprint {payload['configs']['analytic']['fingerprint']}")
    print(f"result_use {payload['result_use']}")
    print(json.dumps(payload["economic_scenario"]["maxima"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
