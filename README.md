# tai-public-finance-poisson

Implementation workspace for the marked-Poisson commitment branch of the TAI
public-finance project: Marked-Poisson commitment branch and fiscal-capacity
diagnostics (computational problem CP005), under the Marked-Poisson commitment
and fiscal-capacity computation specification (CS005, currently draft). This is
a separate model branch from the Brownian stack in
[`tai-public-finance`](https://github.com/Nathan-Barnard/tai-public-finance);
it shares engineering conventions with that repository, not equations.

## Status

First real prototype imported 2026-09-02: a **reduced-coverage computational
pass** of the CS005 post-mark stable-manifold and pre-arrival candidate
enumeration blocks under the provisional calibration `P-CS005-REAL-01`
(EMP005). This is **not a decision-grade CS005 pass**:

- The root search is reduced-coverage relative to CS005's full multi-start
  protocol.
- W2 (two-tranche rank), W3 (tax-span cone), W4 (fixed-mark diagnostic), and
  W5 (strict-viability frontiers) are out of scope for this first import.

PM08 tail/transversality now **passes CS005-level tolerance** (2026-09-02):
the decisive certificate is backward true-time integration from a local
linear tail attached at the anchor (`diagnostics.certify_postmark_tail`),
which contracts off-manifold deviations at rate nu_+ instead of amplifying
them the way the original forward-shooting check did. The forward-shooting
diagnostic is retained as a warning-level indicator only. The certificate
covers the certified post-mark [k_min, k_max] domain with a linearized
contraction bound — a numerical certificate, not a computer-assisted proof.

Substantive prototype result, with the qualifications above: 4 stationary
atlas candidates found, 1 admissible under the implemented checks, 0 matching
the inherited EMP005 state. A numerical root is a candidate, not evidence of
existence, uniqueness, global optimality, or equilibrium; every Poisson-branch
result remains proof-assurance stage S0_unassessed.

Evidence (preferred, native to this repository):
`runs/RUN-20260902T212539Z-CS005-d1e3ea99-01.yaml` and
`outputs/cs005-pm08-tail-certificate/` — the PM08-certificate rerun from a
clean tree at commit `d1e3ea99`, with `pm08_cs005_tolerance_pass: true` and
candidate counts unchanged (same run fingerprint as the earlier runs; the
profile and search are identical, only the tail certificate method changed).
Superseded records, kept as provenance/history:
`runs/RUN-20260902T211134Z-CS005-45f5d452-01.yaml` (native rerun, forward
shooting only, PM08 below tolerance) and
`runs/RUN-20260902T203112Z-CS005-4f27d1d7-01.yaml` (the legacy import, whose
commit belongs to the legacy repository and is not resolvable here).

## Setup

```bash
uv sync
```

## Tests

```bash
uv run pytest
```

## Layout

- `src/tai_public_finance/cs005_marked_poisson/` — primitives, post-mark and
  pre-arrival equation construction and solvers, independent diagnostics,
  reporting, CLI
- `tests/cs005_marked_poisson/` — unit, regression, and diagnostics
  mutation tests
- `configs/cs005/` — versioned, fingerprinted profiles and experiment configs
- `runs/` — immutable run records (see `runs/README.md`)
- `outputs/` — small durable per-run outputs
