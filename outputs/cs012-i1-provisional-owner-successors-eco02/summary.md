# CS012 I1 — laissez-faire owner branch under P-CS012-ECO-02

**Result use: `exploratory_only`. Not an equilibrium, not a welfare result, not a
government portfolio.** CS012 v0.1 is a draft; this run neither promotes it nor makes it
review-ready.

## What was computed

At the named provisional pre-arrival state (`K_0 = 1.0`, `q_0 =
1.1972173631`, owner wealth `a_0 = 1.0`), with two labelled
automation marks:

| | partial `P` | full-AK `F` |
|---|---:|---:|
| successor price `q_j` | 1.2913477098 | 1.2943388186 |
| payoff jump `J_j = q_j/q_0 − 1` | +0.07862427454 | +0.08112265867 |
| physical intensity `λ_j` | 0.01625 | 0.00875 |
| risk-neutral intensity `λ*_j` | 0.014 | 0.026 |
| world kernel `k^w_j = λ*_j/λ_j` | 0.8615384615 | 2.9714285714 |
| owner wealth multiplier `X^K_j` | 0.6234888697 | 0.6115247601 |
| owner kernel `k^K_j = 1/X^K_j` | 1.6038778696 | 1.6352567634 |
| owner wealth after `a_0 X^K_j` | 0.6234888697 | 0.6115247601 |
| contribution to `D_K` | +9.484458e-04 | -9.484458e-04 |

Owner exposure `π = -4.788739006`, solving the unmultiplied
`D_K(π) = Σ_j λ_j (1/(1+πJ_j) − λ*_j/λ_j) J_j = 0` on the open positive-wealth interval
`(-12.327012162, +inf)`,
with residual `+0.000e+00` and a strictly negative slope
`-4.123900e-04`.

## Economic content

The world prices the full-AK mark far more heavily than its physical frequency warrants
(`k^w_F = 2.9714` against `k^w_P = 0.8615`): the risk-neutral law is
tilted toward the mark the domestic owner least wants. Given that, and given that
both marks raise installed-equity value here, the owner's optimal exposure is a **short** position of
`-4.788739` times wealth. Owner wealth moves to
`0.6235` times its pre-arrival level on a partial arrival and
`0.6115` times it on a full-AK arrival.

That asymmetry is the whole point of the block: it is the owner-side input the government
comparison will later be made against. It says nothing yet about what a government would
want, because no government object exists at I1.

## Limits

- owner-side pricing objects only: successor prices, marked payoff jumps, world and owner kernels, owner exposure, and the owner residual D_K
- no government kernel, fiscal marginal value, prefunding path, time path, public-portfolio direction, welfare number, equilibrium claim, or optimal policy
- the economic packet is provisional and illustrative, not an estimate or a country calibration
- the inherited state is a named provisional state, not a solved pre-arrival equilibrium
- the diagnostic capital grid is sensitivity only; K_0 remains the baseline
- CS012 v0.1 is a draft and is neither review-ready nor approved

The public installed-equity, safe-asset, and safe-debt positions are all zero here. That
is the I1 owner-side state only and must never be used to form a finite government
kernel; the strictly positive prefunding family is frozen separately before I2.

## Deviation

`DEV-01` — I1 executed before the public-prefunding sequence, continuation horizon,
terminal condition, and government-kernel thresholds are frozen. None enters this
calculation. Owner: Nathan. Independent reviewer: Codex. Expires before any I2
implementation or result run.
