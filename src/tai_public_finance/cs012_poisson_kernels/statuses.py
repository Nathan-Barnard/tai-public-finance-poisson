"""Explicit status vocabulary for the CS012 I0 pricing-kernel identity core.

Every public routine in this package returns one of these labels. A refusal is
never signalled by ``None``, ``NaN``, a warning string, or a "successful solver"
flag: the caller reads ``.status`` and, if it wants a number, calls the
``require_*`` accessor, which raises rather than inventing a value.

Frozen by ``CS012`` v0.1, section "I0 -- identity and portfolio-pricing core"
and by the implementation handoff
``computation/laissez-faire-poisson-pricing-kernels-i0-claude-handoff--CS012.md``.
"""

from __future__ import annotations

# --- kernel-evaluation statuses -------------------------------------------------

FINITE_MAINTAINED_BRANCH = "finite_maintained_branch"
"""All intensities, marginal values, and owner wealth multipliers are finite and
lie in their declared admissible domains; finite kernel arithmetic is allowed."""

NONFINITE_FINITE_BRANCH_INPUT = "nonfinite_finite_branch_input"
"""A direct input on the maintained finite branch is NaN or infinite, or violates
a strict-positivity / nonnegativity requirement. Not a large finite kernel."""

INVALID_DIRECT_WEALTH_RATIO = "invalid_direct_wealth_ratio"
"""Owner wealth-ratio inputs are unusable (non-positive wealth, non-finite ratio)
or disagree with the ``owner_exposure`` route beyond the declared tolerance."""

NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE = (
    "nonfinite_fiscal_kernel_at_literal_laissez_faire"
)
"""Literal laissez-faire: the full-AK successor leaves hand-to-mouth workers with
zero consumption, so the government's successor marginal value is ``+inf``. This
is a structural extended-real boundary, not a floating-point failure, and it must
not enter finite residual arithmetic."""

KERNEL_STATUSES = (
    FINITE_MAINTAINED_BRANCH,
    NONFINITE_FINITE_BRANCH_INPUT,
    INVALID_DIRECT_WEALTH_RATIO,
    NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE,
)

# --- owner-portfolio root statuses ----------------------------------------------

UNIQUE_INTERIOR_ROOT = "unique_interior_root"
"""A finite sign change was bracketed strictly inside the open admissible exposure
interval; the residual is strictly decreasing there, so the root is unique."""

NO_INTERIOR_ROOT_BOUNDARY_LIMIT = "no_interior_root_boundary_limit"
"""The owner residual keeps one sign on the whole open interval and only approaches
zero (or a nonzero limit) at an endpoint. There is no finite interior root."""

ZERO_PAYOFF_UNIDENTIFIED = "zero_payoff_unidentified"
"""Every marked payoff component is exactly zero, so the owner's portfolio-pricing
equation is satisfied identically and identifies no exposure. Not a root at an
arbitrary default exposure."""

ROOT_STATUSES = (
    UNIQUE_INTERIOR_ROOT,
    NO_INTERIOR_ROOT_BOUNDARY_LIMIT,
    ZERO_PAYOFF_UNIDENTIFIED,
    NONFINITE_FINITE_BRANCH_INPUT,
    INVALID_DIRECT_WEALTH_RATIO,
    NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE,
)

# --- projection statuses --------------------------------------------------------

PROJECTION_RESOLVED = "projection_resolved"
"""The physical-intensity-weighted payoff norm is resolvable and the fiscal gap was
decomposed into marketed and orthogonal parts."""

ZERO_PAYOFF_NORM_REFUSED = "zero_payoff_norm_refused"
"""``sum_j lambda_j J_j^2`` is exactly zero: there is no payoff direction to project
on. The vector is not normalized into a direction."""

UNRESOLVED_PAYOFF_NORM_REFUSED = "unresolved_payoff_norm_refused"
"""The weighted payoff norm is nonzero but too small relative to the terms that
formed it to be resolved in FP64. Refused rather than reported."""

PROJECTION_STATUSES = (
    PROJECTION_RESOLVED,
    ZERO_PAYOFF_NORM_REFUSED,
    UNRESOLVED_PAYOFF_NORM_REFUSED,
    NONFINITE_FINITE_BRANCH_INPUT,
    INVALID_DIRECT_WEALTH_RATIO,
    NONFINITE_FISCAL_KERNEL_AT_LITERAL_LAISSEZ_FAIRE,
)

ALL_STATUSES = tuple(
    dict.fromkeys(KERNEL_STATUSES + ROOT_STATUSES + PROJECTION_STATUSES)
)

# --- declared branch labels -----------------------------------------------------

BRANCH_FINITE_MAINTAINED = "finite_maintained_branch"
BRANCH_LITERAL_LAISSEZ_FAIRE = "literal_laissez_faire"

DECLARED_BRANCHES = (BRANCH_FINITE_MAINTAINED, BRANCH_LITERAL_LAISSEZ_FAIRE)

# --- result-use label -----------------------------------------------------------

RESULT_USE = "exploratory_only"
"""CS012 I0 is identity and boundary-characterization evidence only. It cannot
support a finite government kernel path, a portfolio sign in an economic scenario,
a welfare conclusion, an existence result, or an optimal portfolio."""
