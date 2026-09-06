# CS012 I2a — successor boundary and public prefunding under P-CS012-ECO-02

**Result use: `exploratory_only`.** Successor-side evidence only. No government kernel,
welfare result, equilibrium claim, or optimal portfolio. CS012 v0.1 is a draft.

## The contrast this block establishes

Full automation eliminates worker human wealth. On the full-AK branch productive human
wealth exactly offsets installed-capital value, so worker resources are just the
inherited public safe buffer, `X_F = F`. Worker consumption is `ρF` and the successor
marginal value is `1/(ρF)`, which **diverges like 1/F** as the buffer vanishes. At
`F = 0` exactly, worker consumption is zero and the successor marginal value is positive
infinity — a structural boundary, returned as a tagged extended real and kept out of
every logarithm and finite difference.

Partial automation does not do this. It retains positive worker human wealth net of
installed-capital value — `H_P(K₀) − q_P(K₀)K₀ = 4.867098006` —
so `X_P = F + 4.867098006` stays bounded away from
zero and its successor marginal value has a **finite limit** of about
5.136531.

| F | X_P | V_{P,e} | X_F | V_{F,e} |
|---:|---:|---:|---:|---:|
| 1 | 5.867098006 | 4.261050348 | 1 | 25.000000 |
| 0.3 | 5.167098006 | 4.838305751 | 0.3 | 83.333333 |
| 0.1 | 4.967098006 | 5.033119937 | 0.1 | 250.000000 |
| 0.03 | 4.897098006 | 5.105064258 | 0.03 | 833.333333 |
| 0.01 | 4.877098006 | 5.125999102 | 0.01 | 2500.000000 |
| 0.003 | 4.870098006 | 5.133366920 | 0.003 | 8333.333333 |
| 0.001 | 4.868098006 | 5.135475902 | 0.001 | 25000.000000 |

The log–log elasticities make the same point sharply. The full-AK elasticity is exactly
−1 at every adjacent pair; the partial elasticity runs
-0.105525 → -0.000374,
approaching zero rather than −1.

## What this is not

It is not evidence about an optimal government portfolio, and not yet a government
kernel of any kind. The normalized kernel `k^G_j = V_{j,e}/μ_e` needs the pre-event
optimized government marginal value in the denominator. The closure audit reports:

```
pre_event_mu_e_status: unavailable_missing_optimized_pre_event_value_gradient
```

The pre-arrival costate system exists at the pinned commit only as *equations* — solving
it is CS011 block N4, which is not implemented there — and the one candidate, `μ_e = 1/C`
from the interior consumption condition, would need `C` from a solved optimized
continuation. Supplying `C` by hand would make it a fixed-policy derivative, which CS012
explicitly excludes. So no `k^G` and no `γ` are reported here, rather than being
approximated.

The values above are numerators. They are informative about the boundary's structure and
about which branch is fragile as public wealth vanishes, and about nothing else yet.

## SYN-02

`P-CS012-SYN-02` is a directly constructed analytic fixture replacing the false
"stationary-compatible" label carried by `P-CS012-SYN-01`, which is quarantined and
unmodified. It is stationary-compatible by construction: `r_F − ρ − g = 0` exactly, with
`q_F = exp[φ(g+δ)]` and `A_bar` inverted from the zero-tax user-cost equation. It has no
economic interpretation and is not a two-mark scenario.
