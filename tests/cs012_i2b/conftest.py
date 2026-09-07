"""Shared fixtures for the CS012 I2b tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tai_public_finance.cs012_poisson_kernels.report import Provenance
from tai_public_finance.cs012_poisson_kernels.report_i2b import build_i2b_report

REPOSITORY = Path(__file__).resolve().parents[2]
CONFIGS = REPOSITORY / "configs" / "cs012"
CHECKER_PATH = REPOSITORY / "tools" / "check_cs012_i2b_report.py"

ECO_02, ECO_03 = CONFIGS / "P-CS012-ECO-02.json", CONFIGS / "P-CS012-ECO-03.json"
PREFUND_01, PREFUND_02 = CONFIGS / "P-CS012-PREFUND-01.json", CONFIGS / "P-CS012-PREFUND-02.json"
SYN_02, SYN_03 = CONFIGS / "P-CS012-SYN-02.json", CONFIGS / "P-CS012-SYN-03.json"

TEST_PROVENANCE = Provenance(
    code_commit="0" * 40,
    branch="cs012/i2b-transfer-constrained-prefunding",
    clean_start=True,
    repository_url="https://github.com/Nathan-Barnard/tai-public-finance-poisson.git",
    python_version="3.13.5", scipy_version="1.18.1", numpy_version="2.5.2",
    platform="test", machine="test",
)


@pytest.fixture(scope="session")
def report_eco02():
    return build_i2b_report(ECO_02, PREFUND_01, SYN_02, TEST_PROVENANCE, 0.0)


@pytest.fixture(scope="session")
def report_eco03():
    return build_i2b_report(ECO_03, PREFUND_02, SYN_03, TEST_PROVENANCE, 0.0)


@pytest.fixture(scope="session")
def checker():
    spec = importlib.util.spec_from_file_location("cs012_i2b_checker", CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
