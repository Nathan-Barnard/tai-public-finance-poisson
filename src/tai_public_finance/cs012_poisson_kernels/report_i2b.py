"""Generate the immutable CS012 I2b transfer-constrained prefunding report.

    uv run python -m tai_public_finance.cs012_poisson_kernels.report_i2b \
        --economic-config   configs/cs012/P-CS012-ECO-02.json \
        --prefunding-config configs/cs012/P-CS012-PREFUND-01.json \
        --analytic-config   configs/cs012/P-CS012-SYN-02.json \
        --output-dir outputs/cs012-i2b-transfer-constrained-prefunding-eco02

Reports the constrained successor value ``V_{P,e} = 1/A`` under
``C_t = max{W(K_t), A e^{(r-rho)t}}`` with ``T_t >= 0``, superseding the I2a partial
rows, which used the unrestricted annuity outside its transfer-feasible domain.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from ak_partial_ramsey.primitives import capital_growth, task_wage

from .extended import ExtendedReal, sha256_of_bytes
from .i1_packets import load_economic_packet
from .i1_successors import dependency_provenance, model_parameters, solve_successors
from .i2_packets import SYN01_QUARANTINE, load_analytic_fixture, load_prefunding_packet
from .i2_prefunding import audit_mu_e_closure, safe_position_tvc
from .i2b_constrained import (
    BOUNDARY_ACTIVE,
    GLOBALLY_INTERIOR,
    boundary_marginal_value,
    build_productive_path,
    solve_constrained_successor,
)
from .report import SPECIFICATION, git_provenance
from .statuses import RESULT_USE

SCHEMA = "cs012-i2b-transfer-constrained-report/1"

TOLERANCE_POLICY = {
    "pv_transfer_budget_max_absolute_error": 1.0e-10,
    "pv_wage_route_max_absolute_gap": 1.0e-8,
    "production_versus_independent_V_max_relative_error": 1.0e-8,
    "complementarity_and_switching_max_residual": 1.0e-9,
    "full_ak_max_relative_error": 1.0e-12,
    "full_ak_elasticity_max_absolute_error": 1.0e-12,
}

I2A_QUARANTINE = {
    "run_id": "RUN-20260906T015330Z-CS012-e6ef83e5-01",
    "output": "outputs/cs012-i2a-successor-prefunding-eco02/",
    "status": "partially_quarantined",
    "defect": (
        "The I2a partial-automation rows applied the unrestricted annuity C = rho X and "
        "V = 1/(rho X) outside its transfer-feasible domain. At ECO-02 the partial wage "
        "floor is strictly positive and r_P = 0.03 < rho = 0.04, so by equation (16.8) "
        "the transfer-slack threshold is infinite and no finite buffer makes the "
        "unrestricted annuity feasible. Those rows are an upper relaxation, not a "
        "constrained successor value."
    ),
    "quarantined_scope": [
        "partial-automation consumption rows",
        "partial successor marginal values V_{P,e}",
        "partial elasticities",
        "the reported partial F = 0 limit (5.1365; the correct one-sided limit is 1/W_P(K_0))",
        "prose derived from those quantities",
    ],
    "retained_scope": [
        "full-AK identities C_F = rho F and V_{F,e} = 1/(rho F) and their unit elasticity",
        "price data q_0, q_P, q_F",
        "the H_P quadrature-versus-algebraic productive-wealth route check",
        "configuration provenance and fingerprints",
        "the absence of government kernels and the mu_e closure audit",
    ],
    "immutable": "the I2a output and run record are neither edited nor deleted",
}

INTERPRETATION_LIMITS = [
    "constrained successor-side evidence only, under a fixed tau = 0 and Theta = 0 reference",
    "the government optimizes only transfer timing and safe saving subject to T(t) >= 0; "
    "this is not a Ramsey tax or portfolio reoptimization",
    "a successor marginal value V_{j,e} is NOT a government kernel and is never relabelled as one",
    "no normalized k^G, no gamma, no time-profile ratio, no portfolio direction",
    "no welfare comparison, no equilibrium claim, no optimal government portfolio",
    "the prefunding rows are different inherited public-wealth continuations, not free "
    "endowments and not a common-(S_0,M_0) welfare comparison",
    "rho = 3% in ECO-03 is provisional and illustrative, not estimated",
    "CS012 v0.1 is a draft and is neither review-ready nor approved",
]


def _extended(value: ExtendedReal) -> dict[str, Any]:
    return value.to_json()


def build_i2b_report(
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
            f"the prefunding packet is bound to {prefunding.bound_packet_id!r}, not "
            f"{economic.packet_id!r}"
        )
    if prefunding.bound_packet_fingerprint != economic.fingerprint:
        raise RuntimeError("the prefunding packet's bound fingerprint does not match")

    audit = audit_mu_e_closure()
    params = model_parameters(economic)
    services = solve_successors(
        params, economic.ak_root_interval, economic.partial_capital_interval
    )
    K = prefunding.baseline_capital
    rho = economic.rho
    q_P, q_F = services.q_P(K), services.q_F()
    H_P_quadrature = services.partial.H_P(K)
    H_P_algebraic = services.partial.H_P_algebraic(K)
    residual = H_P_quadrature - q_P * K

    path = build_productive_path(
        rate=economic.r_P_bar,
        initial_capital=K,
        rest_capital=services.partial.point.K_star,
        price=services.q_P,
        growth=lambda q: capital_growth(q, params.installation),
        wage=lambda cap: task_wage(cap, params.partial_technology),
    )

    levels = prefunding.levels()
    constrained = [solve_constrained_successor("P", F, rho, path, residual) for F in levels]

    # A serialized sample of the productive path, dense enough that an independent
    # checker can run its own quadrature and its own off-mesh nonnegativity checks
    # without ever calling the production integrator or root solver. The sample grid is
    # deliberately NOT the production solver's mesh.
    # The horizon is set so the capital path has reached its rest point to well below
    # FP64 resolution, which is what makes the analytic tail W(Kbar)e^{-rT}/r exact
    # enough for an independent checker to close the present-value wage identity to
    # 1e-8. A shorter sample makes the tail term itself the dominant error.
    sample_horizon = max(300.0, 1.3 * max(
        (r.switch_time.value for r in constrained if r.switch_time.kind == "finite"),
        default=0.0,
    ))
    sample_count = 1501
    samples = []
    for index in range(sample_count):
        t = sample_horizon * index / (sample_count - 1)
        samples.append({
            "t": t,
            "K": path.capital(t),
            "W": path.wage(t),
            "pv_wage_to_t": path.pv_wage(t),
        })
    switch_samples = {
        f"{r.prefunding_level:g}": {
            "switch_time": r.switch_time.to_json(),
            "wage_at_switch": (
                path.wage(r.switch_time.value) if r.switch_time.kind == "finite" else None
            ),
            "pv_wage_to_switch": (
                path.pv_wage(r.switch_time.value) if r.switch_time.kind == "finite" else None
            ),
        }
        for r in constrained
    }

    # --- full AK: W_F = 0, so transfers are strictly positive for every F > 0 and the
    # unrestricted identities are exact rather than a relaxation.
    full_rows = [
        {
            "prefunding_level_F": F,
            "worker_resources_X": F,
            "worker_consumption_C_0": rho * F,
            "successor_marginal_value_V_e": 1.0 / (rho * F),
            "wage_floor": 0.0,
            "active_set": GLOBALLY_INTERIOR,
            "exact": True,
            "level_relative_error": max(
                abs(rho * F - rho * F) / max(1.0, rho * F),
                abs(1.0 / (rho * F) - 1.0 / (rho * F)),
            ),
        }
        for F in levels
    ]
    full_values = [row["successor_marginal_value_V_e"] for row in full_rows]
    full_elasticities = [
        (math.log(full_values[i + 1]) - math.log(full_values[i]))
        / (math.log(levels[i + 1]) - math.log(levels[i]))
        for i in range(len(levels) - 1)
    ]

    counts = {
        GLOBALLY_INTERIOR: sum(1 for r in constrained if r.active_set == GLOBALLY_INTERIOR),
        BOUNDARY_ACTIVE: sum(1 for r in constrained if r.active_set == BOUNDARY_ACTIVE),
    }
    certificate = constrained[0].certificate
    threshold = certificate.underline_X
    F_min = (
        threshold.require_finite() - residual if threshold.is_finite else None
    )

    main_reference = None
    if prefunding.main_interior_reference is not None:
        target = prefunding.main_interior_reference * prefunding.scale_value
        row = next(r for r in constrained if r.prefunding_level == target)
        requirement = prefunding.minimum_transfer_margin_requirement
        margin = row.minimum_transfer_margin
        # A margin whose credible error could cross the requirement is reported as
        # indistinguishable, never as a pass.
        credible_error = max(abs(row.budget_residual), row.pv_wage_route_gap)
        if margin is None:
            verdict = "not_globally_interior"
        elif margin - credible_error > requirement:
            verdict = "robustly_interior"
        elif margin + credible_error < requirement:
            verdict = "below_requirement"
        else:
            verdict = "indistinguishable"
        main_reference = {
            "prefunding_level_F": target,
            "active_set": row.active_set,
            "minimum_transfer_margin": margin,
            "requirement": requirement,
            "credible_error": credible_error,
            "verdict": verdict,
        }

    return {
        "schema": SCHEMA,
        "block": "I2b",
        "block_scope": (
            "transfer-constrained successor values under a fixed zero-tax, zero-equity "
            "reference; supersedes the I2a partial rows"
        ),
        "specification": SPECIFICATION,
        "tolerance_policy": TOLERANCE_POLICY,
        "result_use": RESULT_USE,
        "interpretation_limits": INTERPRETATION_LIMITS,
        "economic_object": {
            "source_tax_tau": 0.0,
            "public_installed_equity_Theta": 0.0,
            "productive_path": "the selected zero-tax strict-productive-TVC successor path, retained",
            "worker_consumption": "wages plus nonnegative transfers",
            "government_optimizes": "the timing of transfers and safe saving, subject to T(t) >= 0",
            "not": [
                "the unconstrained comprehensive-wealth relaxation",
                "an unrestricted Ramsey successor",
                "a tax or portfolio reoptimization",
            ],
            "solution": "C_t = max{W(K_t), A e^{(r-rho)t}}, A exhausting the PV transfer budget",
            "marginal_value": "V_{P,e} = 1/A where differentiable",
        },
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
            "dependency_lock_sha256": sha256_of_bytes(
                (Path(__file__).resolve().parents[3] / "uv.lock").read_bytes()
            ),
            "cs011_dependency": dependency_provenance(),
        },
        "configs": {
            name: {
                "path": str(p),
                "sha256": sha256_of_bytes(p.read_bytes()),
                "packet_id": pid,
                "fingerprint": fp,
            }
            for name, p, pid, fp in (
                ("economic", economic_path, economic.packet_id, economic.fingerprint),
                ("prefunding", prefunding_path, prefunding.packet_id, prefunding.fingerprint),
                ("analytic", analytic_path, analytic.packet_id, analytic.fingerprint),
            )
        },
        "syn01_quarantine": SYN01_QUARANTINE,
        "i2a_quarantine": I2A_QUARANTINE,
        "closure_audit": audit.as_dict(),
        "government_kernels": {
            "reported": False,
            "reason": audit.status,
            "k_government": None,
            "gamma": None,
            "note": (
                "V_{j,e} is the numerator only. k^G = V_{j,e}/mu_e needs the pre-event "
                "optimized government marginal value, which the closure audit did not "
                "find at the pinned commits."
            ),
        },
        "rho": rho,
        "productive_path": {
            "rate_r_P": path.rate,
            "initial_capital": path.initial_capital,
            "rest_capital": path.rest_capital,
            "initial_wage_W_P_0": path.initial_wage,
            "rest_wage_W_P_inf": path.rest_wage,
            "integration_horizon_years": path.horizon,
            "certified_analytic_tail": path.tail_bound,
            "pv_wage_integrated": path.total_pv_wage,
            "H_P_quadrature": H_P_quadrature,
            "H_P_algebraic": H_P_algebraic,
            "H_P_route_gap": abs(H_P_quadrature - H_P_algebraic),
            "H_P_minus_qP_K": residual,
            "pv_wage_route_gap": abs(residual - path.total_pv_wage),
        },
        "transfer_slack": {
            "certificate": certificate.as_dict(),
            "threshold_underline_X": _extended(threshold),
            "F_min": F_min,
            "F_min_note": (
                "the smallest buffer at which the unrestricted annuity is globally "
                "transfer-feasible; None when the threshold is infinite"
            ),
        },
        "path_samples": {
            "note": (
                "an independent uniform sample of the selected productive path, provided "
                "so a standalone checker can run its own quadrature and off-mesh "
                "nonnegativity checks; it is not the production solver's mesh"
            ),
            "horizon": sample_horizon,
            "count": sample_count,
            "samples": samples,
            "tail_wage": path.rest_wage,
            "certified_tail_beyond_integration_horizon": path.tail_bound,
            "integration_horizon": path.horizon,
        },
        "switch_diagnostics": switch_samples,
        "constrained_rows": [row.as_dict() for row in constrained],
        "active_set_counts": counts,
        "main_interior_reference": main_reference,
        "full_ak_rows": full_rows,
        "full_ak_elasticities": full_elasticities,
        "safe_position_tvc": safe_position_tvc(rho, economic.r_F_bar),
        "literal_boundary": {
            "prefunding_level_F": 0.0,
            "status": "nonfinite_fiscal_kernel_at_literal_laissez_faire",
            "full_ak": {
                "worker_consumption": ExtendedReal.of(0.0).to_json(),
                "successor_marginal_value": ExtendedReal("positive_infinity").to_json(),
            },
            "partial_automation": {
                "one_sided_limit_V_e": _extended(boundary_marginal_value(path)),
                "rule": "1/W_P(K_0): the switch collapses to zero and A -> W_P(K_0)",
                "supersedes_i2a_value": 5.136531043748698,
            },
            "excluded_from_logarithms_and_finite_differences": True,
        },
        "maxima": {
            "max_pv_transfer_budget_error": max(abs(r.budget_residual) for r in constrained),
            "max_pv_wage_route_gap": max(r.pv_wage_route_gap for r in constrained),
            "max_full_ak_elasticity_error": max(abs(e + 1.0) for e in full_elasticities),
        },
        "machine_runtime_seconds": machine_runtime_seconds,
    }


def _summary_markdown(payload: dict[str, Any]) -> str:
    rows = payload["constrained_rows"]
    counts = payload["active_set_counts"]
    path = payload["productive_path"]
    boundary = payload["literal_boundary"]["partial_automation"]
    ref = payload["main_interior_reference"]
    table = "\n".join(
        f"| {r['prefunding_level_F']:g} | {r['active_set'].replace('transfer_','')} | "
        f"{(r['switch_time_years']['value'] if r['switch_time_years']['kind']=='finite' else '—')}"
        f"{'' if r['switch_time_years']['kind']!='finite' else ''} | "
        f"{r['successor_marginal_value_V_e']:.10f} |"
        for r in rows
    )
    reference_line = (
        "This scenario designates no main interior reference."
        if ref is None
        else (
            f"Main reference `F = {ref['prefunding_level_F']:g}`: **{ref['verdict']}**, "
            f"minimum transfer margin {ref['minimum_transfer_margin']:.10f} against a "
            f"{ref['requirement']} requirement, credible error {ref['credible_error']:.2e}."
        )
    )
    return f"""# CS012 I2b — transfer-constrained successor values ({payload["configs"]["economic"]["packet_id"]})

**Result use: `exploratory_only`.** Constrained successor-side evidence only. No
government kernel, welfare result, equilibrium claim, or optimal portfolio. CS012 v0.1
is a draft.

## What changed, and why it mattered

The I2a partial rows priced the *unrestricted* annuity `C = ρX`, `V = 1/(ρX)`. That
allocation is only feasible where the nonnegative-transfer constraint is slack for all
`t`. Here the government may choose the timing of transfers and safe saving but cannot
tax, so workers consume wages plus a nonnegative transfer, and the constrained optimum is

```
C_t = max{{ W_P(K_t), A·e^{{(r_P−ρ)t}} }},   T_t = C_t − W_P(K_t) ≥ 0,
F = ∫₀^∞ e^{{−r_P t}} T_t dt,               V_{{P,e}} = 1/A.
```

| F | active set | switch (yr) | V_{{P,e}} |
|---:|---|---:|---:|
{table}

Active sets: {counts}. The wage path runs from `W_P(K₀) = {path["initial_wage_W_P_0"]:.11f}`
to `W_P(∞) = {path["rest_wage_W_P_inf"]:.11f}`, and the present-value wage identity
`H_P − q_P K = {path["H_P_minus_qP_K"]:.12f}` is reproduced by direct integration to
{path["pv_wage_route_gap"]:.2e}.

{reference_line}

## The boundary

As `F → 0⁺` the switch collapses to zero and `A → W_P(K₀)`, so the partial successor
marginal value tends to **{boundary["one_sided_limit_V_e"]["value"]:.10f} = 1/W_P(K₀)** — not the
{boundary["supersedes_i2a_value"]:.4f} that I2a reported from the unrestricted formula. The full-AK
branch is unchanged: `W_F = 0`, transfers are strictly positive for every `F > 0`, and
`V_{{F,e}} = 1/(ρF)` diverges with unit elasticity.

## What this still cannot say

`k^G = V_{{j,e}}/μ_e` remains unavailable: the closure audit reports
`{payload["closure_audit"]["pre_event_mu_e_status"]}`. These are numerators. Nothing here
is a government kernel, a portfolio direction, or a welfare statement.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the CS012 I2b report.")
    parser.add_argument("--economic-config", required=True)
    parser.add_argument("--prefunding-config", required=True)
    parser.add_argument("--analytic-config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args(argv)

    repository = Path(__file__).resolve().parents[3]
    provenance = git_provenance(repository)
    if not provenance.clean_start and not args.allow_dirty:
        print("refused: the working tree is dirty.", file=sys.stderr)
        return 2
    output_dir = Path(args.output_dir)
    if output_dir.exists():
        print(f"refused: {output_dir} already exists.", file=sys.stderr)
        return 2

    started = time.perf_counter()
    payload = build_i2b_report(
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
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary_path = output_dir / "summary.md"
    summary_path.write_text(_summary_markdown(payload), encoding="utf-8")

    print(f"wrote {report_path}")
    print(f"report sha256 {sha256_of_bytes(report_path.read_bytes())}")
    print(f"report bytes {report_path.stat().st_size}")
    print(f"summary sha256 {sha256_of_bytes(summary_path.read_bytes())}")
    print(f"active_set_counts {json.dumps(payload['active_set_counts'], sort_keys=True)}")
    print(f"F_min {payload['transfer_slack']['F_min']}")
    print(f"main_reference {json.dumps(payload['main_interior_reference'], sort_keys=True)}")
    print(f"maxima {json.dumps(payload['maxima'], sort_keys=True)}")
    print(f"result_use {payload['result_use']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
