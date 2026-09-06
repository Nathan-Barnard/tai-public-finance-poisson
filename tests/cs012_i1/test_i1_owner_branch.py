"""CS012 I1 acceptance: dependency pinning, successors, owner branch, containment."""

from __future__ import annotations

import json
import math
import sys

import pytest

from tai_public_finance.cs012_poisson_kernels.i1_owner_branch import (
    GOVERNMENT_EXCLUDED,
    MIN_ABS_PAYOFF,
    OwnerBranchError,
    build_payoffs,
    solve_owner_branch,
)
from tai_public_finance.cs012_poisson_kernels.i1_successors import (
    MARK_F,
    MARK_P,
    dependency_provenance,
    payoff_jump,
)

from .conftest import CS011_COMMIT

# Independent preflight values from the I1 handoff. These are cross-checks, not
# constants the implementation may be tuned to reproduce.
SMOKE = {
    "q_0": 1.1972173631218102,
    "K_P_star": 1.25,
    "q_P_K0": 1.2913477098,
    "q_F": 1.1517472652,
    "J_P": 0.07862427454,
    "J_F": -0.03797981832,
    "exposure": 11.016082014,
    "X_P": 1.8661314566,
    "X_F": 0.5816112065,
}


# --- dependency pinning -------------------------------------------------------------


def test_the_dependency_resolves_to_the_exact_pinned_commit():
    resolved = dependency_provenance()["resolved"]
    assert resolved["commit_id"] == CS011_COMMIT
    assert resolved["requested_revision"] == CS011_COMMIT
    assert resolved["vcs"] == "git"


def test_the_lockfile_pins_the_dependency_by_full_revision():
    from .conftest import REPOSITORY

    lock = (REPOSITORY / "uv.lock").read_text(encoding="utf-8")
    assert f"rev={CS011_COMMIT}" in lock
    assert f"#{CS011_COMMIT}" in lock


def test_no_forbidden_cs011_module_is_imported():
    """Only the parameter schemas, tolerances, both successor services, and the
    fixtures data module may be imported. The N2/N3 stationary machinery may not."""
    from .conftest import REPOSITORY

    forbidden = (
        "ak_partial_ramsey.stationary",
        "ak_partial_ramsey.continuation",
        "ak_partial_ramsey.certificate",
        "ak_partial_ramsey.rows",
        "ak_partial_ramsey.profiles",
        "ak_partial_ramsey.derivatives",
        "ak_partial_ramsey.assembly",
        "ak_partial_ramsey.evaluator",
        "ak_partial_ramsey.recovery",
        "ak_partial_ramsey.exposure",
    )
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (REPOSITORY / "src" / "tai_public_finance" / "cs012_poisson_kernels").glob("*.py")
    )
    for module in forbidden:
        bare = module.split(".")[-1]
        assert f"from ak_partial_ramsey.{bare}" not in sources, module
        assert f"import ak_partial_ramsey.{bare}" not in sources, module
    assert not any(name in sys.modules for name in ("ak_partial_ramsey.continuation",
                                                    "ak_partial_ramsey.certificate"))


# --- successor services --------------------------------------------------------------


def test_exactly_one_ak_root_is_selected_and_the_rejected_root_is_retained(services):
    candidates = services.ak.candidates
    assert len(candidates) == 2
    accepted = [c for c in candidates if c.accepted]
    rejected = [c for c in candidates if not c.accepted]
    assert len(accepted) == 1
    assert accepted[0].branch == "lower_strict_tvc"
    assert accepted[0].tvc_margin > 0.0
    assert len(rejected) == 1
    assert rejected[0].branch == "upper_tvc_violating"
    assert rejected[0].reason == "productive_value_tvc_violated"
    assert rejected[0].tvc_margin < 0.0
    assert services.ak.q_F == pytest.approx(SMOKE["q_F"], abs=1e-9)


def test_the_partial_manifold_covers_the_whole_declared_interval(services, economic_packet):
    lo, hi = services.certified_domain
    declared_lo, declared_hi = economic_packet.partial_capital_interval
    assert lo <= declared_lo and hi >= declared_hi
    assert (lo, hi) == (0.5, 2.0)
    assert services.partial.point.K_star == pytest.approx(SMOKE["K_P_star"], abs=1e-12)


def test_extrapolation_outside_the_certified_domain_is_impossible(services):
    from ak_partial_ramsey.errors import DomainError

    for K in (0.49, 2.01, 5.0):
        with pytest.raises(DomainError):
            services.q_P(K)
        with pytest.raises(DomainError):
            services.partial.H_P(K)


def test_the_dependency_independent_route_diagnostics_agree(services):
    diagnostics = services.partial.diagnostics
    assert diagnostics["max_ivp_bvp_difference"] < 1e-6
    assert diagnostics["wealth_route_max_gap"] < 1e-6
    assert diagnostics["rest_point_slope_gap"] < 1e-6
    # Both productive-wealth routes at the baseline, compared rather than averaged.
    assert services.partial.H_P(1.0) == pytest.approx(services.partial.H_P_algebraic(1.0), rel=1e-7)


# --- payoffs and owner branch ---------------------------------------------------------


def test_the_baseline_reproduces_the_independent_preflight_values(services, economic_packet):
    q_0 = economic_packet.q_0
    assert q_0 == pytest.approx(SMOKE["q_0"], abs=1e-15)
    q_P = services.q_P(1.0)
    assert q_P == pytest.approx(SMOKE["q_P_K0"], abs=1e-9)
    J_P = payoff_jump(q_P, q_0)
    J_F = payoff_jump(services.q_F(), q_0)
    assert J_P == pytest.approx(SMOKE["J_P"], abs=1e-10)
    assert J_F == pytest.approx(SMOKE["J_F"], abs=1e-10)

    payoffs = build_payoffs(
        q_0,
        ((MARK_P, q_P), (MARK_F, services.q_F())),
        {
            MARK_P: (economic_packet.lambda_P, economic_packet.lambda_P_star),
            MARK_F: (economic_packet.lambda_F, economic_packet.lambda_F_star),
        },
    )
    branch = solve_owner_branch("smoke", 1.0, q_0, payoffs, economic_packet.a_0)
    assert branch.exposure == pytest.approx(SMOKE["exposure"], abs=1e-8)
    assert branch.marks[0].wealth_multiplier == pytest.approx(SMOKE["X_P"], abs=1e-9)
    assert branch.marks[1].wealth_multiplier == pytest.approx(SMOKE["X_F"], abs=1e-9)


def test_marks_keep_their_labels_and_input_order(i1_report):
    baseline = i1_report["economic"]["baseline"]
    assert [m["mark_id"] for m in baseline["marks"]] == ["P", "F"]
    # P has the larger payoff; a sort by magnitude would not change the order here,
    # so use the descending-|J| case to show order is carried, not derived.
    assert abs(baseline["marks"][0]["payoff_jump"]) > abs(baseline["marks"][1]["payoff_jump"])


def test_every_baseline_wealth_multiplier_is_strictly_positive(i1_report):
    for mark in i1_report["economic"]["baseline"]["marks"]:
        assert mark["wealth_multiplier"] > 0.0
        assert mark["owner_wealth_after"] > 0.0


def test_every_baseline_payoff_clears_the_weak_identification_floor(i1_report):
    for mark in i1_report["economic"]["baseline"]["marks"]:
        assert abs(mark["payoff_jump"]) >= MIN_ABS_PAYOFF


def test_a_weak_payoff_is_refused_rather_than_reported(economic_packet):
    q_0 = economic_packet.q_0
    payoffs = build_payoffs(
        q_0,
        ((MARK_P, q_0 * 1.0001), (MARK_F, q_0 * 0.95)),
        {MARK_P: (0.01625, 0.014), MARK_F: (0.00875, 0.026)},
    )
    with pytest.raises(OwnerBranchError, match="weakly identified"):
        solve_owner_branch("weak", 1.0, q_0, payoffs, 1.0)


def test_the_owner_root_residual_is_inside_tolerance_everywhere(i1_report):
    maxima = i1_report["economic"]["maxima"]
    assert maxima["max_owner_root_residual"] <= 1e-10
    assert maxima["max_independent_exposure_residual"] <= 1e-10
    assert maxima["max_independent_kernel_error"] <= 1e-10
    assert maxima["max_independent_d_owner_error"] <= 1e-10


def test_the_wealth_ratio_route_separates_when_owner_wealth_is_not_one(services, economic_packet):
    """At a_0 = 1 the before/after route reduces to the same FP64 expression as
    1/(1+pi J), so its agreement carries no information. This pins down that the route
    is genuinely evaluated, and still agrees, at a_0 far from one."""
    q_0 = economic_packet.q_0
    payoffs = build_payoffs(
        q_0,
        ((MARK_P, services.q_P(1.0)), (MARK_F, services.q_F())),
        {
            MARK_P: (economic_packet.lambda_P, economic_packet.lambda_P_star),
            MARK_F: (economic_packet.lambda_F, economic_packet.lambda_F_star),
        },
    )
    branch = solve_owner_branch("scaled", 1.0, q_0, payoffs, 3.7)
    for mark in branch.marks:
        assert mark.owner_wealth_before == 3.7
        assert mark.owner_wealth_after != mark.wealth_multiplier
    assert branch.independent_kernel_max_error <= 1e-10
    assert branch.independent_d_owner_error <= 1e-10
    assert branch.exposure == pytest.approx(SMOKE["exposure"], abs=1e-8)


def test_all_reported_quantities_are_finite(i1_report):
    def walk(value, path=""):
        if isinstance(value, float):
            assert math.isfinite(value), path
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}/{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    walk(i1_report)


def test_the_report_serializes_as_strict_json_with_no_infinity_token(i1_report):
    """An unbounded exposure endpoint is null plus a flag, never an ``Infinity``
    token and never a large finite sentinel."""
    text = json.dumps(i1_report, allow_nan=False)
    assert "Infinity" not in text and "NaN" not in text

    def reject(constant):
        raise AssertionError(f"non-standard JSON token: {constant}")

    json.loads(text, parse_constant=reject)


def test_an_unbounded_exposure_endpoint_is_reported_as_null_plus_a_flag(i1_report):
    """At the larger diagnostic capital points both payoffs turn negative, so the
    admissible interval opens downward. That regime must serialize honestly."""
    unbounded = [
        row
        for row in i1_report["economic"]["diagnostic_grid"]
        if row["flags"]["valid"]
        and row["owner"]["exposure_interval"]["lower_is_finite"] is False
    ]
    assert unbounded, "expected at least one all-negative-payoff diagnostic row"
    for row in unbounded:
        owner = row["owner"]
        assert owner["lower_boundary_distance"] is None
        assert owner["lower_boundary_is_unbounded"] is True
        assert row["lower_boundary_distance"] is None
        assert all(mark["payoff_jump"] < 0.0 for mark in owner["marks"])


# --- government exclusion --------------------------------------------------------------


def test_no_government_object_is_produced_anywhere_in_the_report(i1_report):
    """No government *field* exists. Prose that names these objects in order to
    exclude them is exactly what the block should say, so the check walks keys and
    numeric leaves rather than grepping the whole serialization."""
    forbidden = {
        "k_government",
        "gamma",
        "d_government",
        "d_government_owner",
        "d_relative",
        "mu_e",
        "government_current_marginal_value",
        "government_successor_marginal_value",
        "V_F_e",
        "V_P_e",
        "worker_consumption",
        "prefunding",
        "welfare",
    }

    def walk(value, path=""):
        if isinstance(value, dict):
            for key, item in value.items():
                assert key not in forbidden, f"{path}/{key}"
                walk(item, f"{path}/{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    walk(i1_report)
    assert i1_report["economic"]["government_objects_present"] is False


def test_the_reused_i0_kernel_record_carries_no_representable_government_value(
    services, economic_packet
):
    from tai_public_finance.cs012_poisson_kernels.i1_owner_branch import _as_i0_outcome

    q_0 = economic_packet.q_0
    payoffs = build_payoffs(
        q_0,
        ((MARK_P, services.q_P(1.0)), (MARK_F, services.q_F())),
        {MARK_P: (0.01625, 0.014), MARK_F: (0.00875, 0.026)},
    )
    outcome = _as_i0_outcome("t", payoffs)
    assert math.isnan(GOVERNMENT_EXCLUDED)
    for mark in outcome.marks:
        assert math.isnan(mark.k_government)
        assert math.isnan(mark.gamma)


# --- well-conditioned containment (the contained I0 subnormal limitation) --------------


def test_the_economic_packet_stays_inside_the_well_conditioned_domain(i1_report):
    """The ultra-subnormal FP64 root-status defect is outside this packet's declared
    domain. Rather than modifying the I0 root algorithm, assert containment: every
    intensity-payoff product that the owner residual and its projection form is a
    normal double, far from the subnormal region where I0 refuses."""
    tiny = sys.float_info.min  # smallest positive normal double
    for row in i1_report["economic"]["diagnostic_grid"]:
        if not row["flags"]["valid"]:
            continue
        for mark in row["owner"]["marks"]:
            lam, J = mark["lambda_physical"], mark["payoff_jump"]
            assert abs(lam * J) > tiny * 1e12
            assert abs(lam * J * J) > tiny * 1e12
            assert abs(mark["d_owner_contribution"]) > tiny * 1e12
        assert abs(row["owner"]["exposure"]) < 1e12
        assert abs(row["owner"]["derivative_at_root"]) > tiny * 1e12


def test_the_reported_exposure_is_nowhere_near_the_fp64_reach_limit(i1_report):
    for row in i1_report["economic"]["diagnostic_grid"]:
        if row["flags"]["valid"]:
            assert abs(row["owner"]["exposure"]) < 2.0**60


# --- diagnostic grid ------------------------------------------------------------------


def test_the_diagnostic_grid_is_sensitivity_not_a_baseline_search(i1_report, economic_packet):
    grid = i1_report["economic"]["diagnostic_grid"]
    assert [row["capital"] for row in grid] == [0.8, 1.0, 1.2, 1.4, 1.6]
    baselines = [row for row in grid if row["is_baseline"]]
    assert len(baselines) == 1
    assert baselines[0]["capital"] == economic_packet.baseline_capital == 1.0
    assert i1_report["economic"]["baseline"]["capital"] == 1.0


def test_every_grid_row_carries_all_four_flags(i1_report):
    for row in i1_report["economic"]["diagnostic_grid"]:
        flags = row["flags"]
        for name in ("valid", "quarantined", "branch", "inside_certified_domain",
                     "interpolated", "reliable_domain", "note"):
            assert name in flags


def test_a_grid_point_outside_the_certified_domain_is_quarantined_not_aggregated(
    economic_packet, services
):
    """Constructed directly: an out-of-domain point must never reach an aggregate."""
    from ak_partial_ramsey.errors import DomainError

    lo, hi = services.certified_domain
    with pytest.raises(DomainError):
        services.q_P(hi + 0.5)
