"""Report generation, immutable output, and the standalone independent checker.

The checker is loaded from ``tools/check_cs012_i0_report.py`` by file path so
that these tests exercise the same standalone script the validation commands run,
and so that the script keeps its standard-library-only import surface.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tai_public_finance.cs012_poisson_kernels.inputs import load_fixtures
from tai_public_finance.cs012_poisson_kernels.report import (
    Provenance,
    build_report,
    write_report,
)

from .conftest import REPOSITORY

CHECKER_PATH = REPOSITORY / "tools" / "check_cs012_i0_report.py"

IDENTITY_MAX = 1.0e-11
INDEPENDENT_MAX = 1.0e-10


def _load_checker():
    spec = importlib.util.spec_from_file_location("cs012_i0_checker", CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHECKER = _load_checker()


@pytest.fixture(scope="module")
def report(fixture_path) -> dict:
    provenance = Provenance(
        code_commit="0" * 40,
        branch="cs012/i0-pricing-kernel-identities",
        clean_start=True,
        repository_url="https://github.com/Nathan-Barnard/tai-public-finance-poisson.git",
        python_version="3.13.5",
        scipy_version="1.18.1",
        numpy_version="2.5.2",
        platform="test",
        machine="test",
    )
    return build_report(load_fixtures(fixture_path), provenance, Path(fixture_path), 0.0)


def test_the_checker_imports_nothing_from_the_production_package():
    source = CHECKER_PATH.read_text(encoding="utf-8")
    assert "tai_public_finance" not in source.replace(
        "``tai_public_finance``", ""
    ).replace("from ``tai_public_finance``", "")
    assert "import numpy" not in source and "import scipy" not in source


def test_the_report_covers_every_fixture_and_records_its_limits(report, frozen_fixtures):
    assert report["schema"] == "cs012-i0-identity-report/1"
    assert report["result_use"] == "exploratory_only"
    assert report["specification"]["version"] == "0.1"
    assert report["specification"]["status"] == "draft"
    assert (
        report["specification"]["sha256"]
        == "275cf384a6aa8f12831bd0e7b8b8ea4291e49402f3578a9c301baf91fe2930e8"
    )
    assert [entry["fixture_id"] for entry in report["fixtures"]] == list(frozen_fixtures)
    assert report["summary"]["max_decomposition_error"] <= IDENTITY_MAX
    assert report["summary"]["max_relative_identity_error"] <= IDENTITY_MAX
    assert report["summary"]["max_production_versus_independent_error"] <= INDEPENDENT_MAX


def test_every_expected_status_appears_at_least_once(report):
    summary = report["summary"]
    assert summary["kernel_status_counts"] == {
        "finite_maintained_branch": 5,
        "nonfinite_fiscal_kernel_at_literal_laissez_faire": 1,
    }
    assert summary["owner_root_status_counts"] == {
        "no_interior_root_boundary_limit": 1,
        "unique_interior_root": 3,
        "zero_payoff_unidentified": 1,
    }
    assert summary["projection_status_counts"] == {
        "projection_resolved": 4,
        "zero_payoff_norm_refused": 1,
    }


def test_the_standalone_checker_accepts_the_generated_report(report):
    failures = CHECKER.check_report(report)
    assert failures.messages == []


def test_the_report_is_json_serializable_without_non_standard_tokens(report, tmp_path):
    output = tmp_path / "identity_report.json"
    digest = write_report(report, output)
    assert len(digest) == 64
    text = output.read_text(encoding="utf-8")
    assert "Infinity" not in text and "NaN" not in text
    assert json.loads(text)["summary"] == report["summary"]


def test_an_existing_output_is_never_overwritten(report, tmp_path):
    output = tmp_path / "identity_report.json"
    write_report(report, output)
    with pytest.raises(FileExistsError):
        write_report(report, output)


def test_the_checker_script_runs_end_to_end_and_exits_zero(report, tmp_path):
    output = tmp_path / "identity_report.json"
    write_report(report, output)
    completed = subprocess.run(
        [sys.executable, str(CHECKER_PATH), str(output)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "OK: independent reconstruction agrees" in completed.stdout


# --- corruption tests --------------------------------------------------------------


def _corrupt(report: dict, mutate) -> dict:
    corrupted = copy.deepcopy(report)
    mutate(corrupted)
    return corrupted


def _entry(report: dict, fixture_id: str) -> dict:
    return next(e for e in report["fixtures"] if e["fixture_id"] == fixture_id)


def test_the_checker_rejects_a_corrupted_term(report):
    corrupted = _corrupt(
        report,
        lambda r: _entry(r, "two_mark_orthogonal_gap")["marks"][0].update(
            {"term_government": 0.123456}
        ),
    )
    failures = CHECKER.check_report(corrupted)
    assert failures.messages
    assert any("term_government" in message for message in failures.messages)


def test_the_checker_rejects_a_corrupted_status(report):
    corrupted = _corrupt(
        report,
        lambda r: _entry(r, "all_zero_payoff_unidentified")["owner_root"].update(
            {"status": "unique_interior_root"}
        ),
    )
    failures = CHECKER.check_report(corrupted)
    assert failures.messages
    assert any("zero_payoff_unidentified" in message for message in failures.messages)


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        (
            "kernel_value",
            lambda r: _entry(r, "one_mark_alignment")["marks"][0].update({"k_owner": 0.4}),
        ),
        (
            "residual_sum",
            lambda r: _entry(r, "two_mark_one_zero_payoff")["sums"].update({"d_owner": 1.0}),
        ),
        (
            "identity_discrepancy",
            lambda r: _entry(r, "one_mark_alignment")["identities"].update(
                {"decomposition_error": 5.0e-13}
            ),
        ),
        (
            "root_exposure",
            lambda r: _entry(r, "one_mark_alignment")["owner_root"].update({"exposure": 2.5}),
        ),
        (
            "projection_alpha",
            lambda r: _entry(r, "two_mark_orthogonal_gap")["projection"].update(
                {"alpha": 0.5}
            ),
        ),
        (
            "projection_norm",
            lambda r: _entry(r, "two_mark_orthogonal_gap")["projection"].update(
                {"weighted_norm_orthogonal": 0.0}
            ),
        ),
        (
            "kernel_status",
            lambda r: _entry(r, "one_mark_alignment").update(
                {"kernel_status": "nonfinite_finite_branch_input"}
            ),
        ),
        (
            "projection_status",
            lambda r: _entry(r, "all_zero_payoff_unidentified")["projection"].update(
                {"status": "projection_resolved"}
            ),
        ),
        (
            "summary_status_count",
            lambda r: r["summary"]["owner_root_status_counts"].update(
                {"unique_interior_root": 4}
            ),
        ),
        (
            "summary_refusal_count",
            lambda r: r["summary"]["refusal_counts"].update({"projection_refused": 0}),
        ),
        (
            "summary_maximum",
            lambda r: r["summary"].update({"max_orthogonality_error": 0.0}),
        ),
        (
            "safe_account_rank",
            lambda r: _entry(r, "two_mark_orthogonal_gap")["safe_account"].update(
                {"rank_with_safe_account": 2, "rank_increase": 1}
            ),
        ),
        (
            "boundary_sentinel",
            lambda r: _entry(r, "literal_laissez_faire_full_ak")["boundary_marks"][0].update(
                {"k_government": {"kind": "finite", "value": 1.0e308}}
            ),
        ),
        (
            "boundary_finite_arithmetic",
            lambda r: _entry(r, "literal_laissez_faire_full_ak").update(
                {"sums": {"d_owner": 0.0, "d_government": 0.0,
                          "d_government_owner": 0.0, "d_relative": 0.0}}
            ),
        ),
        (
            "specification_hash",
            lambda r: r["specification"].update({"sha256": "0" * 64}),
        ),
        (
            "result_use",
            lambda r: r.update({"result_use": "decision_grade"}),
        ),
        (
            "input_payoff",
            lambda r: _entry(r, "two_mark_orthogonal_gap")["inputs"]["marks"][0].update(
                {"payoff_jump": 0.75}
            ),
        ),
    ],
)
def test_the_checker_rejects_each_corruption(report, label, mutate):
    failures = CHECKER.check_report(_corrupt(report, mutate))
    assert failures.messages, f"the checker accepted a corrupted report: {label}"


def test_the_checker_script_exits_nonzero_on_a_corrupted_report(report, tmp_path):
    corrupted = _corrupt(
        report,
        lambda r: _entry(r, "one_mark_alignment")["marks"][0].update({"gamma": 2.0}),
    )
    output = tmp_path / "corrupted.json"
    output.write_text(json.dumps(corrupted, indent=2), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(CHECKER_PATH), str(output)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 1
    assert "FAILED" in completed.stdout
