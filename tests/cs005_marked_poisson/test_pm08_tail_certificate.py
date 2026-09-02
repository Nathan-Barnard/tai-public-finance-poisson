"""PM08 tail/transversality certificate tests.

The decisive PM08 certificate is diagnostics.certify_postmark_tail: backward
true-time integration from a local linear tail attached at the anchor, which
CONTRACTS off-manifold deviations at rate nu_+ (the exact reverse of forward
saddle-path shooting, which amplifies them). These tests pin three things:

  1. the certificate passes CS005's 1e-8 tolerance for both marks on the real
     profile -- and does so where the retained forward-shooting warning-level
     diagnostic demonstrably cannot (so a regression back to the naive
     forward-shooting-only pass logic fails here);
  2. the certificate is not tautological: deliberately perturbed off-manifold /
     tail-inconsistent paths are detected and failed;
  3. the CLI surfaces the certificate fields in report.json and summary.md
     (see test_cli_reports_pm08_certificate below).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tai_public_finance.cs005_marked_poisson.diagnostics import (
    PM08_METHOD,
    certify_postmark_tail,
    diagnose_postmark,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
_CS005_TOLERANCE = 1.0e-8


class _PerturbedPath:
    """A minimal PostMarkPath stand-in whose q(k) is pushed off the solved graph by
    a smooth multiplicative field f(u). Only the interface certify_postmark_tail
    uses (q, u_min, u_max, k_min, k_max) is provided."""

    def __init__(self, base, f):
        self._base = base
        self._f = f
        self.u_min = base.u_min
        self.u_max = base.u_max
        self.k_min = base.k_min
        self.k_max = base.k_max

    def q(self, k: float) -> float:
        u = self._base.u_of_k(k)
        return self._base.q(k) * (1.0 + self._f(u))


@pytest.mark.parametrize("which", ["L", "H"])
def test_certificate_passes_cs005_tolerance_per_mark(real_postmark, which):
    mp_L, mp_H, path_L, path_H = real_postmark
    mp, path = {"L": (mp_L, path_L), "H": (mp_H, path_H)}[which]
    cert = certify_postmark_tail(mp, path, tolerance=_CS005_TOLERANCE)
    assert cert.mark == which
    assert cert.method == PM08_METHOD
    assert cert.tolerance == _CS005_TOLERANCE
    assert cert.passes
    assert cert.backward_manifold_match_residual <= _CS005_TOLERANCE
    assert cert.saddle_path_exclusion_bound <= _CS005_TOLERANCE
    # Both sides of the anchor must be certified out to the domain edge.
    assert {s.side for s in cert.sides} == {"left", "right"}
    for s in cert.sides:
        assert s.reached_edge
        assert s.n_match_points >= 10


def test_certificate_passes_where_forward_shooting_fails(real_postmark):
    """The regression against the naive PM08 logic: the old decisive criterion was
    `pm08_unstable_projection <= 1e-8` from FORWARD shooting, which this profile
    cannot meet (observed 5e-3..5e-2). Under that logic this test fails; under the
    backward-tail certificate it passes -- pinning that the repair is a genuinely
    different method, not a loosened tolerance."""

    mp_L, mp_H, path_L, path_H = real_postmark
    for mp, path in ((mp_L, path_L), (mp_H, path_H)):
        pm = diagnose_postmark(mp, path)
        # The warning-level forward-shooting diagnostic still fails the CS005 bound...
        assert pm.pm08_unstable_projection > _CS005_TOLERANCE
        # ...while the decisive backward-tail certificate meets it on the same objects.
        cert = certify_postmark_tail(mp, path, tolerance=_CS005_TOLERANCE)
        assert cert.passes


def test_certificate_detects_global_off_manifold_perturbation(real_postmark):
    """Mutation test: a smooth relative perturbation of q_j(k) that vanishes (to
    ~1e-12) at the attachment radius but reaches 1e-5 in the interior is an
    off-manifold graph the certificate must fail via the backward manifold-match
    residual -- forward-only logic could not distinguish this from its own
    shooting noise (both are ~1e-3-scale at the horizon)."""

    mp_L, _mp_H, path_L, _path_H = real_postmark
    eps = 1.0e-5
    perturbed = _PerturbedPath(path_L, lambda u: eps * (u / max(abs(path_L.u_min), path_L.u_max)) ** 2)
    cert = certify_postmark_tail(mp_L, perturbed, tolerance=_CS005_TOLERANCE)
    assert not cert.passes
    assert cert.backward_manifold_match_residual > _CS005_TOLERANCE


def test_certificate_detects_tail_inconsistent_attachment(real_postmark):
    """Mutation test: a constant relative offset (present at the attachment point
    itself) is a tail-inconsistent graph -- the backward trajectory relaxes onto
    the true stable manifold while the offset graph does not, so the manifold-match
    residual must expose it at the offset's own scale."""

    _mp_L, mp_H, _path_L, path_H = real_postmark
    eps = 1.0e-6
    perturbed = _PerturbedPath(path_H, lambda u: eps)
    cert = certify_postmark_tail(mp_H, perturbed, tolerance=_CS005_TOLERANCE)
    assert not cert.passes


def test_cli_reports_pm08_certificate(tmp_path):
    output_dir = tmp_path / "cs005-pm08-cli-test"
    runs_dir = tmp_path / "runs"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tai_public_finance.cs005_marked_poisson.cli",
            "--config",
            "configs/cs005/smoke_baseline.json",
            "--output-dir",
            str(output_dir),
            "--run-id",
            "RUN-TEST-CS005-PM08",
            "--runs-dir",
            str(runs_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode in (0, 2), result.stderr
    payload = json.loads(result.stdout)
    assert "pm08_cs005_tolerance_pass" in payload

    report = json.loads((output_dir / "report.json").read_text())
    certs = report["pm08_certificates"]
    for mark in ("L", "H"):
        cert = certs[mark]
        assert cert["method"] == PM08_METHOD
        for field in (
            "tolerance",
            "saddle_path_exclusion_bound",
            "backward_manifold_match_residual",
            "unstable_projection_at_attachment",
            "local_tail_consistency_error",
            "passes",
            "sides",
        ):
            assert field in cert, field
        for side in cert["sides"]:
            for field in ("u_attach", "k_attach", "u_edge", "k_edge", "reached_edge", "backward_time_horizon"):
                assert field in side, field
    # The decisive pass flag must come from the certificate, not the forward shooting.
    assert payload["pm08_cs005_tolerance_pass"] == (certs["L"]["passes"] and certs["H"]["passes"])
    summary = (output_dir / "summary.md").read_text()
    assert "PM08 tail certificate" in summary
