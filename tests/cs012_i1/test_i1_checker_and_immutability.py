"""Standalone checker acceptance, corruption rejection, and deep immutability."""

from __future__ import annotations

import copy
import dataclasses
import json
import subprocess
import sys
from typing import Any

import pytest

from tai_public_finance.cs012_poisson_kernels.i1_owner_branch import (
    build_payoffs,
    solve_owner_branch,
)
from tai_public_finance.cs012_poisson_kernels.i1_successors import MARK_F, MARK_P

from .conftest import CHECKER_PATH, CS011_COMMIT


def test_the_checker_imports_no_production_or_dependency_module():
    source = CHECKER_PATH.read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            assert "tai_public_finance" not in stripped, stripped
            assert "ak_partial_ramsey" not in stripped, stripped
            assert "numpy" not in stripped and "scipy" not in stripped, stripped


def test_the_checker_accepts_the_generated_report(i1_report, checker):
    failures = checker.check_report(i1_report)
    assert failures.messages == []


def test_the_checker_script_runs_end_to_end(i1_report, tmp_path):
    path = tmp_path / "identity_report.json"
    path.write_text(json.dumps(i1_report, indent=2, allow_nan=False), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(CHECKER_PATH), str(path)], capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "OK: independent reconstruction agrees" in completed.stdout
    assert CS011_COMMIT in completed.stdout


def _corrupt(report: dict, mutate) -> dict:
    corrupted = copy.deepcopy(report)
    mutate(corrupted)
    return corrupted


def _baseline(report: dict) -> dict:
    return report["economic"]["baseline"]


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        # --- the five corruptions the acceptance list names explicitly ------------
        ("payoff", lambda r: _baseline(r)["marks"][0].update({"payoff_jump": 0.2})),
        (
            "wealth_multiplier",
            lambda r: _baseline(r)["marks"][1].update({"wealth_multiplier": 1.4}),
        ),
        (
            "root_status",
            lambda r: _baseline(r).update({"root_status": "no_interior_root_boundary_limit"}),
        ),
        (
            "dependency_commit",
            lambda r: r["provenance"]["cs011_dependency"]["resolved"].update(
                {"commit_id": "0" * 40}
            ),
        ),
        (
            "config_fingerprint",
            lambda r: r["economic"]["packet"].update({"fingerprint": "0" * 64}),
        ),
        # --- further corruptions the report must not survive ----------------------
        ("exposure", lambda r: _baseline(r).update({"exposure": 11.5})),
        ("k_world", lambda r: _baseline(r)["marks"][0].update({"k_world": 0.5})),
        ("k_owner", lambda r: _baseline(r)["marks"][0].update({"k_owner": 0.5})),
        (
            "owner_wealth_after",
            lambda r: _baseline(r)["marks"][0].update({"owner_wealth_after": 2.0}),
        ),
        (
            "d_owner_contribution",
            lambda r: _baseline(r)["marks"][1].update({"d_owner_contribution": 1e-3}),
        ),
        ("d_owner", lambda r: _baseline(r).update({"d_owner": 1.0})),
        (
            "ak_selected_root",
            lambda r: r["economic"]["ak_successor"].update({"selected_q_F": 1.4748268544257426}),
        ),
        (
            "ak_branch_label",
            lambda r: r["economic"]["ak_successor"]["candidates"][1].update(
                {"branch": "lower_strict_tvc"}
            ),
        ),
        (
            "ak_acceptance",
            lambda r: r["economic"]["ak_successor"]["candidates"][1].update({"accepted": True}),
        ),
        (
            "ak_rejected_root_dropped",
            lambda r: r["economic"]["ak_successor"].update(
                {"candidates": [r["economic"]["ak_successor"]["candidates"][0]]}
            ),
        ),
        (
            "certified_domain_shrunk",
            lambda r: r["economic"]["partial_successor"].update(
                {"certified_domain": [0.8, 1.2]}
            ),
        ),
        (
            "ivp_bvp_diagnostic",
            lambda r: r["economic"]["partial_successor"]["independent_route_diagnostics"].update(
                {"max_ivp_bvp_difference": 1.0}
            ),
        ),
        (
            "grid_row_count",
            lambda r: r["economic"]["counts"].update({"valid_rows": 99}),
        ),
        (
            "reported_maximum",
            lambda r: r["economic"]["maxima"].update({"max_owner_root_residual": 0.0}),
        ),
        ("result_use", lambda r: r.update({"result_use": "decision_grade"})),
        ("specification_hash", lambda r: r["specification"].update({"sha256": "0" * 64})),
        ("deviation_dropped", lambda r: r.update({"deviations": []})),
        (
            "government_flag",
            lambda r: r["economic"].update({"government_objects_present": True}),
        ),
        (
            "mark_order",
            lambda r: _baseline(r).update({"marks": list(reversed(_baseline(r)["marks"]))}),
        ),
        (
            "intensity_swap",
            lambda r: _baseline(r)["marks"][0].update(
                {"lambda_physical": 0.014, "lambda_risk_neutral": 0.01625}
            ),
        ),
    ],
)
def test_the_checker_rejects_each_corruption(i1_report, checker, label, mutate):
    failures = checker.check_report(_corrupt(i1_report, mutate))
    assert failures.messages, f"the checker accepted a corrupted report: {label}"


def test_the_checker_script_exits_nonzero_on_a_corrupted_report(i1_report, tmp_path):
    corrupted = _corrupt(i1_report, lambda r: _baseline(r)["marks"][0].update({"k_world": 9.0}))
    path = tmp_path / "corrupted.json"
    path.write_text(json.dumps(corrupted, indent=2, allow_nan=False), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(CHECKER_PATH), str(path)], capture_output=True, text=True
    )
    assert completed.returncode == 1
    assert "FAILED" in completed.stdout


# --- deep immutability ----------------------------------------------------------------

IMMUTABLE_SCALARS = (str, int, float, bool, type(None))


def _walk(value: Any, path: str, seen: set[int]) -> list[str]:
    if id(value) in seen:
        return []
    seen.add(id(value))
    if isinstance(value, IMMUTABLE_SCALARS):
        return []
    if isinstance(value, (list, dict, set, bytearray)):
        return [f"{path}: mutable {type(value).__name__}"]
    if type(value).__module__ == "numpy" or type(value).__name__ == "ndarray":
        return [f"{path}: numpy object {type(value).__name__}"]
    if isinstance(value, tuple):
        problems: list[str] = []
        for index, item in enumerate(value):
            problems.extend(_walk(item, f"{path}[{index}]", seen))
        return problems
    if dataclasses.is_dataclass(value):
        problems = []
        if not value.__dataclass_params__.frozen:
            problems.append(f"{path}: dataclass {type(value).__name__} is not frozen")
        for field in dataclasses.fields(value):
            problems.extend(_walk(getattr(value, field.name), f"{path}.{field.name}", seen))
        return problems
    return [f"{path}: unclassified object {type(value).__name__}"]


@pytest.fixture(scope="module")
def owner_branch(services, economic_packet):
    q_0 = economic_packet.q_0
    payoffs = build_payoffs(
        q_0,
        ((MARK_P, services.q_P(1.0)), (MARK_F, services.q_F())),
        {
            MARK_P: (economic_packet.lambda_P, economic_packet.lambda_P_star),
            MARK_F: (economic_packet.lambda_F, economic_packet.lambda_F_star),
        },
    )
    return solve_owner_branch("immutability", 1.0, q_0, payoffs, economic_packet.a_0)


def test_the_owner_branch_result_is_deeply_immutable(owner_branch):
    assert _walk(owner_branch, "owner_branch", set()) == []


def test_the_packets_are_deeply_immutable(economic_packet, synthetic_packet):
    assert _walk(economic_packet, "economic_packet", set()) == []
    assert _walk(synthetic_packet, "synthetic_packet", set()) == []


def test_public_results_reject_attribute_assignment(owner_branch, economic_packet):
    with pytest.raises(dataclasses.FrozenInstanceError):
        owner_branch.exposure = 0.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        owner_branch.marks[0].k_owner = 0.0
    with pytest.raises(dataclasses.FrozenInstanceError):
        economic_packet.rho = 0.05


def test_packet_direct_fields_cannot_be_mutated_through_a_result(economic_packet):
    first = economic_packet.direct_fields()
    first["preferences"]["rho"] = 99.0
    assert economic_packet.direct_fields()["preferences"]["rho"] == 0.04
    assert economic_packet.rho == 0.04


def test_the_packet_fingerprint_moves_with_every_operative_field(economic_packet):
    baseline = economic_packet.fingerprint
    for field, value in (
        ("rho", 0.041),
        ("varphi", 3.1),
        ("delta", 0.061),
        ("I_0", 0.23),
        ("I_P", 0.47),
        ("Z", 0.0213),
        ("A_bar", 0.11),
        ("r_0_bar", 0.026),
        ("r_P_bar", 0.031),
        ("r_F_bar", 0.031),
        ("lambda_total", 0.026),
        ("lambda_P_star", 0.015),
        ("lambda_F_star", 0.027),
        ("K_0", 1.1),
        ("a_0", 1.1),
        ("baseline_capital", 1.2),
    ):
        variant = dataclasses.replace(economic_packet, **{field: value})
        assert variant.fingerprint != baseline, field
    # Prose is excluded from the fingerprint.
    assert dataclasses.replace(economic_packet, provenance="different").fingerprint == baseline
    assert dataclasses.replace(economic_packet, limits="different").fingerprint == baseline
