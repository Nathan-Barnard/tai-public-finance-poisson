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

- PM08 tail/transversality diagnostics do not pass CS005-level tolerance
  (a known forward-shooting limitation; see the run record's limitations).
- The root search is reduced-coverage relative to CS005's full multi-start
  protocol.
- W2 (two-tranche rank), W3 (tax-span cone), W4 (fixed-mark diagnostic), and
  W5 (strict-viability frontiers) are out of scope for this first import.

Substantive prototype result, with the qualifications above: 4 stationary
atlas candidates found, 1 admissible under the implemented checks, 0 matching
the inherited EMP005 state. A numerical root is a candidate, not evidence of
existence, uniqueness, global optimality, or equilibrium; every Poisson-branch
result remains proof-assurance stage S0_unassessed.

Evidence (preferred, native to this repository):
`runs/RUN-20260902T211134Z-CS005-45f5d452-01.yaml` and
`outputs/cs005-marked-poisson-first-real-rerun/` — a rerun from a clean tree
at commit `45f5d452`, numerically identical to the import (same run
fingerprint). The imported legacy record
`runs/RUN-20260902T203112Z-CS005-4f27d1d7-01.yaml` and
`outputs/cs005-marked-poisson-first-real/` are kept as provenance/history;
the commit they name belongs to the legacy repository and is not resolvable
here.

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
