"""Pre-arrival equation construction: jumps, the private-portfolio quadratic, the
public saving/exposure linear-plus-quadratic reduction, the scalar capital
residual K(k), and the recovery dictionary.

Pure functions only -- no root-finding (see prearrival_solver.py) and no
residual/acceptance evaluation (see diagnostics.py, which re-derives every
check here independently rather than importing it).

The public-block quadratic is built by symbolic multiplication of affine
(slope, intercept) pairs in `e` rather than by hand-expanding the algebra,
so a transcription slip shows up as a wrong (slope, intercept) rather than
a silently-wrong expanded polynomial coefficient.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .postmark_equations import output, rental

Affine = tuple[float, float]  # (slope, intercept): value(e) = slope * e + intercept
Quadratic = tuple[float, float, float]  # (a, b, c): a e^2 + b e + c


def _affine_add(u: Affine, v: Affine, scale_u: float = 1.0, scale_v: float = 1.0) -> Affine:
    return (scale_u * u[0] + scale_v * v[0], scale_u * u[1] + scale_v * v[1])


def _affine_multiply(u: Affine, v: Affine) -> Quadratic:
    (s1, i1), (s2, i2) = u, v
    return (s1 * s2, s1 * i2 + s2 * i1, i1 * i2)


def _quadratic_subtract(p: Quadratic, q: Quadratic) -> Quadratic:
    return (p[0] - q[0], p[1] - q[1], p[2] - q[2])


def solve_quadratic(coeffs: Quadratic, *, zero_tol: float = 1.0e-14) -> list[float]:
    """Real roots of a e^2 + b e + c = 0, falling back to the linear root when a ~ 0."""

    a, b, c = coeffs
    scale = max(abs(a), abs(b), abs(c), 1.0)
    if abs(a) <= zero_tol * scale:
        if abs(b) <= zero_tol * scale:
            return []
        return [-c / b]
    discriminant = b * b - 4.0 * a * c
    if discriminant < 0.0:
        return []
    sqrt_disc = math.sqrt(discriminant)
    return [(-b + sqrt_disc) / (2.0 * a), (-b - sqrt_disc) / (2.0 * a)]


def jump(q_at_k: float, q_star: float) -> float:
    """J_j(k) = q_j(k)/q_star - 1."""

    return q_at_k / q_star - 1.0


def compensator(J_L: float, J_H: float, lambda_L_star: float, lambda_H_star: float) -> float:
    """Lambda(k) = lambda_L^star J_L + lambda_H^star J_H."""

    return lambda_L_star * J_L + lambda_H_star * J_H


def net_production_0(I_0: float, k: float, iota_star: float) -> float:
    """d_0(k) = y_0(k) - iota^star k."""

    return output(I_0, k) - iota_star * k


@dataclass(frozen=True)
class PrivatePortfolioRoot:
    pi: float
    interior: bool  # 1 + pi*J_j > 0 for both j


def private_portfolio_roots(Lambda: float, J_L: float, J_H: float, lambda_total: float, lambda_L: float, lambda_H: float) -> list[PrivatePortfolioRoot]:
    """Roots of 0 = Lambda J_L J_H pi^2 + [Lambda(J_L+J_H) - lambda J_L J_H] pi + [Lambda - lambda_L J_L - lambda_H J_H]."""

    a = Lambda * J_L * J_H
    b = Lambda * (J_L + J_H) - lambda_total * J_L * J_H
    c = Lambda - lambda_L * J_L - lambda_H * J_H
    roots = []
    for pi in solve_quadratic((a, b, c)):
        interior = (1.0 + pi * J_L) > 0.0 and (1.0 + pi * J_H) > 0.0
        roots.append(PrivatePortfolioRoot(pi=pi, interior=interior))
    return roots


def linear_relation_coefficients(
    Delta_0: float, lambda_L: float, lambda_H: float, lambda_total: float, J_L: float, J_H: float, Lambda: float, H_L: float, H_H: float
) -> tuple[float, float, float]:
    """A_e e + A_psi psi + A_H = 0, eliminating m_0/c_0^W between the two public FOCs."""

    A_e = Delta_0 * (lambda_L * J_L + lambda_H * J_H) - lambda_total * Lambda
    A_psi = Delta_0 * lambda_total * J_L * J_H - Lambda * (lambda_L * J_H + lambda_H * J_L)
    A_H = Delta_0 * (lambda_L * J_L * H_H + lambda_H * J_H * H_L) - Lambda * (lambda_L * H_H + lambda_H * H_L)
    return A_e, A_psi, A_H


@dataclass(frozen=True)
class PublicInteriorRoot:
    e: float
    psi: float


def public_interior_roots_via_e(
    A_e: float, A_psi: float, A_H: float, d_0: float, rbar_0: float, Lambda: float, H_L: float, H_H: float, J_L: float, J_H: float, lambda_L: float, lambda_H: float, rho: float, Delta_0: float
) -> list[PublicInteriorRoot]:
    """Substitute the line psi(e) = -(A_e e + A_H)/A_psi into the public-saving FOC and
    solve the resulting quadratic in e. Requires A_psi != 0 -- see
    public_interior_roots_via_psi for the degenerate fallback."""

    psi_line: Affine = (-A_e / A_psi, -A_H / A_psi)
    X_L: Affine = _affine_add((1.0, H_L), psi_line, scale_v=J_L)
    X_H: Affine = _affine_add((1.0, H_H), psi_line, scale_v=J_H)
    c0W: Affine = _affine_add((rbar_0, d_0), psi_line, scale_v=-Lambda)

    combo: Affine = _affine_add(X_H, X_L, scale_u=lambda_L, scale_v=lambda_H)
    lhs = _affine_multiply(combo, c0W)
    rhs_scale = rho * Delta_0
    rhs = _affine_multiply(X_L, X_H)
    rhs_scaled: Quadratic = (rhs_scale * rhs[0], rhs_scale * rhs[1], rhs_scale * rhs[2])
    quadratic = _quadratic_subtract(lhs, rhs_scaled)

    roots = []
    for e in solve_quadratic(quadratic):
        psi = psi_line[0] * e + psi_line[1]
        roots.append(PublicInteriorRoot(e=e, psi=psi))
    return roots


def public_interior_roots_via_psi(
    A_e: float, A_psi: float, A_H: float, d_0: float, rbar_0: float, Lambda: float, H_L: float, H_H: float, J_L: float, J_H: float, lambda_L: float, lambda_H: float, rho: float, Delta_0: float
) -> list[PublicInteriorRoot]:
    """Degenerate fallback when A_psi ~ 0: the line pins e = -A_H/A_e directly, and the
    public-saving FOC becomes a quadratic in psi alone."""

    e_fixed = -A_H / A_e
    X_L: Affine = (J_L, e_fixed + H_L)
    X_H: Affine = (J_H, e_fixed + H_H)
    c0W: Affine = (-Lambda, d_0 + rbar_0 * e_fixed)

    combo: Affine = _affine_add(X_H, X_L, scale_u=lambda_L, scale_v=lambda_H)
    lhs = _affine_multiply(combo, c0W)
    rhs_scale = rho * Delta_0
    rhs = _affine_multiply(X_L, X_H)
    rhs_scaled: Quadratic = (rhs_scale * rhs[0], rhs_scale * rhs[1], rhs_scale * rhs[2])
    quadratic = _quadratic_subtract(lhs, rhs_scaled)

    roots = []
    for psi in solve_quadratic(quadratic):
        roots.append(PublicInteriorRoot(e=e_fixed, psi=psi))
    return roots


def m_values(eta_W: float, rho: float, c0W: float, X_L: float, X_H: float) -> tuple[float, float, float]:
    """m_0 = eta_W/c_0^W, m_L = eta_W/(rho X_L), m_H = eta_W/(rho X_H).

    Returns NaN for any component whose denominator is exactly zero (a
    candidate with c_0^W=0 or X_j=0 is inadmissible -- callers filter it out
    via the transfer/positive-wealth checks -- rather than raising, so a grid
    or bisection search that happens to land exactly on this measure-zero
    set can treat the point as invalid instead of crashing).
    """

    m0 = eta_W / c0W if c0W != 0.0 else math.nan
    mL = eta_W / (rho * X_L) if X_L != 0.0 else math.nan
    mH = eta_W / (rho * X_H) if X_H != 0.0 else math.nan
    return m0, mL, mH


def debt_boundary_quadratic_coefficients(
    *, k: float, I_0: float, iota_star: float, rbar_0: float, Lambda: float, H_L: float, H_H: float, J_L: float, J_H: float, lambda_L: float, lambda_H: float, rho: float, Delta_0: float
) -> Quadratic:
    """The nu_B-eliminated boundary equation, cleared of its X_L/X_H/c_0^W denominators
    (each affine in e when psi=e is imposed), as a genuine quadratic in e.

    Derivation: on the boundary, the two modified public FOCs (model doc section 18) are
        (I)  sum_j lambda_j m_j J_j - m_0 Lambda + nu_B = 0
        (II) Delta_0 m_0 - sum_j lambda_j m_j + nu_B = 0
    (I) - (II) eliminates nu_B:
        sum_j lambda_j m_j (J_j + 1) - m_0 (Lambda + Delta_0) = 0
    which, cleared of denominators, is

        lambda_L(J_L+1) X_H c_0^W + lambda_H(J_H+1) X_L c_0^W - rho(Lambda+Delta_0) X_L X_H = 0

    Solved this way (rather than as the rational form in debt_boundary_equation
    below) because the rational form has poles at X_L=X_H=c_0^W=0 that a
    grid/bracket search can mistake for sign-change roots; a cleared polynomial
    has none. debt_boundary_equation is kept for diagnostics.py's independent
    check -- it evaluates the *uncleared* equation at the polynomial's root.
    """

    X_L: Affine = (1.0 + J_L, H_L)
    X_H: Affine = (1.0 + J_H, H_H)
    d_0 = net_production_0(I_0, k, iota_star)
    c0W: Affine = (rbar_0 - Lambda, d_0)

    term1 = _affine_multiply(X_H, c0W)
    term1 = (lambda_L * (J_L + 1.0) * term1[0], lambda_L * (J_L + 1.0) * term1[1], lambda_L * (J_L + 1.0) * term1[2])
    term2 = _affine_multiply(X_L, c0W)
    term2 = (lambda_H * (J_H + 1.0) * term2[0], lambda_H * (J_H + 1.0) * term2[1], lambda_H * (J_H + 1.0) * term2[2])
    term3 = _affine_multiply(X_L, X_H)
    scale3 = -rho * (Lambda + Delta_0)
    term3 = (scale3 * term3[0], scale3 * term3[1], scale3 * term3[2])
    return (term1[0] + term2[0] + term3[0], term1[1] + term2[1] + term3[1], term1[2] + term2[2] + term3[2])


def debt_boundary_equation(e: float, *, k: float, I_0: float, iota_star: float, rbar_0: float, Lambda: float, H_L: float, H_H: float, J_L: float, J_H: float, lambda_L: float, lambda_H: float, eta_W: float, rho: float, Delta_0: float) -> float:
    """The nu_B-eliminated equation on the b=psi=e boundary, i.e. (I) - (II) above:
    sum_j lambda_j m_j (J_j + 1) - m_0 (Lambda + Delta_0) = 0, as a function of e alone."""

    d_0 = net_production_0(I_0, k, iota_star)
    X_L = e * (1.0 + J_L) + H_L
    X_H = e * (1.0 + J_H) + H_H
    c0W = d_0 + e * (rbar_0 - Lambda)
    m0, mL, mH = m_values(eta_W, rho, c0W, X_L, X_H)
    return lambda_L * mL * (J_L + 1.0) + lambda_H * mH * (J_H + 1.0) - m0 * (Lambda + Delta_0)


def debt_boundary_multiplier(e: float, *, k: float, I_0: float, iota_star: float, rbar_0: float, Lambda: float, H_L: float, H_H: float, J_L: float, J_H: float, lambda_L: float, lambda_H: float, eta_W: float, rho: float, Delta_0: float) -> tuple[float, float]:
    """nu_B recovered from FOC (I) and, separately, from FOC (II) -- both should agree."""

    d_0 = net_production_0(I_0, k, iota_star)
    X_L = e * (1.0 + J_L) + H_L
    X_H = e * (1.0 + J_H) + H_H
    c0W = d_0 + e * (rbar_0 - Lambda)
    m0, mL, mH = m_values(eta_W, rho, c0W, X_L, X_H)
    nu_B_from_portfolio_foc = m0 * Lambda - (lambda_L * mL * J_L + lambda_H * mH * J_H)
    nu_B_from_saving_foc = (lambda_L * mL + lambda_H * mH) - Delta_0 * m0
    return nu_B_from_portfolio_foc, nu_B_from_saving_foc


def jump_derivative_k(q_prime_at_k: float, q_star: float) -> float:
    """J_{j,k} = q_j'(k)/q^star."""

    return q_prime_at_k / q_star


def jump_derivative_iota(phi: float, q_star: float, J_j: float) -> float:
    """J_{j,iota} = -(phi/q^star)(1+J_j)."""

    return -(phi / q_star) * (1.0 + J_j)


def compensator_derivative(lambda_L_star: float, lambda_H_star: float, J_L_x: float, J_H_x: float) -> float:
    """Lambda_x = lambda_L^star J_{L,x} + lambda_H^star J_{H,x}, for x in {k, iota}."""

    return lambda_L_star * J_L_x + lambda_H_star * J_H_x


def envelope_O(eta_K: float, rho: float, pi: float, lambda_L: float, lambda_H: float, J_L: float, J_H: float, J_L_x: float, J_H_x: float, Lambda_x: float) -> float:
    """O_x = (eta_K pi / rho) [sum_j lambda_j J_{j,x}/(1+pi J_j) - Lambda_x]."""

    interior_sum = lambda_L * J_L_x / (1.0 + pi * J_L) + lambda_H * J_H_x / (1.0 + pi * J_H)
    return (eta_K * pi / rho) * (interior_sum - Lambda_x)


def capital_residual(
    *,
    k: float,
    psi: float,
    pi: float,
    m0: float,
    mL: float,
    mH: float,
    rho: float,
    lambda_intensity: float,
    q_star: float,
    iota_star: float,
    I_0: float,
    lambda_L: float,
    lambda_H: float,
    J_L: float,
    J_H: float,
    J_L_k: float,
    J_H_k: float,
    Lambda_k: float,
    Lambda_iota: float,
    O_k: float,
    O_iota: float,
    A_iota: float,
    q_L_at_k: float,
    q_H_at_k: float,
) -> float:
    """K(k) := (rho+lambda)(q^star/k) A_iota(k) - m_0[R_0(k)-iota^star-psi Lambda_k]
    - sum_j lambda_j m_j [q_j(k)+psi J_{j,k}] - O_k."""

    R0 = rental(I_0, k)
    term1 = (rho + lambda_intensity) * (q_star / k) * A_iota
    term2 = m0 * (R0 - iota_star - psi * Lambda_k)
    term3 = lambda_L * mL * (q_L_at_k + psi * J_L_k) + lambda_H * mH * (q_H_at_k + psi * J_H_k)
    return term1 - term2 - term3 - O_k


def capital_residual_A_iota(*, k: float, psi: float, m0: float, lambda_L: float, lambda_H: float, mL: float, mH: float, Lambda_iota: float, J_L_iota: float, J_H_iota: float, O_iota: float) -> float:
    """A_iota(k) = m_0[k + psi Lambda_iota] - sum_j lambda_j m_j psi J_{j,iota} - O_iota."""

    return m0 * (k + psi * Lambda_iota) - (lambda_L * mL * psi * J_L_iota + lambda_H * mH * psi * J_H_iota) - O_iota


def tax_recovery_pre(rbar_0: float, q_star: float, iota_star: float, Lambda: float, R_0_at_k: float) -> float:
    """tau_0^{K,star} = 1 - [rbar_0 q^star + iota^star - q^star Lambda(k)] / R_0(k)."""

    return 1.0 - (rbar_0 * q_star + iota_star - q_star * Lambda) / R_0_at_k


@dataclass(frozen=True)
class Recovery:
    d_0: float
    c0W: float
    t_0: float
    f_0: float
    theta_0: float
    b_0: float
    tau_0: float
    e_L_plus: float
    e_H_plus: float
    f_L_plus: float
    f_H_plus: float
    a_L_plus: float
    a_H_plus: float
    n_0: float
    gamma_a: float


def recover(
    *, k: float, e: float, psi: float, pi: float, a_0: float, I_0: float, iota_star: float, rbar_0: float, rho: float, Lambda: float, J_L: float, J_H: float, H_L: float, H_H: float, q_star: float, q_L_at_k: float, q_H_at_k: float
) -> Recovery:
    d_0 = net_production_0(I_0, k, iota_star)
    c0W = d_0 + rbar_0 * e - psi * Lambda
    w_0 = (1.0 - I_0) * output(I_0, k)
    t_0 = c0W - w_0
    f_0 = e + q_star * k
    theta_0 = psi + q_star * k
    b_0 = psi - e
    R0 = rental(I_0, k)
    tau_0 = tax_recovery_pre(rbar_0, q_star, iota_star, Lambda, R0)
    e_L_plus = e + psi * J_L
    e_H_plus = e + psi * J_H
    f_L_plus = e_L_plus + q_L_at_k * k
    f_H_plus = e_H_plus + q_H_at_k * k
    a_L_plus = a_0 * (1.0 + pi * J_L)
    a_H_plus = a_0 * (1.0 + pi * J_H)
    n_0 = a_0 + e
    gamma_a = rbar_0 - rho - pi * Lambda
    return Recovery(
        d_0=d_0,
        c0W=c0W,
        t_0=t_0,
        f_0=f_0,
        theta_0=theta_0,
        b_0=b_0,
        tau_0=tau_0,
        e_L_plus=e_L_plus,
        e_H_plus=e_H_plus,
        f_L_plus=f_L_plus,
        f_H_plus=f_H_plus,
        a_L_plus=a_L_plus,
        a_H_plus=a_H_plus,
        n_0=n_0,
        gamma_a=gamma_a,
    )
