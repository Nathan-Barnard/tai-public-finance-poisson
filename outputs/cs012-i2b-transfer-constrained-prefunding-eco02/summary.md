# CS012 I2b — transfer-constrained successor values (P-CS012-ECO-02)

**Result use: `exploratory_only`.** Constrained successor-side evidence only. No
government kernel, welfare result, equilibrium claim, or optimal portfolio. CS012 v0.1
is a draft.

## What changed, and why it mattered

The I2a partial rows priced the *unrestricted* annuity `C = ρX`, `V = 1/(ρX)`. That
allocation is only feasible where the nonnegative-transfer constraint is slack for all
`t`. Here the government may choose the timing of transfers and safe saving but cannot
tax, so workers consume wages plus a nonnegative transfer, and the constrained optimum is

```
C_t = max{ W_P(K_t), A·e^{(r_P−ρ)t} },   T_t = C_t − W_P(K_t) ≥ 0,
F = ∫₀^∞ e^{−r_P t} T_t dt,               V_{P,e} = 1/A.
```

| F | active set | switch (yr) | V_{P,e} |
|---:|---|---:|---:|
| 1 | boundary_active | 38.5401654776123 | 4.5664527129 |
| 0.3 | boundary_active | 18.69321881122939 | 5.6329412368 |
| 0.1 | boundary_active | 9.77317276587308 | 6.2928185835 |
| 0.03 | boundary_active | 4.980143019574578 | 6.7637107165 |
| 0.01 | boundary_active | 2.7661757308327948 | 7.0300851997 |
| 0.003 | boundary_active | 1.4789584052795886 | 7.2049260335 |
| 0.001 | boundary_active | 0.8433750695526989 | 7.2977621592 |

Active sets: {'globally_transfer_interior': 0, 'transfer_boundary_active': 7}. The wage path runs from `W_P(K₀) = 0.13461666352`
to `W_P(∞) = 0.14916860501`, and the present-value wage identity
`H_P − q_P K = 4.867098005847` is reproduced by direct integration to
9.64e-11.

This scenario designates no main interior reference.

## The boundary

As `F → 0⁺` the switch collapses to zero and `A → W_P(K₀)`, so the partial successor
marginal value tends to **7.4285008545 = 1/W_P(K₀)** — not the
5.1365 that I2a reported from the unrestricted formula. The full-AK
branch is unchanged: `W_F = 0`, transfers are strictly positive for every `F > 0`, and
`V_{F,e} = 1/(ρF)` diverges with unit elasticity.

## What this still cannot say

`k^G = V_{j,e}/μ_e` remains unavailable: the closure audit reports
`unavailable_missing_optimized_pre_event_value_gradient`. These are numerators. Nothing here
is a government kernel, a portfolio direction, or a welfare statement.
