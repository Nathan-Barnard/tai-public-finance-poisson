"""Command-line entry point for the CS005 first-real-attempt run (F0-F2 core / W1)."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .diagnostics import (
    candidate_is_admissible,
    certify_postmark_tail,
    check_physical_risk_neutral_separation,
    diagnose_candidate,
    diagnose_postmark,
)
from .postmark_equations import mark_params
from .postmark_solver import solve_postmark
from .prearrival_solver import enumerate_with_domain_expansion, point_geometry
from .primitives import compute_derived_constants, load_raw_primitives, run_fingerprint
from .reporting import git_metadata, serializable, write_bundle
from .strict_viability import CERTIFIED_INFEASIBLE, CERTIFIED_VIABLE, FRONTIER_UNRESOLVED, W5_METHOD, candidate_strict_viability

_STRUCTURAL_TOLERANCE = 1.0e-6
"""Generous tolerance separating "the ODE/algebra solved correctly" (observed residuals
are 1e-10 to 1e-17 throughout) from a genuine numerical failure -- not CS005's eventual
1e-10/1e-8 acceptance tolerance, which independent_tolerance in the config targets."""


def _load_experiment(config_path: Path) -> dict:
    experiment = json.loads(config_path.read_text(encoding="utf-8"))
    primitive_path = (config_path.parent / experiment["primitive_file"]).resolve()
    experiment["_primitive_path"] = primitive_path
    return experiment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--runs-dir", help="Where to write the immutable run-record YAML (default: <repository>/runs).")
    parser.add_argument("--preflight-tests-status", default="not_recorded")
    parser.add_argument("--k-grid-points", type=int, default=None, help="Override the experiment config's k_grid_points.")
    args = parser.parse_args()

    repository = Path(__file__).resolve().parents[3]
    git_at_run_start = git_metadata(repository)
    started = time.perf_counter()

    config_path = Path(args.config).resolve()
    experiment = _load_experiment(config_path)
    primitives = load_raw_primitives(experiment["_primitive_path"])
    derived = compute_derived_constants(primitives)
    tolerances = experiment.get("tolerances", {"independent_tolerance": 1.0e-8, "solver_tolerance": 1.0e-10})
    k_grid_points = args.k_grid_points or experiment.get("k_grid_points", 400)

    mp_L = mark_params(primitives, derived, "L")
    mp_H = mark_params(primitives, derived, "H")
    path_L = solve_postmark(mp_L, mp_L.anchor.u_min, mp_L.anchor.u_max)
    path_H = solve_postmark(mp_H, mp_H.anchor.u_min, mp_H.anchor.u_max)

    pm_L = diagnose_postmark(mp_L, path_L)
    pm_H = diagnose_postmark(mp_H, path_H)
    postmark_diagnostics = {"L": serializable(pm_L), "H": serializable(pm_H)}
    postmark_ok = all(
        getattr(pm, field) <= _STRUCTURAL_TOLERANCE
        for pm in (pm_L, pm_H)
        for field in (
            "pm01_ode_residual_finite_difference",
            "pm02_H_prime_vs_q_finite_difference",
            "pm03_anchor_user_cost_identity",
            "pm03_k_star_recompute_relative_error",
            "pm04_eigenvalue_relative_error_vs_numerical_jacobian",
            "pm06_zero_tax_recovery_max_abs",
        )
    ) and all(pm.pm07_specialization_margin_min > 0.0 for pm in (pm_L, pm_H))

    result, path_L, path_H = enumerate_with_domain_expansion(primitives, derived, path_L, path_H, k_grid_points=k_grid_points)

    # PM08 decisive tail/transversality certificate: backward true-time integration
    # from a local linear tail, computed on the FINAL (possibly domain-expanded)
    # paths so the certificate covers the domain the candidates actually used. The
    # forward-shooting pm08_* fields above remain as warning-level diagnostics.
    independent_tolerance = tolerances.get("independent_tolerance", 1.0e-8)
    cert_L = certify_postmark_tail(mp_L, path_L, tolerance=independent_tolerance)
    cert_H = certify_postmark_tail(mp_H, path_H, tolerance=independent_tolerance)
    pm08_certificates = {"L": serializable(cert_L), "H": serializable(cert_H)}

    candidate_rows = []
    structural_ok = postmark_ok
    for c in result.candidates:
        diag = diagnose_candidate(primitives, derived, path_L, path_H, c)
        admissible_ex_w5 = candidate_is_admissible(diag, tolerances.get("independent_tolerance", 1.0e-8))
        # W5 strict support-based fiscal viability: f_j^+ >= underline_f_j(k, ell) for
        # every supported mark, certified conservatively (see strict_viability.py).
        # Candidate-level "admissible" now REQUIRES a certified_viable W5 label;
        # admissible_ex_w5 preserves the pre-W5 meaning (implemented checks only).
        # A frontier_unresolved label blocks admissibility certification but is a
        # certification gap, never an infeasibility finding.
        viability = candidate_strict_viability(primitives, derived, path_L, path_H, c)
        admissible = admissible_ex_w5 and viability.passes
        g = point_geometry(primitives, derived, path_L, path_H, c.k)
        sep = check_physical_risk_neutral_separation(primitives, g)
        row_structural_ok = (
            diag.pr02_private_portfolio_raw_foc <= _STRUCTURAL_TOLERANCE
            and diag.pr03_public_portfolio_raw_foc <= _STRUCTURAL_TOLERANCE
            and diag.pr04_public_saving_raw_foc <= _STRUCTURAL_TOLERANCE
            and diag.pr06_capital_residual_independent_reimplementation <= _STRUCTURAL_TOLERANCE
            and diag.pr07_balance_sheet_identity <= _STRUCTURAL_TOLERANCE
            and (diag.pr08_boundary_uncleared_equation is None or diag.pr08_boundary_uncleared_equation <= _STRUCTURAL_TOLERANCE)
            and sep.uses_risk_neutral
        )
        structural_ok = structural_ok and row_structural_ok
        candidate_rows.append(
            {
                "k": c.k,
                "e": c.e,
                "psi": c.psi,
                "pi": c.pi,
                "branch": c.branch,
                "nu_B": c.nu_B,
                "b": c.b,
                "epsilon_B": c.epsilon_B,
                "K_residual": c.K_residual,
                "slot": c.slot,
                "recovery": serializable(c.recovery),
                "diagnostics": serializable(diag),
                "admissible": admissible,
                "admissible_ex_w5": admissible_ex_w5,
                "strict_viability_checked": True,
                "strict_viability_pass": viability.passes,
                "strict_viability_label": viability.label,
                "strict_viability_margin": viability.min_margin,
                "strict_viability": serializable(viability),
                "is_atlas_entry": diag.is_atlas_entry,
                "structural_checks_pass": row_structural_ok,
                "physical_risk_neutral_separation": serializable(sep),
            }
        )

    n_admissible = sum(1 for row in candidate_rows if row["admissible"])
    n_admissible_ex_w5 = sum(1 for row in candidate_rows if row["admissible_ex_w5"])
    n_date_zero = sum(1 for row in candidate_rows if not row["is_atlas_entry"])
    w5_label_counts = {
        label: sum(1 for row in candidate_rows if row["strict_viability_label"] == label)
        for label in (CERTIFIED_VIABLE, FRONTIER_UNRESOLVED, CERTIFIED_INFEASIBLE)
    }
    outcome = "computational_pass" if structural_ok else "computational_fail"
    pm08_cs005_tolerance_pass = cert_L.passes and cert_H.passes
    qualification = (
        "First real prototype / reduced-coverage computational pass, not a decision-grade CS005 pass "
        f"(spec draft; PM08 tail/transversality at CS005 tolerance: {pm08_cs005_tolerance_pass}; "
        "W5 strict viability checked via certified-inner/outer bounds; W2/W3/W4 out of scope): "
    )
    w5_sentence = (
        f" W5 strict-viability labels: {w5_label_counts[CERTIFIED_VIABLE]} certified_viable, "
        f"{w5_label_counts[FRONTIER_UNRESOLVED]} frontier_unresolved, "
        f"{w5_label_counts[CERTIFIED_INFEASIBLE]} certified_infeasible_on_declared_domain. "
        f"{n_admissible_ex_w5} candidate(s) pass every pre-W5 implemented check (admissible_ex_w5); "
        f"'admissible' additionally requires a certified_viable W5 label. A frontier_unresolved label is a "
        "certification gap of the constant-tax lower-bound witness, not evidence of fiscal infeasibility."
    )
    if not structural_ok:
        conclusion = "One or more structural/independent-evaluator checks failed to meet the generous 1e-6 sanity tolerance -- treat all candidates below as unverified. See per-check residuals in diagnostics."
    elif n_admissible == 0:
        conclusion = qualification + (
            f"computation completed cleanly ({len(candidate_rows)} candidates enumerated, all independent checks passed at high precision); "
            "no candidate satisfies every admissibility condition (tax bounds, positive consumption, transfer floor, debt sign, private solvency, specialization, "
            "certified W5 strict viability) simultaneously under this profile and reduced-coverage search. This is a substantive finding, not a computational failure."
            + w5_sentence
        )
    else:
        conclusion = qualification + (
            f"computation completed cleanly; {n_admissible} of {len(candidate_rows)} candidates are fully admissible (including certified W5 strict viability). "
            f"{n_date_zero} candidate(s) match the declared inherited state (date-zero); all others are atlas entries."
            + w5_sentence
        )

    run_id = args.run_id or f"RUN-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-CS005-{(git_at_run_start['commit'] or 'nogit')[:8]}-01"
    report = {
        "run_id": run_id,
        "profile_id": primitives.primitive_set_id,
        "config_path": str(config_path),
        "primitive_path": str(experiment["_primitive_path"]),
        "run_fingerprint": run_fingerprint(
            primitives,
            tolerances,
            {"k_grid_points": k_grid_points, "marks": ["L", "H"], "worker": "W1_binary_mark_rank_one_baseline", "w5_strict_viability_method": W5_METHOD},
        ),
        "tolerances": tolerances,
        "postmark_status": "pass" if postmark_ok else "fail",
        "postmark_diagnostics": postmark_diagnostics,
        "pm08_certificates": pm08_certificates,
        "derived_constants": {
            "eta_W": derived.eta_W,
            "eta_K": derived.eta_K,
            "q_star": derived.q_star,
            "iota_star": derived.iota_star,
            "lambda_L": derived.lambda_L,
            "lambda_H": derived.lambda_H,
            "Delta_0": derived.Delta_0,
            "anchors": {mark: serializable(a) for mark, a in derived.anchors.items()},
        },
        "inherited_state": serializable(derived.inherited_state),
        "k_domain": result.k_domain,
        "discarded_nonconvergent_brackets": result.discarded_nonconvergent_brackets,
        "candidates": candidate_rows,
        "outcome": outcome,
        "decision_grade": False,
        "coverage": "reduced",
        "pm08_cs005_tolerance_pass": pm08_cs005_tolerance_pass,
        "strict_viability_checked": True,
        "strict_viability_method": W5_METHOD,
        "n_admissible_ex_w5": n_admissible_ex_w5,
        "strict_viability_label_counts": w5_label_counts,
        "conclusion": conclusion,
        "preflight_tests_status": args.preflight_tests_status,
    }

    limitations = [
        "Draft specification (CS005 v0.7): every result is proof-assurance stage S0_unassessed; a numerical root is a candidate, not evidence of existence, uniqueness, global optimality, or equilibrium.",
        "Reduced-coverage root search: one log-spaced k-grid per branch slot (interior x2, boundary x2, private-portfolio x2) with pole-aware bracket rejection and bisection refinement -- not CS005's full 513/1025-node Chebyshev, 64-Sobol-start, iterative box/domain-doubling coverage-certification protocol. Branch-slot identity is sorted-order-based, not continuation-tracked, so a bifurcation could in principle hide or double-count a root.",
        "PM08 tail/transversality: the decisive certificate is backward true-time integration from a local linear tail attached at |u|=1e-3 using the numerically-built Jacobian eigendecomposition (diagnostics.certify_postmark_tail; per-mark method, attachment point, saddle-path exclusion bound, manifold-match residual, tolerance, and pass/fail reported in pm08_certificates). It certifies the tail/transversality property on the certified [k_min, k_max] domain only, with a LINEARIZED contraction bound for the off-manifold exclusion -- not a computer-assisted proof. The original forward-shooting diagnostic is retained as a warning-level indicator (pm08_* fields in postmark_diagnostics); its large projections reflect forward saddle-path shooting instability, not evidence against q_j(k).",
        "PR06 (the scalar capital residual K(k)) is independently re-implemented from the same displayed reduced formula (fresh code, different intermediate structuring) plus finite-difference verification of every partial-derivative term, not from a from-scratch unreduced costate/investment-FOC pair -- CS005's four authorized source documents supply only the reduced K(k), not that pair, for this profile.",
        "W5 strict viability is checked CONSERVATIVELY, not closed: the branch-specific lower frontier underline_f_j(k, ell) = -C_j(k, ell) is bracketed between a certified-inner capacity lower bound (constant-tax continuations on the rescaled certified zero-tax stable manifold -- a RESTRICTED control family, no time-varying tax front-loading or collocation, witness PV independently re-integrated in the u-coordinate at four-times-finer tolerance) and CS005's coarse tau=1 compact-domain outer bound on the declared (possibly expanded) k-domain. Labels are certified_viable (f_j^+ above -C_lower with a 1e-6*H_ref margin, every supported mark), certified_infeasible_on_declared_domain (f_j^+ below -C_upper for some mark), or frontier_unresolved -- the last is a certification gap, never an infeasibility finding, per CS005's rule that W5 may not classify a candidate infeasible from failure to find a path. The lower/upper capacity gap is NOT within CS005's 1e-4 closing tolerance, so no claimed frontier is reported and CS005's full I5 collocation/mesh/horizon refinement protocol remains outstanding. The witness respects the profile's frozen tax bounds [tau_min, tau_max] (tighter than the spec's 0<=tau<=1, hence conservative for the inner bound); the outer bound uses tau=1 (conservative for infeasibility). Successor protected-value/branch consistency is imposed only through the tau-consistent smooth stable-manifold selection (price label smooth_zero_tax_stable_manifold_branch); alternative capacity concepts (sdf_value, expected_physical, defaultable) are separate experiments, not computed here.",
        "Candidate-level 'admissible' now REQUIRES a certified_viable W5 label in addition to every previously implemented check; 'admissible_ex_w5' preserves the pre-W5 meaning. A candidate that is admissible_ex_w5 but frontier_unresolved is neither certified viable nor refuted.",
        "W2 (two-tranche capital-income-strip/residual-equity rank), W3 (direct tax-path price-response cone), W4 (fixed-mark diagnostic), a global transition, and a closed-economy version are all explicitly out of scope for this pass.",
        "The provisional profile P-CS005-REAL-01 is a judgement calibration (EMP005), not a source-versioned empirical estimate -- report every economic quantity as a first real attempt, not a decision-grade magnitude.",
        "gamma_a (private-wealth stationarity compatibility) is reported per candidate, not enforced -- a nonzero value means the candidate is a conditional real-fiscal policy rest point rather than a full domestic balanced-growth path, per the model doc's own framing; this is not treated as a failure.",
        "Codex-side registry note: CP005 has no bound implementation_repository entry as of this run; this record names the repository, commit, and branch explicitly per the fallback convention until that binding is made.",
    ]

    command = (
        f"uv run python -m tai_public_finance.cs005_marked_poisson.cli --config {args.config} "
        f"--output-dir {args.output_dir} --run-id {run_id}"
    )
    runs_dir = Path(args.runs_dir).resolve() if args.runs_dir else None
    output = write_bundle(Path(args.output_dir).resolve(), report, repository, time.perf_counter() - started, command, git_at_run_start, runs_dir, primitives.spec_version, limitations)
    print(
        json.dumps(
            {
                "run_id": run_id,
                "outcome": outcome,
                "decision_grade": False,
                "coverage": "reduced",
                "pm08_cs005_tolerance_pass": pm08_cs005_tolerance_pass,
                "strict_viability_checked": True,
                "strict_viability_label_counts": w5_label_counts,
                "n_candidates": len(candidate_rows),
                "n_admissible": n_admissible,
                "n_admissible_ex_w5": n_admissible_ex_w5,
                "n_date_zero": n_date_zero,
                "discarded_nonconvergent_brackets": result.discarded_nonconvergent_brackets,
                "record": str(output["record_path"]),
                "report": str(output["report_path"]),
            },
            indent=2,
        )
    )
    return 0 if outcome == "computational_pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
