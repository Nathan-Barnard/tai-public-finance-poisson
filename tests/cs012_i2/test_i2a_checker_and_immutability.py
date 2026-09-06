"""I2a standalone checker, corruption rejection, and prior-artifact immutability."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys

import pytest

from .conftest import CHECKER_PATH, CONFIGS, ECO_01, ECO_02, PREFUND, REPOSITORY, SYN_01

# Hashes recorded when the earlier blocks were accepted for review. These are the
# artifacts this block promised not to touch.
FROZEN_ARTIFACTS = {
    "configs/cs012/P-CS012-ECO-01.json":
        "bcdc33be61a801c3b84346893020e2d60249c33311b4a9e39f2d31ae644ccd03",
    "configs/cs012/P-CS012-ECO-02.json":
        "9d1c2ff7d30218d0b7fd2d284935360c4ec90511c1e022fcac49387b1c7b7940",
    "configs/cs012/P-CS012-SYN-01.json":
        "74cc08c122876593dab557c6c0626e906ef383eeb4e72ba3cbc0f98444895ba3",
    "outputs/cs012-i0-pricing-kernel-identities/identity_report.json":
        "2ce7e59d8174fd149cafa5e63b12945cb506ec8b7762f7e93c9d22a8c3b3bb78",
    "outputs/cs012-i1-provisional-owner-successors/identity_report.json":
        "e078541c1cc664e33573bf13af4078aef64561e5e7db9fe8b77922919982c349",
    "outputs/cs012-i1-provisional-owner-successors/summary.md":
        "3d4304af3788e75a9f76cc0138c0d2ffec3bc13896d417ea207318db10ba71ad",
    "outputs/cs012-i1-provisional-owner-successors-eco02/identity_report.json":
        "d9e70c606e49bb392570d0435aba9a420c994738f550097e181204fed583d4d3",
    "outputs/cs012-i1-provisional-owner-successors-eco02/summary.md":
        "421ed4299fc1c6f34fbe5d810a83b5333e43f984adef81504c7d7b72295250ad",
}


def test_every_prior_artifact_is_unchanged():
    for relative, expected in FROZEN_ARTIFACTS.items():
        path = REPOSITORY / relative
        assert path.exists(), relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == expected, f"{relative} changed: {digest} != {expected}"


def test_every_prior_run_record_is_unchanged():
    """Run records are immutable; a later block may add one but never edit one."""
    records = sorted(p.name for p in (REPOSITORY / "runs").glob("RUN-*CS012*.yaml"))
    assert "RUN-20260905T210214Z-CS012-09830d98-01.yaml" in records
    assert "RUN-20260905T222042Z-CS012-8c738c6d-01.yaml" in records
    assert "RUN-20260906T001240Z-CS012-ca8a63a6-01.yaml" in records
    assert "RUN-20260906T011740Z-CS012-c42cbfd3-01.yaml" in records
    completed = subprocess.run(
        # 84d9863 is this block's starting HEAD. Every earlier run record must be
        # byte-identical to it; adding a new record is allowed, editing one is not.
        ["git", "-C", str(REPOSITORY), "diff", "--name-only", "84d9863", "HEAD", "--",
         "runs/RUN-20260905T210214Z-CS012-09830d98-01.yaml",
         "runs/RUN-20260905T222042Z-CS012-8c738c6d-01.yaml",
         "runs/RUN-20260906T001240Z-CS012-ca8a63a6-01.yaml",
         "runs/RUN-20260906T011740Z-CS012-c42cbfd3-01.yaml"],
        capture_output=True, text=True,
    )
    assert completed.stdout.strip() == "", completed.stdout


def test_syn01_is_unchanged_and_cannot_be_accepted_as_stationary_compatible():
    """SYN-01 keeps its bytes, and nothing in the codebase re-blesses it."""
    payload = json.loads(SYN_01.read_text(encoding="utf-8"))
    assert payload["packet_id"] == "P-CS012-SYN-01"
    # The I2 packet module records it as quarantined with its true character.
    from tai_public_finance.cs012_poisson_kernels.i2_packets import SYN01_QUARANTINE

    assert SYN01_QUARANTINE["packet_id"] == "P-CS012-SYN-01"
    assert SYN01_QUARANTINE["status"] == "quarantined"
    assert "false" in SYN01_QUARANTINE["defect"].lower()
    assert "stationary" not in SYN01_QUARANTINE["true_character"].lower()
    assert "arbitrary" in SYN01_QUARANTINE["true_character"]
    # The SYN-02 loader refuses a packet claiming SYN-01's id.
    from tai_public_finance.cs012_poisson_kernels.i1_packets import PacketError
    from tai_public_finance.cs012_poisson_kernels.i2_packets import load_analytic_fixture

    with pytest.raises(PacketError, match="expected P-CS012-SYN-02"):
        load_analytic_fixture(SYN_01)


def test_the_i1_economic_section_is_unchanged_by_this_block():
    """Rebuilding the I1 ECO-02 report must reproduce its economic section exactly."""
    from tai_public_finance.cs012_poisson_kernels.report_i1 import build_i1_report

    from .conftest import TEST_PROVENANCE

    rebuilt = build_i1_report(CONFIGS / "P-CS012-SYN-01.json", ECO_02, TEST_PROVENANCE, 0.0)
    committed = json.loads(
        (REPOSITORY / "outputs" / "cs012-i1-provisional-owner-successors-eco02"
         / "identity_report.json").read_text(encoding="utf-8")
    )
    assert json.dumps(rebuilt["economic"], sort_keys=True) == json.dumps(
        committed["economic"], sort_keys=True
    )


# --- checker ---------------------------------------------------------------------------


def test_the_checker_imports_no_production_or_dependency_module():
    for line in CHECKER_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            assert "tai_public_finance" not in stripped, stripped
            assert "ak_partial_ramsey" not in stripped, stripped
            assert "numpy" not in stripped and "scipy" not in stripped, stripped


def test_the_checker_accepts_the_generated_report(i2_report, checker):
    assert checker.check_report(i2_report).messages == []


def test_the_checker_script_runs_end_to_end(i2_report, tmp_path):
    path = tmp_path / "identity_report.json"
    path.write_text(json.dumps(i2_report, indent=2, allow_nan=False), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(CHECKER_PATH), str(path)], capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "OK: independent reconstruction agrees" in completed.stdout
    assert "absent (correct)" in completed.stdout


def _corrupt(report: dict, mutate) -> dict:
    corrupted = copy.deepcopy(report)
    mutate(corrupted)
    return corrupted


def _eco(report: dict) -> dict:
    return report["economic_scenario"]


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("full_ak_level", lambda r: _eco(r)["full_rows"][2].update(
            {"successor_marginal_value_V_e": 260.0})),
        ("full_ak_consumption", lambda r: _eco(r)["full_rows"][0].update(
            {"worker_consumption_C_W": 0.05})),
        ("partial_level", lambda r: _eco(r)["partial_rows"][3].update(
            {"worker_resources_X": 4.0})),
        ("partial_event_map", lambda r: _eco(r)["partial_rows"][1].update(
            {"event_wealth_coordinate_e_plus": 0.0})),
        ("elasticity", lambda r: _eco(r)["elasticities"].update(
            {"full_ak": [-1.0, -1.0, -1.0, -1.0, -1.0, -0.9]})),
        ("sequence_point", lambda r: _eco(r).update(
            {"prefunding_levels": [1.0, 0.3, 0.1, 0.03, 0.01, 0.003, 0.0005]})),
        ("zero_in_sequence", lambda r: _eco(r).update(
            {"prefunding_levels": [1.0, 0.3, 0.1, 0.03, 0.01, 0.003, 0.0]})),
        ("boundary_status", lambda r: _eco(r)["literal_boundary"].update(
            {"status": "finite"})),
        ("boundary_sentinel", lambda r: _eco(r)["literal_boundary"]["full_ak"].update(
            {"successor_marginal_value": {"kind": "finite", "value": 1e308}})),
        ("boundary_consumption", lambda r: _eco(r)["literal_boundary"]["full_ak"].update(
            {"worker_consumption": {"kind": "finite", "value": 1e-12}})),
        ("closure_flag", lambda r: r["closure_audit"].update(
            {"government_kernels_permitted": True})),
        ("closure_status", lambda r: r["closure_audit"].update(
            {"pre_event_mu_e_status": "available_optimized_pre_event_value_gradient"})),
        ("government_reported", lambda r: r["government_kernels"].update(
            {"reported": True, "k_government": [0.5, 0.5]})),
        ("gamma_smuggled", lambda r: _eco(r).update({"gamma": [1.0, 1.0]})),
        ("mu_e_smuggled", lambda r: _eco(r).update({"mu_e": 1.0})),
        ("H_P_route_gap", lambda r: _eco(r)["productive_wealth"].update(
            {"H_P_route_gap": 0.5})),
        ("H_P_disagreement", lambda r: _eco(r)["productive_wealth"].update(
            {"H_P_algebraic": 7.0, "H_P_route_gap": 0.84})),
        ("balance_sheet_sign", lambda r: _eco(r)["balance_sheet_convention"][
            "safe_debt_B_examples"].update({"1.0": 1.0})),
        ("theta_nonzero", lambda r: _eco(r)["balance_sheet_convention"].update(
            {"public_installed_equity_Theta": 0.5})),
        ("eco_fingerprint", lambda r: r["configs"]["economic"].update(
            {"fingerprint": "0" * 64})),
        ("syn02_fingerprint", lambda r: r["configs"]["analytic"].update(
            {"fingerprint": "0" * 64})),
        ("syn02_q_F", lambda r: r["syn02"]["derived"].update({"q_F": 1.30})),
        ("syn02_A_bar", lambda r: r["syn02"]["derived"].update({"A_bar": 0.15})),
        ("syn02_stationary", lambda r: r["syn02"]["analytic_checks"].update(
            {"stationary_compatibility_residual": 0.01})),
        ("syn02_two_mark_claim", lambda r: r["syn02"]["direct_fields"].update(
            {"fixture_scope": "two_mark_scenario"})),
        ("syn01_unquarantined", lambda r: r["syn01_quarantine"].update(
            {"status": "accepted"})),
        ("syn01_relabelled", lambda r: r["syn01_quarantine"].update(
            {"true_character": "a stationary-compatible benchmark"})),
        ("dependency_commit", lambda r: r["provenance"]["cs011_dependency"][
            "resolved"].update({"commit_id": "0" * 40})),
        ("specification_hash", lambda r: r["specification"].update({"sha256": "0" * 64})),
        ("result_use", lambda r: r.update({"result_use": "decision_grade"})),
        ("tvc", lambda r: _eco(r)["safe_position_tvc"].update(
            {"utility_discounted_tvc_holds": False})),
    ],
)
def test_the_checker_rejects_each_corruption(i2_report, checker, label, mutate):
    corrupted = _corrupt(i2_report, mutate)
    try:
        failures = checker.check_report(corrupted)
    except Exception:
        return  # a raise is also a rejection
    assert failures.messages, f"the checker accepted a corrupted report: {label}"


def test_the_checker_script_exits_nonzero_on_a_corrupted_report(i2_report, tmp_path):
    corrupted = _corrupt(
        i2_report, lambda r: _eco(r)["full_rows"][0].update(
            {"successor_marginal_value_V_e": 30.0})
    )
    path = tmp_path / "corrupted.json"
    path.write_text(json.dumps(corrupted, indent=2, allow_nan=False), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(CHECKER_PATH), str(path)], capture_output=True, text=True
    )
    assert completed.returncode == 1
    assert "FAILED" in completed.stdout
