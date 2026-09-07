"""CS012 I2b: constrained successor values, active sets, and the interior reference."""

from __future__ import annotations

import math

import pytest

from tai_public_finance.cs012_poisson_kernels.i2b_constrained import (
    BOUNDARY_ACTIVE,
    GLOBALLY_INTERIOR,
    ConstrainedSuccessorError,
    boundary_marginal_value,
    build_productive_path,
    solve_constrained_successor,
    transfer_slack_certificate,
)

FROZEN = (1.0, 0.3, 0.1, 0.03, 0.01, 0.003, 0.001)

# Independent expectations supplied with the dispatch: cross-checks, never targets.
ECO02_V = [4.5664527129, 5.6329412368, 6.2928185834, 6.7637107165,
           7.0300851997, 7.2049260335, 7.2977621592]
ECO02_SWITCH = [38.5402, 18.6932, 9.77317, 4.98014, 2.76618, 1.47896, 0.843375]
ECO03_V = [5.6814004641, 6.4510743353, 6.7130803027, 6.9707517172,
           7.1458865910, 7.2673968009, 7.3335913230]
W_P_0 = 0.13461666352108043
W_P_INF = 0.14916860501222598
RESIDUAL = 4.867098005846903
F_MIN = 0.1051888279
MARGIN_AT_03 = 0.0058443352


def _constant_wage_path(rate: float, wage: float):
    """A manufactured path with constant capital, hence a constant wage floor.

    Exact closed forms are available, so this isolates the water-filling logic from the
    successor manifold entirely.
    """
    return build_productive_path(
        rate=rate, initial_capital=1.0, rest_capital=1.0,
        price=lambda K: 1.0, growth=lambda q: 0.0, wage=lambda K: wage,
    )


# --- manufactured constant-wage cases ---------------------------------------------------


def test_constant_wage_r_below_rho_matches_the_closed_form():
    """r < rho: the annuity decays, so there is exactly one transfer-to-zero switch and
    the budget has a closed form."""
    rate, rho, wage = 0.03, 0.04, 0.2
    path = _constant_wage_path(rate, wage)
    residual = wage / rate  # PV of a constant wage
    assert path.total_pv_wage == pytest.approx(residual, rel=1e-12)
    certificate = transfer_slack_certificate(path, rho, residual + 1.0)
    assert not certificate.threshold_is_finite
    assert certificate.underline_X.kind == "positive_infinity"

    for F in (1.0, 0.1, 0.01):
        row = solve_constrained_successor("M", F, rho, path, residual)
        assert row.active_set == BOUNDARY_ACTIVE
        t = row.switch_time.require_finite()
        A = row.annuity_coefficient
        # Continuity and the closed-form budget, both written out independently here.
        assert A * math.exp((rate - rho) * t) == pytest.approx(wage, rel=1e-11)
        closed_form = (
            A * (1.0 - math.exp(-rho * t)) / rho - wage * (1.0 - math.exp(-rate * t)) / rate
        )
        assert closed_form == pytest.approx(F, abs=1e-10)
        assert row.successor_marginal_value == pytest.approx(1.0 / A, rel=1e-15)


def test_constant_wage_r_equals_rho_is_globally_interior_for_every_positive_F():
    """r = rho with a constant wage: the PV of wages is exactly W/rho, so the threshold
    binds at F = 0 and every positive buffer is interior."""
    rate = rho = 0.03
    wage = 0.2
    path = _constant_wage_path(rate, wage)
    residual = wage / rate
    certificate = transfer_slack_certificate(path, rho, residual)
    assert certificate.threshold_is_finite
    assert certificate.underline_X.require_finite() == pytest.approx(wage / rho, rel=1e-12)

    for F in (1.0, 0.1, 1e-6):
        row = solve_constrained_successor("M", F, rho, path, residual)
        assert row.active_set == GLOBALLY_INTERIOR
        assert row.switch_time.kind == "undefined"
        assert row.annuity_coefficient == pytest.approx(rho * (F + residual), rel=1e-14)
        assert row.minimum_transfer_margin == pytest.approx(rho * F, rel=1e-9)
        assert abs(row.budget_residual) <= 1e-12


def test_constant_wage_r_above_rho_is_refused_not_guessed():
    """r > rho reverses the active-set geometry -- transfers switch ON, not off -- and
    equations (16.10)-(16.13) are not implemented. It must refuse."""
    path = _constant_wage_path(0.05, 0.2)
    with pytest.raises(ConstrainedSuccessorError, match="r > rho"):
        transfer_slack_certificate(path, 0.03, 10.0)
    with pytest.raises(ConstrainedSuccessorError, match="r > rho"):
        solve_constrained_successor("M", 1.0, 0.03, path, 4.0)


def test_a_non_positive_prefunding_level_is_refused():
    path = _constant_wage_path(0.03, 0.2)
    for F in (0.0, -1e-30):
        with pytest.raises(ConstrainedSuccessorError, match="strictly positive F"):
            solve_constrained_successor("M", F, 0.04, path, 6.6)


# --- ECO-02 -----------------------------------------------------------------------------


def test_eco02_wage_path_and_pv_identity(report_eco02):
    path = report_eco02["productive_path"]
    assert path["initial_wage_W_P_0"] == pytest.approx(W_P_0, abs=1e-14)
    assert path["rest_wage_W_P_inf"] == pytest.approx(W_P_INF, abs=1e-14)
    assert path["H_P_minus_qP_K"] == pytest.approx(RESIDUAL, abs=1e-12)
    assert path["pv_wage_route_gap"] < 1e-8


def test_eco02_every_row_is_boundary_active(report_eco02):
    """r_P = 0.03 < rho = 0.04, so by (16.8) the slack threshold is infinite."""
    rows = report_eco02["constrained_rows"]
    assert report_eco02["active_set_counts"] == {
        GLOBALLY_INTERIOR: 0, BOUNDARY_ACTIVE: 7,
    }
    assert report_eco02["transfer_slack"]["threshold_underline_X"]["kind"] == "positive_infinity"
    assert report_eco02["transfer_slack"]["F_min"] is None
    for row in rows:
        assert row["active_set"] == BOUNDARY_ACTIVE
        assert row["switch_time_years"]["kind"] == "finite"


def test_eco02_values_match_the_independent_expectations(report_eco02):
    rows = report_eco02["constrained_rows"]
    assert [r["prefunding_level_F"] for r in rows] == list(FROZEN)
    for row, expected_V, expected_t in zip(rows, ECO02_V, ECO02_SWITCH, strict=True):
        assert row["successor_marginal_value_V_e"] == pytest.approx(expected_V, abs=1e-9)
        assert row["switch_time_years"]["value"] == pytest.approx(expected_t, rel=1e-5)
        assert abs(row["pv_transfer_budget_residual"]) <= 1e-10


def test_eco02_supersedes_the_quarantined_i2a_partial_limit(report_eco02):
    boundary = report_eco02["literal_boundary"]["partial_automation"]
    assert boundary["one_sided_limit_V_e"]["value"] == pytest.approx(1.0 / W_P_0, abs=1e-10)
    assert boundary["one_sided_limit_V_e"]["value"] == pytest.approx(7.4285008545, abs=1e-9)
    assert boundary["supersedes_i2a_value"] == pytest.approx(5.136531043748698, abs=1e-12)


# --- ECO-03 -----------------------------------------------------------------------------


def test_eco03_threshold_and_classification(report_eco03):
    slack = report_eco03["transfer_slack"]
    assert slack["threshold_underline_X"]["kind"] == "finite"
    assert slack["F_min"] == pytest.approx(F_MIN, abs=1e-9)
    counts = report_eco03["active_set_counts"]
    assert counts == {GLOBALLY_INTERIOR: 2, BOUNDARY_ACTIVE: 5}
    by_level = {r["prefunding_level_F"]: r for r in report_eco03["constrained_rows"]}
    assert by_level[1.0]["active_set"] == GLOBALLY_INTERIOR
    assert by_level[0.3]["active_set"] == GLOBALLY_INTERIOR
    for F in (0.1, 0.03, 0.01, 0.003, 0.001):
        assert by_level[F]["active_set"] == BOUNDARY_ACTIVE
    assert by_level[0.1]["switch_time_years"]["value"] == pytest.approx(39.0572, rel=1e-4)


def test_eco03_values_match_the_independent_expectations(report_eco03):
    for row, expected in zip(report_eco03["constrained_rows"], ECO03_V, strict=True):
        assert row["successor_marginal_value_V_e"] == pytest.approx(expected, abs=1e-9)


def test_eco03_main_reference_is_robustly_interior(report_eco03):
    reference = report_eco03["main_interior_reference"]
    assert reference["prefunding_level_F"] == 0.3
    assert reference["active_set"] == GLOBALLY_INTERIOR
    assert reference["minimum_transfer_margin"] == pytest.approx(MARGIN_AT_03, abs=1e-9)
    assert reference["requirement"] == 0.005
    assert reference["verdict"] == "robustly_interior"
    # The verdict must be earned by a margin that clears the requirement by more than
    # the credible error, not merely by exceeding it.
    assert reference["minimum_transfer_margin"] - reference["credible_error"] > 0.005


def test_an_interiority_margin_inside_its_own_error_is_indistinguishable():
    """The verdict logic must degrade honestly, not round up to a pass."""
    margin, requirement = 0.005 + 1e-12, 0.005
    for error, expected in ((1e-15, "robustly_interior"), (1e-9, "indistinguishable")):
        verdict = ("robustly_interior" if margin - error > requirement
                   else "below_requirement" if margin + error < requirement
                   else "indistinguishable")
        assert verdict == expected


def test_globally_interior_rows_use_an_explicit_no_switch_status(report_eco03):
    for row in report_eco03["constrained_rows"]:
        if row["active_set"] == GLOBALLY_INTERIOR:
            assert row["switch_time_years"] == {"kind": "undefined", "value": None}
            assert row["minimum_transfer_margin"] is not None


# --- rho is the only changed primitive ---------------------------------------------------


def test_eco03_leaves_every_price_and_owner_object_unchanged():
    """rho enters neither the successor price equations nor the owner portfolio
    condition, so disagreement is an implementation or configuration failure."""
    from tai_public_finance.cs012_poisson_kernels.i1_owner_branch import (
        build_payoffs, solve_owner_branch,
    )
    from tai_public_finance.cs012_poisson_kernels.i1_packets import load_economic_packet
    from tai_public_finance.cs012_poisson_kernels.i1_successors import (
        MARK_F, MARK_P, model_parameters, solve_successors,
    )

    from .conftest import ECO_02, ECO_03

    results = {}
    for tag, path in (("02", ECO_02), ("03", ECO_03)):
        packet = load_economic_packet(path)
        services = solve_successors(
            model_parameters(packet), packet.ak_root_interval, packet.partial_capital_interval
        )
        payoffs = build_payoffs(
            packet.q_0,
            ((MARK_P, services.q_P(1.0)), (MARK_F, services.q_F())),
            {MARK_P: (packet.lambda_P, packet.lambda_P_star),
             MARK_F: (packet.lambda_F, packet.lambda_F_star)},
        )
        branch = solve_owner_branch(tag, 1.0, packet.q_0, payoffs, packet.a_0)
        results[tag] = {
            "q_0": packet.q_0, "q_P": services.q_P(1.0), "q_F": services.q_F(),
            "J": [m.payoff_jump for m in branch.marks],
            "k_world": [m.k_world for m in branch.marks],
            "exposure": branch.exposure,
            "k_owner": [m.k_owner for m in branch.marks],
        }
    a, b = results["02"], results["03"]
    for key in ("q_0", "q_P", "q_F", "exposure"):
        assert abs(a[key] - b[key]) <= 1e-12, key
    for key in ("J", "k_world", "k_owner"):
        for x, y in zip(a[key], b[key], strict=True):
            assert abs(x - y) <= 1e-12, key


def test_eco03_differs_from_eco02_in_rho_alone():
    import json

    from .conftest import ECO_02, ECO_03

    first = json.loads(ECO_02.read_text(encoding="utf-8"))
    second = json.loads(ECO_03.read_text(encoding="utf-8"))
    for prose in ("provenance", "limits"):
        first.pop(prose), second.pop(prose)
    differences: list[str] = []

    def walk(x, y, path=""):
        if isinstance(x, dict):
            for key in sorted(set(x) | set(y)):
                walk(x.get(key), y.get(key), f"{path}/{key}")
        elif x != y:
            differences.append(path)

    walk(first, second)
    assert differences == ["/packet_id", "/preferences/rho"]
    assert second["preferences"]["rho"] == 0.03
    assert second["technology"]["A_bar"] == 0.10329029481590953
    assert second["world_rates"]["r_P_bar"] == 0.030
    assert second["world_rates"]["r_F_bar"] == 0.030


# --- full AK and the unsafe helper --------------------------------------------------------


def test_full_ak_identities_are_unchanged_and_exact(report_eco02):
    rho = report_eco02["rho"]
    for row in report_eco02["full_ak_rows"]:
        F = row["prefunding_level_F"]
        assert row["wage_floor"] == 0.0
        assert row["worker_consumption_C_0"] == pytest.approx(rho * F, rel=1e-15)
        assert row["successor_marginal_value_V_e"] == pytest.approx(1.0 / (rho * F), rel=1e-14)
    for elasticity in report_eco02["full_ak_elasticities"]:
        assert elasticity == pytest.approx(-1.0, abs=1e-12)


def test_the_unrestricted_helper_now_labels_itself_a_relaxation():
    from tai_public_finance.cs012_poisson_kernels.i2_prefunding import (
        unrestricted_upper_relaxation_row,
    )

    exact = unrestricted_upper_relaxation_row("F", 1.0, 0.04, 1.0, 1.0, wage_floor=0.0)
    assert exact.is_exact and exact.relaxation_label == "exact_zero_wage_floor"
    relaxed = unrestricted_upper_relaxation_row("P", 1.0, 0.04, 6.0, 1.0, wage_floor=0.13)
    assert not relaxed.is_exact
    assert relaxed.relaxation_label == "unrestricted_upper_relaxation"


def test_boundary_marginal_value_is_one_over_the_initial_wage():
    path = _constant_wage_path(0.03, 0.2)
    assert boundary_marginal_value(path).require_finite() == pytest.approx(1.0 / 0.2, rel=1e-15)
    zero_wage = _constant_wage_path(0.03, 0.0)
    assert boundary_marginal_value(zero_wage).kind == "positive_infinity"
