"""Shared fixtures for the CS012 I2a tests."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from tai_public_finance.cs012_poisson_kernels.i1_packets import load_economic_packet
from tai_public_finance.cs012_poisson_kernels.i1_successors import (
    model_parameters,
    solve_successors,
)
from tai_public_finance.cs012_poisson_kernels.i2_packets import (
    load_analytic_fixture,
    load_prefunding_packet,
)
from tai_public_finance.cs012_poisson_kernels.report import Provenance
from tai_public_finance.cs012_poisson_kernels.report_i2 import build_i2_report

REPOSITORY = Path(__file__).resolve().parents[2]
CONFIGS = REPOSITORY / "configs" / "cs012"
ECO_02 = CONFIGS / "P-CS012-ECO-02.json"
ECO_01 = CONFIGS / "P-CS012-ECO-01.json"
SYN_01 = CONFIGS / "P-CS012-SYN-01.json"
SYN_02 = CONFIGS / "P-CS012-SYN-02.json"
PREFUND = CONFIGS / "P-CS012-PREFUND-01.json"
CHECKER_PATH = REPOSITORY / "tools" / "check_cs012_i2_report.py"

TEST_PROVENANCE = Provenance(
    code_commit="0" * 40,
    branch="cs012/i1-provisional-owner-successors",
    clean_start=True,
    repository_url="https://github.com/Nathan-Barnard/tai-public-finance-poisson.git",
    python_version="3.13.5",
    scipy_version="1.18.1",
    numpy_version="2.5.2",
    platform="test",
    machine="test",
)


@pytest.fixture(scope="session")
def prefunding_packet():
    return load_prefunding_packet(PREFUND)


@pytest.fixture(scope="session")
def analytic_fixture():
    return load_analytic_fixture(SYN_02)


@pytest.fixture(scope="session")
def eco02():
    return load_economic_packet(ECO_02)


@pytest.fixture(scope="session")
def services(eco02):
    return solve_successors(
        model_parameters(eco02), eco02.ak_root_interval, eco02.partial_capital_interval
    )


@pytest.fixture(scope="session")
def i2_report():
    return build_i2_report(ECO_02, PREFUND, SYN_02, TEST_PROVENANCE, 0.0)


@pytest.fixture(scope="session")
def checker():
    spec = importlib.util.spec_from_file_location("cs012_i2_checker", CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
