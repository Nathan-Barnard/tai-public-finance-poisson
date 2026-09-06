"""CS012 I2a: literal boundary, prefunding family, asymptote, SYN-02, closure gate."""

from __future__ import annotations

import json
import math

import pytest

from tai_public_finance.cs012_poisson_kernels.extended import ExtendedRealError
from tai_public_finance.cs012_poisson_kernels.i1_packets import PacketError
from tai_public_finance.cs012_poisson_kernels.i2_packets import (
    load_analytic_fixture,
    load_prefunding_packet,
)
from tai_public_finance.cs012_poisson_kernels.i2_prefunding import (
    MU_E_UNAVAILABLE,
    PrefundingError,
    adjacent_log_log_elasticities,
    audit_mu_e_closure,
    literal_boundary,
    unrestricted_upper_relaxation_row,
)

from .conftest import PREFUND, SYN_02

RHO = 0.04
FROZEN = (1.0, 0.3, 0.1, 0.03, 0.01, 0.003, 0.001)
EXPECTED_V_F = {
    1.0: 25.0, 0.3: 250.0 / 3.0, 0.1: 250.0, 0.03: 2500.0 / 3.0,
    0.01: 2500.0, 0.003: 25000.0 / 3.0, 0.001: 25000.0,
}


# --- packets ---------------------------------------------------------------------------


def test_the_prefunding_packet_is_bound_to_eco02_by_fingerprint(prefunding_packet, eco02):
    assert prefunding_packet.bound_packet_id == "P-CS012-ECO-02"
    assert prefunding_packet.bound_packet_fingerprint == eco02.fingerprint
    assert prefunding_packet.prefunding_ratios == FROZEN
    assert prefunding_packet.levels() == FROZEN  # a_0 = 1 is the named scale
    assert prefunding_packet.public_installed_equity == 0.0
    assert prefunding_packet.source_tax == 0.0


def test_zero_is_never_a_member_of_the_finite_sequence(tmp_path):
    payload = json.loads(PREFUND.read_text(encoding="utf-8"))
    payload["prefunding_ratio_sequence"] = [1.0, 0.3, 0.0]
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PacketError, match="strictly positive"):
        load_prefunding_packet(path)


def test_the_safe_debt_sign_convention_is_negative_for_inherited_wealth(prefunding_packet):
    for F in prefunding_packet.levels():
        assert prefunding_packet.safe_debt(F) == -F < 0.0


# --- full-AK asymptote -----------------------------------------------------------------


@pytest.mark.parametrize("F", FROZEN)
def test_full_ak_levels_match_the_closed_form(F, services, eco02):
    q_F, K = services.q_F(), 1.0
    row = unrestricted_upper_relaxation_row("F", F, RHO, q_F * K, q_F * K, wage_floor=0.0)
    assert row.worker_resources == pytest.approx(F, rel=1e-15)
    assert row.worker_consumption == pytest.approx(0.04 * F, rel=1e-14)
    assert row.successor_marginal_value == pytest.approx(EXPECTED_V_F[F], rel=1e-12)
    assert row.successor_marginal_value == pytest.approx(25.0 / F, rel=1e-12)


def test_the_full_ak_elasticity_is_minus_one_everywhere(services):
    q_F = services.q_F()
    values = tuple(unrestricted_upper_relaxation_row("F", F, RHO, q_F, q_F, wage_floor=0.0).successor_marginal_value
                   for F in FROZEN)
    for value in adjacent_log_log_elasticities(FROZEN, values):
        assert value == pytest.approx(-1.0, abs=1e-12)


def test_the_partial_elasticity_approaches_zero_not_minus_one(services):
    K, q_P = 1.0, services.q_P(1.0)
    H_P = services.partial.H_P(K)
    values = tuple(unrestricted_upper_relaxation_row("P", F, RHO, H_P, q_P * K, wage_floor=0.0).successor_marginal_value
                   for F in FROZEN)
    elasticities = adjacent_log_log_elasticities(FROZEN, values)
    assert all(-1.0 < e < 0.0 for e in elasticities)
    assert abs(elasticities[-1]) < abs(elasticities[0])
    assert abs(elasticities[-1]) < 1e-3
    assert elasticities[-1] != pytest.approx(-1.0, abs=0.5)


def test_both_H_P_routes_agree_at_the_baseline(services):
    K = 1.0
    quadrature, algebraic = services.partial.H_P(K), services.partial.H_P_algebraic(K)
    assert quadrature == pytest.approx(6.15844571561235, abs=1e-9)
    assert abs(quadrature - algebraic) < 1e-8
    assert quadrature - services.q_P(K) * K == pytest.approx(4.867098005846903, abs=1e-9)


# --- literal boundary ------------------------------------------------------------------


def test_the_literal_boundary_is_an_exact_tagged_extended_real():
    boundary = literal_boundary(RHO, 4.867098005846903)
    assert boundary.status == "nonfinite_fiscal_kernel_at_literal_laissez_faire"
    assert boundary.worker_consumption.require_finite() == 0.0
    assert boundary.successor_marginal_value.kind == "positive_infinity"
    with pytest.raises(ExtendedRealError):
        boundary.successor_marginal_value.require_finite()
    payload = boundary.as_dict()
    text = json.dumps(payload, allow_nan=False)
    assert "Infinity" not in text and "NaN" not in text
    json.loads(text, parse_constant=lambda c: pytest.fail(f"non-standard token {c}"))


def test_the_partial_branch_stays_finite_at_the_boundary():
    boundary = literal_boundary(RHO, 4.867098005846903)
    assert boundary.partial_successor_marginal_value.kind == "finite"
    assert boundary.partial_successor_marginal_value.require_finite() == pytest.approx(
        1.0 / (RHO * 4.867098005846903), rel=1e-14
    )
    assert "structurally different" in boundary.contrast


def test_no_code_path_regularizes_the_literal_boundary():
    """F = 0 must be refused by the finite row builder, never floored or epsilon-ed."""
    with pytest.raises(PrefundingError, match="strictly positive F"):
        unrestricted_upper_relaxation_row("F", 0.0, RHO, 1.0, 1.0, wage_floor=0.0)
    with pytest.raises(PrefundingError, match="strictly positive F"):
        unrestricted_upper_relaxation_row("F", -1e-30, RHO, 1.0, 1.0, wage_floor=0.0)
    # And a log-log calculation refuses a zero point rather than dropping it.
    with pytest.raises(PrefundingError, match="strictly positive points"):
        adjacent_log_log_elasticities((1.0, 0.0), (1.0, 2.0))


def test_non_positive_worker_resources_are_refused_not_floored():
    with pytest.raises(PrefundingError, match="not strictly positive"):
        unrestricted_upper_relaxation_row("P", 0.001, RHO, 1.0, 5.0, wage_floor=0.0)


# --- SYN-02 ----------------------------------------------------------------------------


def test_syn02_is_genuinely_stationary_compatible(analytic_fixture):
    assert analytic_fixture.r_F_bar == pytest.approx(0.06, abs=1e-15)
    assert analytic_fixture.q_F == pytest.approx(1.2712491503214047, abs=1e-15)
    assert analytic_fixture.A_bar == pytest.approx(0.14126634945332445, abs=1e-15)
    assert analytic_fixture.implied_growth == pytest.approx(0.02, abs=1e-15)
    assert abs(analytic_fixture.stationary_residual) <= 1e-15
    assert analytic_fixture.tvc_margin == pytest.approx(0.04, abs=1e-15)
    assert abs(analytic_fixture.user_cost_residual()) <= 1e-12


def test_syn02_is_a_direct_construction_not_a_dependency_fixture(analytic_fixture):
    assert analytic_fixture.packet_kind == "directly_constructed_analytic_fixture"
    assert analytic_fixture.fixture_scope == "full_ak_pure_safe_fund_benchmark"
    text = (analytic_fixture.provenance + analytic_fixture.limits).lower()
    assert "does not come from" in text
    assert "two-mark" in text or "two mark" in text  # explicitly disclaimed
    assert "no economic interpretation" in text


@pytest.mark.parametrize(
    "mutate",
    [
        # Perturb a primitive: the stated expectations no longer match the rules.
        lambda p: p.update({"target_growth_g": 0.03}),
        lambda p: p.update({"preferences": {"rho": 0.05}}),
        lambda p: p.update({"installation": {"varphi": 3.0, "delta": 0.07}}),
        lambda p: p.update({"installation": {"varphi": 3.5, "delta": 0.06}}),
        # Perturb a stated identity: it no longer matches the derived rules.
        lambda p: p["analytic_expectations"].update({"q_F": 1.28}),
        lambda p: p["analytic_expectations"].update({"A_bar": 0.15}),
        lambda p: p["analytic_expectations"].update({"r_F_bar": 0.07}),
        lambda p: p["analytic_expectations"].update({"implied_growth": 0.021}),
        lambda p: p["analytic_expectations"].update({"stationary_residual": 0.001}),
        lambda p: p["analytic_expectations"].update({"productive_tvc_margin": 0.05}),
    ],
)
def test_syn02_fails_if_any_stationary_identity_is_perturbed(tmp_path, mutate):
    """Stated and derived representations pin each other.

    Deriving alone would make the fixture unfalsifiable: editing a primitive would
    silently yield a new, still self-consistent fixture. Stating alone would let the
    numbers drift from the rules. Requiring agreement is what makes perturbation
    detectable at all.
    """
    payload = json.loads(SYN_02.read_text(encoding="utf-8"))
    mutate(payload)
    path = tmp_path / "perturbed.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PacketError):
        load_analytic_fixture(path)


def test_syn02_rejects_a_claim_of_dependency_origin(tmp_path):
    payload = json.loads(SYN_02.read_text(encoding="utf-8"))
    payload["construction"] = "from_dependency_fixture"
    path = tmp_path / "borrowed.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PacketError, match="directly constructed"):
        load_analytic_fixture(path)


# --- closure gate ----------------------------------------------------------------------


def test_the_closure_audit_finds_no_optimized_pre_event_mu_e():
    audit = audit_mu_e_closure()
    assert audit.status == MU_E_UNAVAILABLE
    assert audit.government_kernels_permitted is False
    assert audit.missing_object.startswith("mu_e(")
    assert "N4" in audit.missing_interface
    evidence = " ".join(audit.evidence)
    assert "EQUATIONS only" in evidence
    assert "caller-supplied" in evidence


def test_the_audit_names_every_forbidden_substitute():
    from tai_public_finance.cs012_poisson_kernels.i2_prefunding import (
        FORBIDDEN_MU_E_SUBSTITUTES,
    )

    joined = " ".join(FORBIDDEN_MU_E_SUBSTITUTES).lower()
    for banned in ("mu_e = 1", "1/c_0", "owner's kernel", "world kernel",
                   "fixed-policy", "unpinned"):
        assert banned in joined


def test_no_government_kernel_is_reported_anywhere(i2_report):
    assert i2_report["government_kernels"]["reported"] is False
    assert i2_report["government_kernels"]["k_government"] is None
    assert i2_report["government_kernels"]["gamma"] is None
    economic = json.dumps(i2_report["economic_scenario"])
    for forbidden in ("k_government", "gamma", "mu_e", "government_kernel"):
        assert forbidden not in economic


def test_successor_marginal_values_cannot_be_relabelled_as_government_kernels(i2_report):
    """The field name carries the distinction, and the limits state it."""
    for section in ("partial_rows", "full_rows"):
        for row in i2_report["economic_scenario"][section]:
            assert "successor_marginal_value_V_e" in row
            assert not any("kernel" in key for key in row)
    limits = " ".join(i2_report["interpretation_limits"])
    assert "NOT a government kernel" in limits


# --- report shape ----------------------------------------------------------------------


def test_the_report_is_strict_json_and_finite_where_it_must_be(i2_report):
    text = json.dumps(i2_report, allow_nan=False)
    assert "Infinity" not in text and "NaN" not in text
    json.loads(text, parse_constant=lambda c: pytest.fail(f"non-standard token {c}"))
    for section in ("partial_rows", "full_rows"):
        for row in i2_report["economic_scenario"][section]:
            for key, value in row.items():
                if isinstance(value, float):
                    assert math.isfinite(value), f"{section}/{key}"


def test_the_report_records_the_syn01_quarantine(i2_report):
    quarantine = i2_report["syn01_quarantine"]
    assert quarantine["packet_id"] == "P-CS012-SYN-01"
    assert quarantine["status"] == "quarantined"
    assert "false" in quarantine["defect"].lower()
    assert quarantine["replacement"] == "P-CS012-SYN-02"


def test_the_report_refuses_a_prefunding_packet_bound_to_another_scenario(tmp_path):
    from tai_public_finance.cs012_poisson_kernels.report_i2 import build_i2_report

    from .conftest import ECO_01, SYN_02, TEST_PROVENANCE

    with pytest.raises(RuntimeError, match="bound to"):
        build_i2_report(ECO_01, PREFUND, SYN_02, TEST_PROVENANCE, 0.0)
