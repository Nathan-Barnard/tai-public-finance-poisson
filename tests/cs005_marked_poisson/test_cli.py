from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_cli_end_to_end_on_smoke_profile(tmp_path):
    output_dir = tmp_path / "cs005-smoke-cli-test"
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
            "RUN-TEST-CS005-SMOKE",
            "--runs-dir",
            str(runs_dir),
            "--preflight-tests-status",
            "passed",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode in (0, 2), result.stderr  # 2 = computational_fail is still a clean exit, not a crash
    payload = json.loads(result.stdout)
    assert payload["run_id"] == "RUN-TEST-CS005-SMOKE"
    assert (output_dir / "report.json").exists()
    assert (output_dir / "summary.md").exists()
    assert (runs_dir / "RUN-TEST-CS005-SMOKE.yaml").exists()

    with (output_dir / "report.json").open() as f:
        report = json.load(f)
    assert report["profile_id"] == "P-CS005-SMOKE-01"
    assert isinstance(report["candidates"], list)


def test_cli_refuses_to_overwrite_an_existing_run_record(tmp_path):
    output_dir_1 = tmp_path / "out1"
    output_dir_2 = tmp_path / "out2"
    runs_dir = tmp_path / "runs"
    common_args = [
        sys.executable,
        "-m",
        "tai_public_finance.cs005_marked_poisson.cli",
        "--config",
        "configs/cs005/smoke_baseline.json",
        "--run-id",
        "RUN-TEST-DUPLICATE",
        "--runs-dir",
        str(runs_dir),
    ]
    first = subprocess.run([*common_args, "--output-dir", str(output_dir_1)], cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
    assert first.returncode in (0, 2), first.stderr
    second = subprocess.run([*common_args, "--output-dir", str(output_dir_2)], cwd=REPO_ROOT, capture_output=True, text=True, timeout=120)
    assert second.returncode != 0
    assert "immutable" in second.stderr.lower() or "already exists" in second.stderr.lower()
