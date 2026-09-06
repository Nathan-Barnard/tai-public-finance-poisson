"""Shared fixtures for the CS012 I1 owner-branch tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tai_public_finance.cs012_poisson_kernels.i1_packets import (
    load_economic_packet,
    load_synthetic_packet,
)
from tai_public_finance.cs012_poisson_kernels.i1_successors import (
    model_parameters,
    solve_successors,
)
from tai_public_finance.cs012_poisson_kernels.report_i1 import build_i1_report
from tai_public_finance.cs012_poisson_kernels.report import Provenance

REPOSITORY = Path(__file__).resolve().parents[2]
SYNTHETIC_CONFIG = REPOSITORY / "configs" / "cs012" / "P-CS012-SYN-01.json"
ECONOMIC_CONFIG = REPOSITORY / "configs" / "cs012" / "P-CS012-ECO-01.json"
CHECKER_PATH = REPOSITORY / "tools" / "check_cs012_i1_report.py"

CS011_COMMIT = "6b457682c4eed8ad4e3bdd867d1292abac38f424"

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
def economic_packet():
    return load_economic_packet(ECONOMIC_CONFIG)


@pytest.fixture(scope="session")
def synthetic_packet():
    return load_synthetic_packet(SYNTHETIC_CONFIG)


@pytest.fixture(scope="session")
def services(economic_packet):
    return solve_successors(
        model_parameters(economic_packet),
        economic_packet.ak_root_interval,
        economic_packet.partial_capital_interval,
    )


@pytest.fixture(scope="session")
def i1_report():
    return build_i1_report(SYNTHETIC_CONFIG, ECONOMIC_CONFIG, TEST_PROVENANCE, 0.0)


@pytest.fixture(scope="session")
def checker():
    import importlib.util

    spec = importlib.util.spec_from_file_location("cs012_i1_checker", CHECKER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module
