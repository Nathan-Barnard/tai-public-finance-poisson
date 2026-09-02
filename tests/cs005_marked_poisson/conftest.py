from __future__ import annotations

from pathlib import Path

import pytest

from tai_public_finance.cs005_marked_poisson.postmark_equations import mark_params
from tai_public_finance.cs005_marked_poisson.postmark_solver import solve_postmark
from tai_public_finance.cs005_marked_poisson.primitives import compute_derived_constants, load_raw_primitives

CONFIGS_DIR = Path(__file__).resolve().parents[2] / "configs" / "cs005"


@pytest.fixture(scope="session")
def smoke_primitives():
    return load_raw_primitives(CONFIGS_DIR / "P-CS005-SMOKE-01.json")


@pytest.fixture(scope="session")
def real_primitives():
    return load_raw_primitives(CONFIGS_DIR / "P-CS005-REAL-01.json")


@pytest.fixture(scope="session")
def smoke_derived(smoke_primitives):
    return compute_derived_constants(smoke_primitives)


@pytest.fixture(scope="session")
def real_derived(real_primitives):
    return compute_derived_constants(real_primitives)


def _solved_paths(primitives, derived):
    mp_L = mark_params(primitives, derived, "L")
    mp_H = mark_params(primitives, derived, "H")
    path_L = solve_postmark(mp_L, mp_L.anchor.u_min, mp_L.anchor.u_max)
    path_H = solve_postmark(mp_H, mp_H.anchor.u_min, mp_H.anchor.u_max)
    return mp_L, mp_H, path_L, path_H


@pytest.fixture(scope="session")
def smoke_postmark(smoke_primitives, smoke_derived):
    return _solved_paths(smoke_primitives, smoke_derived)


@pytest.fixture(scope="session")
def real_postmark(real_primitives, real_derived):
    return _solved_paths(real_primitives, real_derived)
