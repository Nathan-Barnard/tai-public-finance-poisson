"""P-CS012-ECO-02: a parameter-only rerun at higher full-AK productivity.

ECO-02 differs from ECO-01 in exactly one primitive, ``technology.A_bar``. Nothing in
the successor equations, root solver, owner FOC, partial manifold, or kernel formulas
changed; the only code change was widening the loader's recognized packet-id set from
one name to a closed set of two.

The economics that changed is worth stating, because it is why the packet exists. Under
ECO-01 the full-AK mark *lowered* installed-equity value (``J_F < 0``) while the partial
mark raised it, and the owner took a large levered long position. Under ECO-02 the
higher ``A_bar`` puts full-AK growth above partial growth, both payoffs turn positive,
and the owner's optimal exposure flips sign to a short position.
"""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from tai_public_finance.cs012_poisson_kernels.i1_owner_branch import (
    build_payoffs,
    solve_owner_branch,
)
from tai_public_finance.cs012_poisson_kernels.i1_packets import (
    ECONOMIC_PACKET_IDS,
    PacketError,
    load_economic_packet,
)
from tai_public_finance.cs012_poisson_kernels.i1_successors import (
    MARK_F,
    MARK_P,
    model_parameters,
    solve_successors,
)
from tai_public_finance.cs012_poisson_kernels.report_i1 import build_i1_report

from .conftest import (
    ECONOMIC_CONFIG,
    ECONOMIC_CONFIG_02,
    SYNTHETIC_CONFIG,
    TEST_PROVENANCE,
)

# Independent expectations supplied with the dispatch. Cross-checks, not targets.
EXPECTED = {
    "q_0": 1.1972173631218102,
    "q_P": 1.291347709765447,
    "g_P": 0.02522880308958336,
    "q_F": 1.2943388186242377,
    "g_F": 0.026,
    "J_P": 0.07862427454124687,
    "J_F": 0.08112265867008306,
    "q_F_upper": 1.3256524605639481,
    "g_F_upper": 0.03396825376828801,
    "pi_owner": -4.7887390064,
}
A_BAR_01 = 0.10
A_BAR_02 = 0.10329029481590953


def _growth(q: float, varphi: float, delta: float) -> float:
    return math.log(q) / varphi - delta


# --- packet identity and the closed recognized set -------------------------------------


def test_eco02_loads(economic_packet_02):
    assert economic_packet_02.packet_id == "P-CS012-ECO-02"
    assert economic_packet_02.packet_kind == "provisional_illustrative_economic_scenario"
    assert economic_packet_02.A_bar == A_BAR_02


def test_the_two_economic_packets_have_different_operative_fingerprints(
    economic_packet, economic_packet_02
):
    assert economic_packet.fingerprint != economic_packet_02.fingerprint


def test_the_operative_difference_is_exactly_packet_identity_and_A_bar(
    economic_packet, economic_packet_02
):
    """Prose is excluded from the operative fields by construction, so this compares
    everything the calculation can actually see."""
    first = economic_packet.direct_fields()
    second = economic_packet_02.direct_fields()
    differences: list[str] = []

    def walk(a, b, path=""):
        if isinstance(a, dict):
            for key in sorted(set(a) | set(b)):
                walk(a.get(key), b.get(key), f"{path}/{key}")
        elif a != b:
            differences.append(path)

    walk(first, second)
    assert differences == ["/packet_id", "/technology/A_bar"]
    assert first["technology"]["A_bar"] == A_BAR_01
    assert second["technology"]["A_bar"] == A_BAR_02


@pytest.mark.parametrize(
    "bad_id",
    [
        "P-CS012-ECO-04",
        "P-CS012-ECO-1",
        "P-CS012-EC0-02",
        "p-cs012-eco-02",
        "P-CS012-ECO-02 ",
        "ECO-02",
        "",
    ],
)
def test_unrecognized_or_misspelled_packet_ids_stay_rejected(tmp_path, bad_id):
    payload = json.loads(ECONOMIC_CONFIG_02.read_text(encoding="utf-8"))
    payload["packet_id"] = bad_id
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PacketError, match="expected one of"):
        load_economic_packet(path)


def test_the_recognized_set_is_closed_and_enumerated():
    assert ECONOMIC_PACKET_IDS == (
        "P-CS012-ECO-01",
        "P-CS012-ECO-02",
        "P-CS012-ECO-03",
    )


def test_malformed_packet_rejection_is_not_weakened(tmp_path):
    """Widening the id set must not have loosened any other structural check."""
    base = json.loads(ECONOMIC_CONFIG_02.read_text(encoding="utf-8"))
    for mutate, match in (
        (lambda p: p["shock_law"].update({"lambda_P": 0.02}), "contradicts"),
        (lambda p: p["shock_law"].update({"p_P": 0.7}), "sum to one"),
        (lambda p: p["technology"].update({"I_P": 0.2}), "0 < I_0 < I_P < 1"),
        (lambda p: p["inherited_state"].update({"public_safe_asset": 1.0}), "must be zero"),
        (lambda p: p["inherited_state"].update({"M_0": "something"}), "one-time-protection"),
        (lambda p: p["inherited_state"].update({"q_0_rule": "1.2"}), "exp\\(varphi\\*delta\\)"),
        (lambda p: p["diagnostics"].update({"baseline_capital": 9.0}), "baseline capital"),
        (lambda p: p["shock_law"].update({"lambda_P_star": -0.01}), "nonnegative"),
    ):
        payload = json.loads(json.dumps(base))
        mutate(payload)
        path = tmp_path / "malformed.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(PacketError, match=match):
            load_economic_packet(path)


# --- A_bar propagates through the existing calculation ---------------------------------


def test_A_bar_propagates_rather_than_being_a_hard_coded_expectation(economic_packet_02):
    """The solved AK price must track the analytic inverse of the user-cost equation
    across a range of A_bar, not just at the two frozen values.

    ``A_bar = q(r_F_bar - g(q)) + (q-1)/varphi`` is inverted here by solving for the
    price the packet's own A_bar implies, and compared against what the production
    successor service returns. Agreement at one point could be a coincidence or a
    constant; agreement across a swept range cannot.
    """
    varphi, delta = economic_packet_02.varphi, economic_packet_02.delta
    rF = economic_packet_02.r_F_bar

    def implied_A_bar(g_target: float) -> float:
        q = math.exp(varphi * (g_target + delta))
        return q * (rF - g_target) + (q - 1.0) / varphi

    previous_q = None
    for g_target in (0.0, 0.005, 0.010, 0.018, 0.026, 0.028):
        A_bar = implied_A_bar(g_target)
        packet = dataclasses.replace(economic_packet_02, A_bar=A_bar)
        services = solve_successors(
            model_parameters(packet),
            packet.ak_root_interval,
            packet.partial_capital_interval,
        )
        q_F = services.q_F()
        assert _growth(q_F, varphi, delta) == pytest.approx(g_target, abs=1e-9)
        assert q_F == pytest.approx(math.exp(varphi * (g_target + delta)), rel=1e-11)
        if previous_q is not None:
            # Strictly increasing in A_bar: the mapping is not a constant.
            assert q_F > previous_q
        previous_q = q_F

    # And the two frozen packets sit on that same curve at different points.
    assert implied_A_bar(0.026) == pytest.approx(A_BAR_02, rel=1e-15)
    assert A_BAR_01 != A_BAR_02


# --- ECO-02 baseline -------------------------------------------------------------------


def test_the_eco02_baseline_matches_the_independent_expectations(
    economic_packet_02, services_02
):
    varphi, delta = economic_packet_02.varphi, economic_packet_02.delta
    q_0 = economic_packet_02.q_0
    q_P = services_02.q_P(1.0)
    q_F = services_02.q_F()

    assert q_0 == pytest.approx(EXPECTED["q_0"], abs=1e-14)
    assert q_P == pytest.approx(EXPECTED["q_P"], abs=1e-12)
    assert q_F == pytest.approx(EXPECTED["q_F"], abs=1e-12)
    assert _growth(q_P, varphi, delta) == pytest.approx(EXPECTED["g_P"], abs=1e-12)
    assert _growth(q_F, varphi, delta) == pytest.approx(EXPECTED["g_F"], abs=1e-12)
    assert economic_packet_02.r_F_bar - _growth(q_F, varphi, delta) == pytest.approx(
        0.004, abs=1e-11
    )
    assert q_P / q_0 - 1.0 == pytest.approx(EXPECTED["J_P"], abs=1e-12)
    assert q_F / q_0 - 1.0 == pytest.approx(EXPECTED["J_F"], abs=1e-12)


def test_the_required_growth_and_price_orderings_hold(economic_packet_02, services_02):
    varphi, delta = economic_packet_02.varphi, economic_packet_02.delta
    q_0, q_P, q_F = economic_packet_02.q_0, services_02.q_P(1.0), services_02.q_F()
    g_0 = _growth(q_0, varphi, delta)
    assert g_0 == pytest.approx(0.0, abs=1e-15)
    assert _growth(q_F, varphi, delta) > _growth(q_P, varphi, delta) > g_0
    assert q_F > q_P > q_0


def test_exactly_one_ak_root_is_accepted_and_the_upper_root_is_retained(
    economic_packet_02, services_02
):
    varphi, delta = economic_packet_02.varphi, economic_packet_02.delta
    candidates = services_02.ak.candidates
    assert len(candidates) == 2
    accepted = [c for c in candidates if c.accepted]
    rejected = [c for c in candidates if not c.accepted]
    assert len(accepted) == 1 and len(rejected) == 1
    assert accepted[0].branch == "lower_strict_tvc"
    assert accepted[0].tvc_margin > 0.0
    assert accepted[0].tvc_margin == pytest.approx(0.004, abs=1e-11)
    assert rejected[0].branch == "upper_tvc_violating"
    assert rejected[0].reason == "productive_value_tvc_violated"
    assert rejected[0].tvc_margin < 0.0
    assert rejected[0].q == pytest.approx(EXPECTED["q_F_upper"], abs=1e-10)
    assert _growth(rejected[0].q, varphi, delta) == pytest.approx(
        EXPECTED["g_F_upper"], abs=1e-10
    )
    # The two branches are separated by the analytic minimiser, not by sorting.
    assert accepted[0].q < rejected[0].q


def test_the_owner_exposure_flips_to_an_interior_short_position(
    economic_packet_02, services_02
):
    q_0 = economic_packet_02.q_0
    payoffs = build_payoffs(
        q_0,
        ((MARK_P, services_02.q_P(1.0)), (MARK_F, services_02.q_F())),
        {
            MARK_P: (economic_packet_02.lambda_P, economic_packet_02.lambda_P_star),
            MARK_F: (economic_packet_02.lambda_F, economic_packet_02.lambda_F_star),
        },
    )
    branch = solve_owner_branch("eco02", 1.0, q_0, payoffs, economic_packet_02.a_0)
    assert branch.exposure == pytest.approx(EXPECTED["pi_owner"], abs=1e-9)
    assert branch.exposure < 0.0
    assert branch.interval.contains(branch.exposure)
    # Both payoffs are now positive, so the admissible interval is unbounded above.
    assert branch.interval.lower_is_finite and not branch.interval.upper_is_finite
    for mark in branch.marks:
        assert mark.payoff_jump > 0.0
        assert mark.wealth_multiplier > 0.0
        assert mark.owner_wealth_after > 0.0
    assert abs(branch.residual_at_root) <= 1e-10
    assert branch.independent_exposure_residual <= 1e-10
    assert branch.independent_kernel_max_error <= 1e-10
    assert branch.independent_d_owner_error <= 1e-10


def test_the_sign_of_the_owner_position_reverses_between_the_two_packets(
    i1_report, i1_report_02
):
    """The economically substantive difference the parameter change produces."""
    assert i1_report["economic"]["baseline"]["exposure"] > 0.0
    assert i1_report_02["economic"]["baseline"]["exposure"] < 0.0
    assert i1_report["economic"]["baseline"]["marks"][1]["payoff_jump"] < 0.0
    assert i1_report_02["economic"]["baseline"]["marks"][1]["payoff_jump"] > 0.0


def test_no_eco02_economic_row_is_quarantined(i1_report_02):
    economic = i1_report_02["economic"]
    assert economic["counts"]["quarantined_rows"] == 0
    assert economic["quarantined_rows"] == []
    assert economic["counts"]["valid_rows"] == economic["counts"]["grid_rows"] == 5
    assert economic["counts"]["ak_roots_enumerated"] == 2
    assert economic["counts"]["ak_roots_accepted"] == 1


def test_every_eco02_economic_quantity_is_finite(i1_report_02):
    def walk(value, path=""):
        if isinstance(value, float):
            assert math.isfinite(value), path
        elif isinstance(value, dict):
            for key, item in value.items():
                walk(item, f"{path}/{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")

    walk(i1_report_02["economic"])
    json.loads(json.dumps(i1_report_02, allow_nan=False))


# --- containment of the quarantined synthetic subsection --------------------------------


def test_the_economic_section_is_structurally_independent_of_the_synthetic_packet():
    """Structural evidence: the economic builder takes only the economic packet.

    ``P-CS012-SYN-01`` carries a known provenance defect -- it describes
    ``manufactured-two-mark`` as stationary-compatible, while the pinned dependency
    calls that fixture an arbitrary probe -- so the synthetic subsection of this run is
    quarantined. Nothing in the economic result may depend on it.
    """
    import inspect

    from tai_public_finance.cs012_poisson_kernels import report_i1

    signature = inspect.signature(report_i1._economic_scenario)
    assert list(signature.parameters) == ["packet", "tolerances"]
    source = inspect.getsource(report_i1._economic_scenario)
    for name in ("synthetic", "fixture", "SYN", "get_fixture"):
        assert name not in source, name


def test_the_economic_section_is_byte_identical_under_a_different_synthetic_packet(tmp_path):
    """Behavioural evidence: swap the synthetic packet for one naming a different
    primary fixture and a different regression set; the economic section must not move."""
    payload = json.loads(SYNTHETIC_CONFIG.read_text(encoding="utf-8"))
    payload["primary_fixture"] = "manufactured-single-ak-support"
    payload["regression_fixtures"] = ["manufactured-single-ak-support"]
    alternative = tmp_path / "P-CS012-SYN-01.json"
    alternative.write_text(json.dumps(payload), encoding="utf-8")

    first = build_i1_report(SYNTHETIC_CONFIG, ECONOMIC_CONFIG_02, TEST_PROVENANCE, 0.0)
    second = build_i1_report(alternative, ECONOMIC_CONFIG_02, TEST_PROVENANCE, 0.0)

    assert first["synthetic"] != second["synthetic"], "the synthetic sections should differ"
    assert json.dumps(first["economic"], sort_keys=True) == json.dumps(
        second["economic"], sort_keys=True
    )


def test_eco01_artifacts_are_untouched_by_this_rerun(economic_packet):
    """ECO-01 keeps its own fingerprint and its own A_bar."""
    assert economic_packet.packet_id == "P-CS012-ECO-01"
    assert economic_packet.A_bar == A_BAR_01
    assert economic_packet.fingerprint == (
        "7524e29731dcfe46d6e18d6e129f72b0bbd8f7c4d7374b20c7e03b06b7fc4c2f"
    )
