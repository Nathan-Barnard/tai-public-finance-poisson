"""CS012 I0: the Poisson pricing-kernel identity core.

A parameter-free, solver-independent implementation of the world, domestic-owner,
and government jump pricing kernels; the owner's admissible exposure interval and
portfolio-pricing root; the exact government/owner residual decomposition; the
intensity-weighted marketed projection and orthogonal fiscal gap; the exact
safe-account payoff rank; and the literal laissez-faire extended-real boundary.

Governing records, in the read-only Codex research workspace:

* specification ``CS012`` v0.1 (draft), SHA-256
  ``d345f07cdeaf6901fd1ea985cb2566d8c717e4b4dce5ba9fa489375b895d0498``;
* work plan ``CP012``; decision ``CD016``.

The first I0 report was generated against the earlier CS012 hash
``275cf384a6aa8f12831bd0e7b8b8ea4291e49402f3578a9c301baf91fe2930e8`` and remains
valid historical exploratory evidence under that hash. The intervening
specification change concerns the downstream signed-safe ``CS011 v0.6`` scope and
alters no I0 formula.

This package shares no equations with the quarantined ``cs005_marked_poisson``
pre-arrival route and imports nothing from it. Everything it produces is
``exploratory_only``: identity and boundary evidence, never a finite government
kernel path, a portfolio sign in an economic scenario, a welfare conclusion, an
existence result, or an optimal portfolio.
"""

from .extended import ExtendedReal, ExtendedRealError
from .independent import IndependentReconstruction, reconstruct
from .inputs import FixtureInput, InputError, MarkInput, load_fixtures
from .kernels import (
    BoundaryKernels,
    KernelOutcome,
    KernelRefusal,
    MarkKernels,
    evaluate_kernels,
)
from .portfolio import (
    Decomposition,
    ExposureInterval,
    OwnerRootResult,
    ResidualTerm,
    decompose,
    exposure_interval,
    finite_root_exists,
    normalized_error,
    one_mark_analytic_root,
    owner_residual,
    owner_residual_derivative,
    owner_residual_limit,
    solve_owner_root,
)
from .projection import (
    ProjectionComponent,
    ProjectionResult,
    SafeAccountRank,
    project_fiscal_gap,
    safe_account_rank,
)
from .statuses import ALL_STATUSES, RESULT_USE

__all__ = [
    "ALL_STATUSES",
    "RESULT_USE",
    "BoundaryKernels",
    "Decomposition",
    "ExposureInterval",
    "ExtendedReal",
    "ExtendedRealError",
    "FixtureInput",
    "IndependentReconstruction",
    "InputError",
    "KernelOutcome",
    "KernelRefusal",
    "MarkInput",
    "MarkKernels",
    "OwnerRootResult",
    "ProjectionComponent",
    "ProjectionResult",
    "ResidualTerm",
    "SafeAccountRank",
    "decompose",
    "evaluate_kernels",
    "exposure_interval",
    "finite_root_exists",
    "load_fixtures",
    "normalized_error",
    "one_mark_analytic_root",
    "owner_residual",
    "owner_residual_derivative",
    "owner_residual_limit",
    "project_fiscal_gap",
    "reconstruct",
    "safe_account_rank",
    "solve_owner_root",
]
