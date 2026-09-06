"""I2b checker independence, corruption rejection, and prior-artifact immutability."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys

import pytest

from .conftest import CHECKER_PATH, REPOSITORY

FROZEN_ARTIFACTS = {
    "configs/cs012/P-CS012-ECO-01.json":
        "bcdc33be61a801c3b84346893020e2d60249c33311b4a9e39f2d31ae644ccd03",
    "configs/cs012/P-CS012-ECO-02.json":
        "9d1c2ff7d30218d0b7fd2d284935360c4ec90511c1e022fcac49387b1c7b7940",
    "configs/cs012/P-CS012-SYN-01.json":
        "74cc08c122876593dab557c6c0626e906ef383eeb4e72ba3cbc0f98444895ba3",
    "configs/cs012/P-CS012-PREFUND-01.json":
        "173fcaa123a00e75ed1c3f140e7a763fc788f15d6c3498eac0d062e30ea409db",
    "configs/cs012/P-CS012-SYN-02.json":
        "e891c851148ecc04c5c202715adaa9626d14407d6dcf2b799b687632c01b7bbc",
    "outputs/cs012-i0-pricing-kernel-identities/identity_report.json":
        "2ce7e59d8174fd149cafa5e63b12945cb506ec8b7762f7e93c9d22a8c3b3bb78",
    "outputs/cs012-i1-provisional-owner-successors/identity_report.json":
        "e078541c1cc664e33573bf13af4078aef64561e5e7db9fe8b77922919982c349",
    "outputs/cs012-i1-provisional-owner-successors-eco02/identity_report.json":
        "d9e70c606e49bb392570d0435aba9a420c994738f550097e181204fed583d4d3",
    "outputs/cs012-i2a-successor-prefunding-eco02/identity_report.json":
        "347250aa380fe64cc54a4b21e4b0e7dbc4a962bcd243867efbffc022e9b5812f",
    "outputs/cs012-i2a-successor-prefunding-eco02/summary.md":
        "3964b7bf4f22d23ba0220cf913e7b3ec24ccf8e9d9e50f70ad9eba379e811dda",
}

PINNED_CHECKS = [
    ("tools/check_cs012_i1_report.py",
     "outputs/cs012-i1-provisional-owner-successors/identity_report.json"),
    ("tools/check_cs012_i1_report.py",
     "outputs/cs012-i1-provisional-owner-successors-eco02/identity_report.json"),
    ("tools/check_cs012_i2_report.py",
     "outputs/cs012-i2a-successor-prefunding-eco02/identity_report.json"),
]


def test_every_prior_artifact_is_byte_identical():
    for relative, expected in FROZEN_ARTIFACTS.items():
        path = REPOSITORY / relative
        assert path.exists(), relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, relative


def test_prior_run_records_are_unchanged():
    completed = subprocess.run(
        ["git", "-C", str(REPOSITORY), "diff", "--name-only",
         "c325aee0b92e4101ba085c74183c8e293c2ef2ef", "HEAD", "--", "runs/"],
        capture_output=True, text=True,
    )
    edited = [line for line in completed.stdout.split() if line.endswith(".yaml")]
    assert edited == [], f"a prior run record was edited: {edited}"


@pytest.mark.parametrize(("checker", "artifact"), PINNED_CHECKS)
def test_the_inherited_checkers_still_pass_on_their_pinned_artifacts(checker, artifact):
    completed = subprocess.run(
        [sys.executable, str(REPOSITORY / checker), str(REPOSITORY / artifact)],
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_the_checker_shares_no_module_with_production():
    source = CHECKER_PATH.read_text(encoding="utf-8")
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            for banned in ("tai_public_finance", "ak_partial_ramsey", "numpy", "scipy"):
                assert banned not in stripped, stripped
    # And it must carry its own numerics rather than importing a shared helper.
    assert "def simpson(" in source and "def bisect(" in source


@pytest.mark.parametrize("fixture_name", ["report_eco02", "report_eco03"])
def test_the_checker_accepts_both_reports(request, checker, fixture_name):
    report = request.getfixturevalue(fixture_name)
    assert checker.check_report(report).messages == []


@pytest.mark.parametrize("fixture_name", ["report_eco02", "report_eco03"])
def test_the_checker_script_runs_end_to_end(request, tmp_path, fixture_name):
    report = request.getfixturevalue(fixture_name)
    path = tmp_path / f"{fixture_name}.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(CHECKER_PATH), str(path)], capture_output=True, text=True
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "OK: independent reconstruction agrees" in completed.stdout


def _corrupt(report: dict, mutate) -> dict:
    corrupted = copy.deepcopy(report)
    mutate(corrupted)
    return corrupted


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("A_value", lambda r: r["constrained_rows"][2].update(
            {"annuity_coefficient_A": 0.16})),
        ("V_value", lambda r: r["constrained_rows"][1].update(
            {"successor_marginal_value_V_e": 5.0})),
        ("switch_time", lambda r: r["constrained_rows"][3]["switch_time_years"].update(
            {"value": 7.0})),
        ("switch_sentinel", lambda r: r["constrained_rows"][0].update(
            {"switch_time_years": {"kind": "finite", "value": 1.0e12}})),
        ("active_set_label", lambda r: r["constrained_rows"][-1].update(
            {"active_set": "globally_transfer_interior"})),
        ("active_set_counts", lambda r: r["active_set_counts"].update(
            {"transfer_boundary_active": 99})),
        ("budget_term", lambda r: r["constrained_rows"][4].update(
            {"pv_transfer_budget_residual": 1.0e-3})),
        ("prefunding_level", lambda r: r["constrained_rows"][5].update(
            {"prefunding_level_F": 0.004})),
        ("tail_contribution", lambda r: r["path_samples"].update(
            {"tail_wage": 0.30})),
        ("wage_sample", lambda r: r["path_samples"]["samples"][10].update({"W": 0.05})),
        ("initial_wage", lambda r: r["productive_path"].update(
            {"initial_wage_W_P_0": 0.10})),
        ("pv_wage_route", lambda r: r["productive_path"].update(
            {"H_P_minus_qP_K": 5.2})),
        ("route_gap", lambda r: r["productive_path"].update({"pv_wage_route_gap": 1.0})),
        ("boundary_classification", lambda r: r["literal_boundary"]["partial_automation"][
            "one_sided_limit_V_e"].update({"kind": "positive_infinity", "value": None})),
        ("boundary_limit_value", lambda r: r["literal_boundary"]["partial_automation"][
            "one_sided_limit_V_e"].update({"value": 5.1365})),
        ("boundary_status", lambda r: r["literal_boundary"].update({"status": "finite"})),
        ("full_ak_level", lambda r: r["full_ak_rows"][0].update(
            {"successor_marginal_value_V_e": 26.0})),
        ("full_ak_elasticity", lambda r: r["full_ak_elasticities"].__setitem__(0, -0.95)),
        ("closure_flag", lambda r: r["government_kernels"].update({"reported": True})),
        ("kernel_smuggled", lambda r: r["constrained_rows"][0].update(
            {"k_government": 0.5})),
        ("gamma_smuggled", lambda r: r["transfer_slack"].update({"gamma": [1.0]})),
        ("config_fingerprint", lambda r: r["configs"]["economic"].update(
            {"fingerprint": "0" * 64})),
        ("dependency_commit", lambda r: r["provenance"]["cs011_dependency"][
            "resolved"].update({"commit_id": "0" * 40})),
        ("specification_hash", lambda r: r["specification"].update({"sha256": "0" * 64})),
        ("result_use", lambda r: r.update({"result_use": "decision_grade"})),
        ("i2a_quarantine_dropped", lambda r: r["i2a_quarantine"].update(
            {"status": "accepted"})),
        ("economic_object", lambda r: r["economic_object"].update({"source_tax_tau": 0.2})),
    ],
)
def test_the_checker_rejects_each_corruption(report_eco02, checker, label, mutate):
    try:
        failures = checker.check_report(_corrupt(report_eco02, mutate))
    except Exception:
        return
    assert failures.messages, f"the checker accepted a corrupted report: {label}"


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("F_min", lambda r: r["transfer_slack"].update({"F_min": 0.5})),
        ("threshold", lambda r: r["transfer_slack"]["threshold_underline_X"].update(
            {"value": 4.0})),
        ("interiority_margin", lambda r: r["main_interior_reference"].update(
            {"minimum_transfer_margin": 0.02})),
        ("interiority_verdict", lambda r: r["main_interior_reference"].update(
            {"verdict": "robustly_interior", "credible_error": 0.01})),
        ("interior_row_margin", lambda r: next(
            row for row in r["constrained_rows"]
            if row["active_set"] == "globally_transfer_interior"
        ).update({"minimum_transfer_margin": 0.02})),
        ("misclassified_row", lambda r: next(
            row for row in r["constrained_rows"]
            if row["prefunding_level_F"] == 0.1
        ).update({"active_set": "globally_transfer_interior",
                  "switch_time_years": {"kind": "undefined", "value": None}})),
    ],
)
def test_the_checker_rejects_eco03_specific_corruptions(report_eco03, checker, label, mutate):
    try:
        failures = checker.check_report(_corrupt(report_eco03, mutate))
    except Exception:
        return
    assert failures.messages, f"the checker accepted a corrupted report: {label}"


def test_the_checker_script_exits_nonzero_on_a_corrupted_report(report_eco02, tmp_path):
    corrupted = _corrupt(
        report_eco02, lambda r: r["constrained_rows"][0].update(
            {"successor_marginal_value_V_e": 4.0})
    )
    path = tmp_path / "corrupted.json"
    path.write_text(json.dumps(corrupted, indent=2, allow_nan=False), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(CHECKER_PATH), str(path)], capture_output=True, text=True
    )
    assert completed.returncode == 1
    assert "FAILED" in completed.stdout


def test_reports_carry_no_nan_untagged_infinity_or_sentinel(report_eco02, report_eco03):
    for report in (report_eco02, report_eco03):
        text = json.dumps(report, allow_nan=False)
        assert "Infinity" not in text and "NaN" not in text
        json.loads(text, parse_constant=lambda c: pytest.fail(f"non-standard token {c}"))
        for row in report["constrained_rows"]:
            switch = row["switch_time_years"]
            assert switch["kind"] in ("finite", "undefined")
            if switch["kind"] == "undefined":
                assert switch["value"] is None
            else:
                assert 0.0 < switch["value"] < 1.0e6
