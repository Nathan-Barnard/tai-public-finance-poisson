"""Assembling the material-run bundle: JSON report and the immutable run record."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import scipy
import yaml


def serializable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: serializable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)  # "nan"/"inf"/"-inf" -- not valid JSON literals
    if isinstance(value, dict):
        return {str(key): serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serializable(item) for item in value]
    return value


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def git_metadata(repository: Path) -> dict[str, Any]:
    def run(*args: str) -> str:
        completed = subprocess.run(["git", *args], cwd=repository, check=True, capture_output=True, text=True)
        return completed.stdout.strip()

    try:
        commit = run("rev-parse", "HEAD")
        branch = run("branch", "--show-current")
        dirty = bool(run("status", "--porcelain"))
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, branch, dirty = None, None, None
    return {"commit": commit, "branch": branch, "dirty_worktree_at_run_start": dirty}


def environment_metadata() -> dict[str, Any]:
    memory_gb = None
    try:
        memory_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3
    except (ValueError, OSError, AttributeError):
        pass
    return {
        "operating_system": platform.platform(),
        "architecture": platform.machine(),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "pyyaml": yaml.__version__,
        "cpu": platform.processor() or None,
        "logical_cores": os.cpu_count(),
        "memory_gb": memory_gb,
        "precision": "float64",
    }


def write_bundle(
    output_dir: Path,
    report: dict[str, Any],
    repository: Path,
    elapsed_seconds: float,
    command: str,
    git_at_run_start: dict[str, Any],
    runs_dir: Path | None,
    spec_version: str,
    limitations: list[str],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=False)

    environment = environment_metadata()
    report_to_write = serializable(report | {"environment": environment, "implementation": git_at_run_start, "elapsed_seconds": elapsed_seconds})
    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report_to_write, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    n_candidates = len(report["candidates"])
    n_admissible = sum(1 for c in report["candidates"] if c["admissible"])
    summary_path = output_dir / "summary.md"
    summary_path.write_text(
        "\n".join(
            [
                f"# {report['run_id']}",
                "",
                f"- Outcome: **{report['outcome']}** (prototype / reduced-coverage pass; decision_grade: "
                f"{str(report['decision_grade']).lower()}, coverage: {report['coverage']}, "
                f"pm08_cs005_tolerance_pass: {str(report['pm08_cs005_tolerance_pass']).lower()}, "
                f"strict_viability_checked: {str(report['strict_viability_checked']).lower()})",
                f"- Profile: `{report['profile_id']}` (spec CS005 v{spec_version}, status draft -- exploratory first attempt)",
                f"- Post-mark blocks: L and H both `{report['postmark_status']}`",
                f"- Candidates found: {n_candidates} (discarded non-convergent brackets: {report['discarded_nonconvergent_brackets']})",
                f"- Fully admissible candidates: {n_admissible}",
                f"- Date-zero (inherited-state-matching) candidates: {sum(1 for c in report['candidates'] if not c['is_atlas_entry'])}",
                "",
                "Interpretation: every candidate is a conditional rest point/atlas entry unless "
                "explicitly marked otherwise; a numerical root is not evidence of existence, "
                "uniqueness, global optimality, or equilibrium. See report.json's `limitations` "
                "for what this run does and does not establish.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    artifacts = [
        {"role": "primary_output", "location": str(report_path.relative_to(repository)) if _is_relative(report_path, repository) else str(report_path), "sha256": sha256_file(report_path), "bytes": report_path.stat().st_size},
        {"role": "supporting_output", "location": str(summary_path.relative_to(repository)) if _is_relative(summary_path, repository) else str(summary_path), "sha256": sha256_file(summary_path), "bytes": summary_path.stat().st_size},
    ]

    run_record = {
        "schema_version": "1.0",
        "run_id": report["run_id"],
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "status": "completed",
        "purpose": (
            "First real-attempt CP005 run under the provisional calibration P-CS005-REAL-01 "
            "(or the synthetic regression profile P-CS005-SMOKE-01): post-mark stable-manifold "
            "continuation (F1), pre-arrival rank-one candidate enumeration with debt-interior "
            "and debt-boundary KKT branches (F2 core / W1), and independent diagnostics. "
            "Diagnostic first-run evidence, not a decision-grade empirical result -- "
            "see specification.status."
        ),
        "specification": {"id": "CS005", "version": spec_version, "status": "draft", "fingerprint_sha256": None},
        "input_fingerprints": {"run_fingerprint_sha256": report["run_fingerprint"]},
        "problem_id": "CP005",
        "approach_id": "CA008",
        "benchmark_id": "CB005",
        "implementation": {
            "repository_url": "https://github.com/Nathan-Barnard/tai-public-finance-poisson",
            "local_path": str(repository),
            "commit": git_at_run_start["commit"],
            "branch": git_at_run_start["branch"],
            "dirty_worktree": git_at_run_start["dirty_worktree_at_run_start"],
            "dirty_worktree_at_run_start": git_at_run_start["dirty_worktree_at_run_start"],
            "implementer": "claude_code",
            "entrypoint": "python3 -m tai_public_finance.cs005_marked_poisson.cli",
            "command": command,
        },
        "environment": {
            "operating_system": environment["operating_system"],
            "architecture": environment["architecture"],
            "runtime_versions": {key: environment[key] for key in ("python", "numpy", "scipy", "pyyaml")},
            "dependency_lock_path": "uv.lock",
            "dependency_lock_sha256": sha256_file(repository / "uv.lock") if (repository / "uv.lock").exists() else None,
            "container_or_image": None,
        },
        "hardware": {
            "resource_lane": "L1_interactive",
            "machine_label": "local_mac",
            "cpu": environment["cpu"],
            "logical_cores": environment["logical_cores"],
            "memory_gb": environment["memory_gb"],
            "accelerator": None,
            "accelerator_memory_gb": None,
            "detected_at_runtime": True,
        },
        "budget": {
            "wall_seconds_limit": 600,
            "cash_limit_usd": 0,
            "actual_cash_usd": 0,
            "early_stop_rule": "Stop and retain failure if the post-mark ODE, anchor, or independent-evaluator checks fail outright; economic inadmissibility of a candidate (tax bound, transfer floor, debt sign, consumption positivity) is reported, not treated as a run failure.",
        },
        "randomness": {"deterministic_requested": True, "seeds": [], "nondeterminism_notes": "Deterministic float64 ODE integration and grid/bisection root search; no simulation draws."},
        "inputs": {
            "profile_id": report["profile_id"],
            "input_artifacts": [report["config_path"], report["primitive_path"]],
        },
        "solver": {
            "packages_and_versions": {"numpy": environment["numpy"], "scipy": environment["scipy"]},
            "method": (
                "Post-mark: two one-sided scipy.integrate.solve_ivp (DOP853) shooting solves in "
                "(u=log(k/k*), v=log(q/q*)) continuation coordinates from the first-order stable "
                "expansion, with domain expansion on demand. Pre-arrival: algebraic elimination "
                "(affine-polynomial construction, not hand-expanded) for the private-portfolio "
                "quadratic, the public-saving/exposure linear-plus-quadratic system, and the "
                "cleared debt-boundary KKT polynomial; the scalar capital residual K(k) is then "
                "searched on a log-spaced grid per branch slot, with pole-aware bracket rejection "
                "and manual (non-scipy) bisection refinement -- a reduced-coverage search "
                "relative to CS005's full Chebyshev/Sobol multi-start protocol (see "
                "prearrival_solver.py's module docstring)."
            ),
            "tolerances": report["tolerances"],
            "initialization": "First-order stable-manifold expansion at the anchor; log-spaced k-grid for candidate search.",
            "continuation": "Domain expansion by one log unit (capped at |u|=8) when an accepted root is within 0.25 log units of the post-mark graph's edge.",
            "precision": "float64",
        },
        "preflight": {
            "tests_command": "uv run pytest",
            "tests_status": report["preflight_tests_status"],
            "exact_or_manufactured_benchmark": "Closed-form anchor/eigenvalue identities, numerically-built Jacobian eigendecomposition, raw nonlinear public-FOC substitution, and a deliberate physical/risk-neutral intensity swap regression.",
        },
        "result": {
            "outcome": report["outcome"],
            "decision_grade": report["decision_grade"],
            "coverage": report["coverage"],
            "pm08_cs005_tolerance_pass": report["pm08_cs005_tolerance_pass"],
            "strict_viability_checked": report["strict_viability_checked"],
            "wall_seconds": elapsed_seconds,
            "peak_memory_gb": None,
            "actual_cash_usd": 0,
            "checkpoints_recovered": False,
            "solver_reported_metrics": {"n_candidates": n_candidates, "n_admissible": n_admissible, "discarded_nonconvergent_brackets": report["discarded_nonconvergent_brackets"]},
            "independent_diagnostics": {"postmark": report["postmark_diagnostics"], "candidates": [c["diagnostics"] for c in report["candidates"]]},
            "economic_quantities": {"derived_constants": report["derived_constants"], "inherited_state": report["inherited_state"], "candidates": report["candidates"]},
            "reliable_region": "Post-mark continuation objects (q_j(k), H_j(k)) only, on the certified [k_min, k_max] domain reported per mark; pre-arrival candidates are conditional atlas entries, not equilibria.",
            "failure_code": None,
            "failure_detail": None,
        },
        "artifacts": artifacts,
        "interpretation": {
            "supports_result_ids": ["R26", "R27", "R28"],
            "challenges_result_ids": [],
            "question_ids": ["Q09", "Q11", "Q13", "Q14"],
            "assurance_or_review_artifacts": [
                "economics-verification/reviews/poisson-branch-genealogy-tax-timing-portfolios-and-safe-debt--EV07.md",
                "economics-verification/reviews/ramsey-counterfactual-design-inherited-state-rents-and-interpretation--EV09.md",
            ],
            "conclusion": report["conclusion"],
            "limitations": limitations,
            "next_decision": "Report back to Nathan for independent review before attempting the two-tranche (W2) and tax-span (W3/W4/W5) blocks; the Codex-side registry still needs CP005's repository binding recorded.",
        },
    }
    record_path = (runs_dir or repository / "runs") / f"{report['run_id']}.yaml"
    record_path.parent.mkdir(parents=True, exist_ok=True)
    if record_path.exists():
        raise FileExistsError(f"Run record {record_path} already exists. Run records are immutable -- reuse of a run_id is not permitted.")
    record_path.write_text(yaml.safe_dump(serializable(run_record), sort_keys=False, allow_unicode=False), encoding="utf-8")
    return {"record_path": record_path, "report_path": report_path, "summary_path": summary_path, "artifacts": artifacts, "environment": environment, "git": git_at_run_start}


def _is_relative(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False
