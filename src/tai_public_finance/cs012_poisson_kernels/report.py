"""Build and write the compact CS012 I0 manufactured-fixture identity report.

CLI (frozen by the CS012 I0 implementation handoff):

    uv run python -m tai_public_finance.cs012_poisson_kernels.report \
        --fixtures configs/cs012/i0_manufactured_fixtures.json \
        --output outputs/cs012-i0-pricing-kernel-identities/identity_report.json

The report is written once and never overwritten: an existing output path is a
refusal, not a silent replacement. Reconstruct into a scratch path and compare
hashes instead.

Everything in the report is ``exploratory_only`` identity and boundary
characterization evidence. It cannot support a finite government kernel path, a
portfolio sign in an economic scenario, a welfare conclusion, an existence
result, or an optimal portfolio.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .extended import ExtendedReal, canonical_json, sha256_of_bytes, sha256_of_object
from .independent import NotReconstructible, owner_residual_independent, reconstruct
from .inputs import FORMULA_CONVENTION, FixtureInput, load_fixtures
from .kernels import KernelOutcome, evaluate_kernels
from .portfolio import (
    Decomposition,
    OwnerRootResult,
    decompose,
    normalized_error,
    solve_owner_root,
)
from .projection import ProjectionResult, SafeAccountRank, project_fiscal_gap, safe_account_rank
from .statuses import (
    BRANCH_LITERAL_LAISSEZ_FAIRE,
    FINITE_MAINTAINED_BRANCH,
    PROJECTION_RESOLVED,
    RESULT_USE,
    UNIQUE_INTERIOR_ROOT,
)

SCHEMA = "cs012-i0-identity-report/1"

SPECIFICATION = {
    "specification_id": "CS012",
    "version": "0.1",
    "status": "draft",
    "sha256": "d345f07cdeaf6901fd1ea985cb2566d8c717e4b4dce5ba9fa489375b895d0498",
    "superseded_specification_sha256": "275cf384a6aa8f12831bd0e7b8b8ea4291e49402f3578a9c301baf91fe2930e8",
    "supersession_note": (
        "The 2026-09-05 report at the earlier CS012 hash remains valid historical "
        "exploratory evidence under that hash; it is not edited or withdrawn. The "
        "intervening specification change concerns the downstream signed-safe "
        "CS011 v0.6 scope and does not alter any I0 formula."
    ),
    "path": (
        "computation/specifications/"
        "laissez-faire-poisson-relative-valuation-and-public-portfolio-laboratory--CS012.md"
    ),
    "workspace": "TAI public finnace codex",
}

TOLERANCE_POLICY = {
    "normalized_error": "abs(lhs-rhs)/max(1, sum(abs(term)))",
    "production_identity_max": 1.0e-11,
    "production_versus_independent_max": 1.0e-10,
    "owner_root_residual_max": 1.0e-11,
    "owner_root_boundary_margin_min_factor": 1.0e-10,
    "weighted_orthogonality_max": 1.0e-11,
}


def _extended(value: ExtendedReal | None) -> dict[str, Any] | None:
    return None if value is None else value.to_json()


def fixture_fingerprint(fixtures: tuple[FixtureInput, ...]) -> str:
    """SHA-256 over the operative I0 fields only.

    Includes the specification id/version/hash, the formula convention, the mark
    ordering, the direct fields, the tolerance policy, and each fixture's declared
    boundary status. Excludes paths, prose, timestamps, and every computed
    residual, so it is insensitive to JSON whitespace and key order but sensitive
    to every operative value.
    """
    return sha256_of_object(
        {
            "specification": {
                key: SPECIFICATION[key]
                for key in ("specification_id", "version", "sha256")
            },
            "formula_convention": FORMULA_CONVENTION,
            "tolerance_policy": TOLERANCE_POLICY,
            "fixtures": [fixture.direct_fields() for fixture in fixtures],
        }
    )


@dataclass(frozen=True, slots=True)
class Provenance:
    code_commit: str
    branch: str
    clean_start: bool
    repository_url: str
    python_version: str
    scipy_version: str
    numpy_version: str
    platform: str
    machine: str


def git_provenance(repository: Path) -> Provenance:
    import numpy
    import scipy

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repository), *args],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    return Provenance(
        code_commit=git("rev-parse", "HEAD"),
        branch=git("rev-parse", "--abbrev-ref", "HEAD"),
        clean_start=git("status", "--porcelain") == "",
        repository_url=git("remote", "get-url", "origin"),
        python_version=sys.version.split()[0],
        scipy_version=scipy.__version__,
        numpy_version=numpy.__version__,
        platform=platform.platform(),
        machine=platform.machine(),
    )


def _root_payload(root: OwnerRootResult) -> dict[str, Any]:
    interval = root.interval
    return {
        "status": root.status,
        "detail": root.detail,
        "interval": None
        if interval is None
        else {
            "lower": interval.lower if interval.lower_is_finite else None,
            "upper": interval.upper if interval.upper_is_finite else None,
            "lower_is_finite": interval.lower_is_finite,
            "upper_is_finite": interval.upper_is_finite,
            "zero_is_interior": interval.contains(0.0),
        },
        "exposure": root.exposure,
        "residual_at_root": root.residual_at_root,
        "derivative_at_root": root.derivative_at_root,
        "boundary_margin": root.boundary_margin
        if root.boundary_margin is None or root.boundary_margin != float("inf")
        else None,
        "boundary_margin_is_unbounded": root.boundary_margin == float("inf"),
        "residual_at_zero_exposure": root.residual_at_zero,
        "limit_at_unbounded_end": root.limit_at_unbounded_end,
    }


def _projection_payload(projection: ProjectionResult) -> dict[str, Any]:
    return {
        "status": projection.status,
        "detail": projection.detail,
        "denominator": projection.denominator,
        "numerator": projection.numerator,
        "alpha": projection.alpha,
        "components": [
            {
                "mark_id": component.mark_id,
                "gap": component.gap,
                "parallel": component.parallel,
                "orthogonal": component.orthogonal,
            }
            for component in projection.components
        ],
        "weighted_norm_gap": projection.weighted_norm_gap,
        "weighted_norm_parallel": projection.weighted_norm_parallel,
        "weighted_norm_orthogonal": projection.weighted_norm_orthogonal,
        "weighted_inner_product_orthogonal_payoff": (
            projection.weighted_inner_product_orthogonal_payoff
        ),
        "orthogonality_error": projection.orthogonality_error,
    }


def _safe_payload(safe: SafeAccountRank) -> dict[str, Any]:
    return {
        "safe_payoff_vector": list(safe.safe_payoff_vector),
        "risky_payoff_vector": list(safe.risky_payoff_vector),
        "rank_risky": safe.rank_risky,
        "rank_with_safe_account": safe.rank_with_safe_account,
        "rank_increase": safe.rank_increase,
        "safe_account_has_zero_marked_payoff": safe.safe_account_has_zero_marked_payoff,
        "detail": safe.detail,
    }


def _finite_fixture_payload(
    fixture: FixtureInput, outcome: KernelOutcome
) -> dict[str, Any]:
    decomposition: Decomposition = decompose(outcome)
    root = solve_owner_root(outcome)
    projection = project_fiscal_gap(outcome)
    safe = safe_account_rank(outcome)

    marks = [
        {
            "mark_id": mark.mark_id,
            "lambda_physical": mark.lambda_physical,
            "lambda_risk_neutral": mark.lambda_risk_neutral,
            "payoff_jump": mark.payoff_jump,
            "owner_wealth_multiplier": mark.owner_wealth_multiplier,
            "k_world": mark.k_world,
            "k_owner": mark.k_owner,
            "k_government": mark.k_government,
            "gamma": mark.gamma,
            "term_owner": term.owner,
            "term_government": term.government,
            "term_government_owner": term.government_owner,
            "term_relative": term.relative,
        }
        for mark, term in zip(outcome.marks, decomposition.terms, strict=True)
    ]

    payload: dict[str, Any] = {
        "fixture_id": fixture.fixture_id,
        "declared_branch": fixture.declared_branch,
        "description": fixture.description,
        "inputs": fixture.direct_fields(),
        "kernel_status": outcome.status,
        "kernel_detail": outcome.detail,
        "worker_consumption": _extended(outcome.worker_consumption),
        "marks": marks,
        "boundary_marks": [],
        "sums": {
            "d_owner": decomposition.d_owner,
            "d_government": decomposition.d_government,
            "d_government_owner": decomposition.d_government_owner,
            "d_relative": decomposition.d_relative,
        },
        "identities": {
            "decomposition_error": decomposition.decomposition_error,
            "relative_identity_error": decomposition.relative_identity_error,
            "relative_identity_applies": decomposition.relative_identity_applies,
        },
        "owner_root": _root_payload(root),
        "projection": _projection_payload(projection),
        "safe_account": _safe_payload(safe),
        "units": {
            "lambda_physical": "inverse time",
            "lambda_risk_neutral": "inverse time",
            "payoff_jump": "current good per unit installed equity",
            "owner_exposure": "inverse payoff unit",
            "government_marginal_value": "utility per current good",
            "kernels": "dimensionless",
            "residual_sums": "inverse time",
        },
    }

    # --- independent reconstruction, by the alternative in-package route --------
    independent = reconstruct(fixture)
    kernel_errors = [
        max(
            abs(production["k_world"] - alt.k_world),
            abs(production["k_owner"] - alt.k_owner),
            abs(production["k_government"] - alt.k_government),
            abs(production["gamma"] - alt.gamma),
        )
        for production, alt in zip(marks, independent.marks, strict=True)
    ]
    term_scale = tuple(
        value
        for mark in marks
        for value in (
            mark["term_owner"],
            mark["term_government"],
            mark["term_government_owner"],
            mark["term_relative"],
        )
    )
    sum_errors = {
        "d_owner": normalized_error(decomposition.d_owner, independent.d_owner, term_scale),
        "d_government": normalized_error(
            decomposition.d_government, independent.d_government, term_scale
        ),
        "d_government_owner": normalized_error(
            decomposition.d_government_owner,
            independent.d_government_owner,
            term_scale,
        ),
        "d_relative": normalized_error(
            decomposition.d_relative, independent.d_relative, term_scale
        ),
    }
    root_route_error: float | None = None
    if root.status == UNIQUE_INTERIOR_ROOT and root.exposure is not None:
        root_route_error = normalized_error(
            owner_residual_independent(fixture, root.exposure), 0.0, term_scale
        )
    projection_error: float | None = None
    if projection.status == PROJECTION_RESOLVED and independent.projection_alpha is not None:
        projection_error = max(
            abs((projection.alpha or 0.0) - independent.projection_alpha),
            max(
                (
                    abs(component.orthogonal - alt)
                    for component, alt in zip(
                        projection.components, independent.orthogonal, strict=True
                    )
                ),
                default=0.0,
            ),
        )

    payload["independent"] = {
        "route": "expanded-form sums, consumption-ratio owner kernel, plain summation",
        "marks": [
            {
                "mark_id": alt.mark_id,
                "k_world": alt.k_world,
                "k_owner": alt.k_owner,
                "k_government": alt.k_government,
                "gamma": alt.gamma,
                "term_owner": alt.term_owner,
                "term_government": alt.term_government,
                "term_government_owner": alt.term_government_owner,
                "term_relative": alt.term_relative,
            }
            for alt in independent.marks
        ],
        "sums": {
            "d_owner": independent.d_owner,
            "d_government": independent.d_government,
            "d_government_owner": independent.d_government_owner,
            "d_relative": independent.d_relative,
        },
        "projection_alpha": independent.projection_alpha,
        "projection_denominator": independent.projection_denominator,
        "orthogonal": list(independent.orthogonal),
    }
    payload["production_versus_independent"] = {
        "max_kernel_absolute_error": max(kernel_errors, default=0.0),
        "sum_normalized_errors": sum_errors,
        "max_sum_normalized_error": max(sum_errors.values()),
        "owner_root_independent_residual": root_route_error,
        "projection_absolute_error": projection_error,
    }
    return payload


def _boundary_fixture_payload(
    fixture: FixtureInput, outcome: KernelOutcome
) -> dict[str, Any]:
    safe = safe_account_rank(outcome)
    return {
        "fixture_id": fixture.fixture_id,
        "declared_branch": fixture.declared_branch,
        "description": fixture.description,
        "inputs": fixture.direct_fields(),
        "kernel_status": outcome.status,
        "kernel_detail": outcome.detail,
        "worker_consumption": _extended(outcome.worker_consumption),
        "marks": [],
        "boundary_marks": [
            {
                "mark_id": mark.mark_id,
                "lambda_physical": mark.lambda_physical,
                "lambda_risk_neutral": mark.lambda_risk_neutral,
                "payoff_jump": mark.payoff_jump,
                "k_world": mark.k_world.to_json(),
                "owner_wealth_multiplier": mark.owner_wealth_multiplier.to_json(),
                "k_owner": mark.k_owner.to_json(),
                "k_government": mark.k_government.to_json(),
                "gamma": mark.gamma.to_json(),
            }
            for mark in outcome.boundary_marks
        ],
        # No finite residual arithmetic is attempted at the boundary: the sums,
        # identities, owner root, and projection are structurally absent, not zero.
        "sums": None,
        "identities": None,
        "owner_root": None,
        "projection": None,
        "safe_account": _safe_payload(safe),
        "independent": None,
        "production_versus_independent": None,
        "units": {
            "worker_consumption": "current good",
            "government_marginal_value": "utility per current good",
            "kernels": "dimensionless (extended real)",
        },
    }


def build_report(
    fixtures: tuple[FixtureInput, ...],
    provenance: Provenance,
    fixture_path: Path,
    machine_runtime_seconds: float,
) -> dict[str, Any]:
    """Assemble the full report payload for a parsed fixture set."""
    entries: list[dict[str, Any]] = []
    for fixture in fixtures:
        outcome = evaluate_kernels(fixture)
        if outcome.status == FINITE_MAINTAINED_BRANCH:
            entries.append(_finite_fixture_payload(fixture, outcome))
        elif fixture.declared_branch == BRANCH_LITERAL_LAISSEZ_FAIRE:
            entries.append(_boundary_fixture_payload(fixture, outcome))
        else:
            raise RuntimeError(
                f"fixture {fixture.fixture_id!r} refused on the finite branch with "
                f"status {outcome.status}: {outcome.detail}. Invalid and non-finite "
                "cases belong in tests, not in the accepted finite fixture report."
            )

    kernel_counts = Counter(entry["kernel_status"] for entry in entries)
    root_counts = Counter(
        entry["owner_root"]["status"]
        for entry in entries
        if entry["owner_root"] is not None
    )
    projection_counts = Counter(
        entry["projection"]["status"]
        for entry in entries
        if entry["projection"] is not None
    )

    def _maxima(extract) -> float:
        values = [
            value
            for entry in entries
            for value in (extract(entry),)
            if value is not None
        ]
        return max(values) if values else 0.0

    summary = {
        "fixture_count": len(entries),
        "kernel_status_counts": dict(sorted(kernel_counts.items())),
        "owner_root_status_counts": dict(sorted(root_counts.items())),
        "projection_status_counts": dict(sorted(projection_counts.items())),
        "refusal_counts": {
            "kernel_non_finite_branch": len(entries) - kernel_counts.get(
                FINITE_MAINTAINED_BRANCH, 0
            ),
            "owner_root_unidentified_or_boundary": sum(
                count
                for status, count in root_counts.items()
                if status != UNIQUE_INTERIOR_ROOT
            ),
            "projection_refused": sum(
                count
                for status, count in projection_counts.items()
                if status != PROJECTION_RESOLVED
            ),
        },
        "max_decomposition_error": _maxima(
            lambda entry: None
            if entry["identities"] is None
            else entry["identities"]["decomposition_error"]
        ),
        "max_relative_identity_error": _maxima(
            lambda entry: None
            if entry["identities"] is None
            else entry["identities"]["relative_identity_error"]
        ),
        "max_owner_root_residual": _maxima(
            lambda entry: None
            if entry["owner_root"] is None
            else (
                None
                if entry["owner_root"]["residual_at_root"] is None
                else abs(entry["owner_root"]["residual_at_root"])
            )
        ),
        "max_orthogonality_error": _maxima(
            lambda entry: None
            if entry["projection"] is None
            else entry["projection"]["orthogonality_error"]
        ),
        "max_production_versus_independent_error": _maxima(
            lambda entry: None
            if entry["production_versus_independent"] is None
            else max(
                entry["production_versus_independent"]["max_sum_normalized_error"],
                entry["production_versus_independent"]["max_kernel_absolute_error"],
                entry["production_versus_independent"][
                    "owner_root_independent_residual"
                ]
                or 0.0,
                entry["production_versus_independent"]["projection_absolute_error"]
                or 0.0,
            )
        ),
    }

    return {
        "schema": SCHEMA,
        "specification": SPECIFICATION,
        "formula_convention": FORMULA_CONVENTION,
        "tolerance_policy": TOLERANCE_POLICY,
        "result_use": RESULT_USE,
        "interpretation_limits": [
            "identity and boundary characterization only",
            "no economic calibration, scenario, successor, transition, or portfolio grid",
            "no policy, welfare, existence, or optimality claim",
            "CS012 is a draft specification; this run does not promote it",
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
                (Path(__file__).resolve().parents[3] / "uv.lock").read_bytes()
            ),
        },
        "fixture_set": {
            "path": str(fixture_path),
            "sha256": sha256_of_bytes(fixture_path.read_bytes()),
            "fingerprint": fixture_fingerprint(fixtures),
        },
        "fixtures": entries,
        "summary": summary,
        "machine_runtime_seconds": machine_runtime_seconds,
    }


def write_report(payload: dict[str, Any], output: Path) -> str:
    """Write the report once. Returns its SHA-256. Refuses to overwrite."""
    if output.exists():
        raise FileExistsError(
            f"{output} already exists; immutable outputs are never overwritten. "
            "Reproduce into a scratch path and compare hashes instead."
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    output.write_text(text, encoding="utf-8")
    return sha256_of_bytes(output.read_bytes())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the CS012 I0 manufactured-fixture identity report."
    )
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Record clean_start=false and generate anyway. Never use for evidence.",
    )
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

    fixture_path = Path(args.fixtures).resolve()
    fixtures = load_fixtures(fixture_path)
    started = time.perf_counter()
    payload = build_report(fixtures, provenance, fixture_path, 0.0)
    payload["machine_runtime_seconds"] = time.perf_counter() - started

    output = Path(args.output)
    digest = write_report(payload, output)
    print(f"wrote {output}")
    print(f"sha256 {digest}")
    print(f"bytes {output.stat().st_size}")
    print(f"fixture_fingerprint {payload['fixture_set']['fingerprint']}")
    print(f"result_use {payload['result_use']}")
    print(canonical_json(payload["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
