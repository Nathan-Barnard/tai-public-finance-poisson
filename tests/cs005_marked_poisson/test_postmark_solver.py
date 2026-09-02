from __future__ import annotations

import math

import pytest

from tai_public_finance.cs005_marked_poisson.postmark_solver import ensure_domain


@pytest.mark.parametrize("mark_index", [0, 1])
def test_anchor_boundary_conditions_hold_exactly(smoke_postmark, mark_index):
    mp_L, mp_H, path_L, path_H = smoke_postmark
    mp, path = (mp_L, path_L) if mark_index == 0 else (mp_H, path_H)
    k_star = mp.anchor.k_star
    assert path.q(k_star) == pytest.approx(mp.q_star, rel=1e-10)
    assert path.H(k_star) == pytest.approx(mp.anchor.H_star, rel=1e-10)
    assert path.q_prime(k_star) == pytest.approx(mp.anchor.q_prime_star, rel=1e-10)


def test_q_decreasing_in_k_away_from_anchor_both_marks(real_postmark):
    # Diminishing returns + adjustment costs: along the stable manifold, Tobin's q
    # falls as capital rises past the anchor (scarce capital commands a high shadow
    # price; abundant capital a low one). A flat or increasing q(k) here would
    # indicate the wrong eigenvector branch was selected.
    mp_L, mp_H, path_L, path_H = real_postmark
    for path in (path_L, path_H):
        ks = [path.k_min * 1.01, path.mp.anchor.k_star, path.k_max * 0.99]
        qs = [path.q(k) for k in ks]
        assert qs[0] > qs[1] > qs[2]


def test_domain_respects_specialization_floor(real_postmark):
    mp_L, mp_H, path_L, path_H = real_postmark
    for mp, path in ((mp_L, path_L), (mp_H, path_H)):
        assert path.k_min >= mp.anchor.specialization_floor * (1.0 - 1e-9)


def test_ensure_domain_expands_and_is_idempotent_at_cap(real_postmark):
    mp_L, _mp_H, path_L, _path_H = real_postmark
    expanded = ensure_domain(path_L, path_L.u_min - 1.5, path_L.u_max + 1.5)
    assert expanded.u_min < path_L.u_min
    assert expanded.u_max > path_L.u_max
    # Still consistent at the (now wider) anchor and edges.
    assert expanded.q(mp_L.anchor.k_star) == pytest.approx(mp_L.q_star, rel=1e-10)

    at_cap = ensure_domain(expanded, -8.0, 8.0)
    assert at_cap.u_min == pytest.approx(-8.0)
    assert at_cap.u_max == pytest.approx(8.0)
    same = ensure_domain(at_cap, -8.0, 8.0)
    assert same is at_cap  # no further expansion possible/needed


def test_q_prime_matches_finite_difference_away_from_anchor(real_postmark):
    _mp_L, _mp_H, path_L, _path_H = real_postmark
    k = path_L.mp.anchor.k_star * math.exp(1.0)
    h = 1e-5 * k
    fd = (path_L.q(k + h) - path_L.q(k - h)) / (2.0 * h)
    assert path_L.q_prime(k) == pytest.approx(fd, rel=1e-6)
