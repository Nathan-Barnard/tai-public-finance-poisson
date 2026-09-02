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
- W2 (two-tranche rank), W3 (tax-span cone), and W4 (fixed-mark diagnostic)
  remain out of scope.

PM08 tail/transversality now **passes CS005-level tolerance** (2026-09-02):
the decisive certificate is backward true-time integration from a local
linear tail attached at the anchor (`diagnostics.certify_postmark_tail`),
which contracts off-manifold deviations at rate nu_+ instead of amplifying
them the way the original forward-shooting check did. The forward-shooting
diagnostic is retained as a warning-level indicator only. The certificate
covers the certified post-mark [k_min, k_max] domain with a linearized
contraction bound — a numerical certificate, not a computer-assisted proof.

W5 strict fiscal viability is now **checked conservatively** (2026-09-02):
each candidate's successor public wealth `f_j^+` is certified against the
branch-specific lower fiscal-capacity frontier
`underline_f_j(k, ell) = -C_j(k, ell)` using a certified-inner lower bound on
capacity (a feasible constant-tax witness family living on the rescaled
certified zero-tax stable manifold, independently re-integrated at
four-times-finer tolerance) and CS005's coarse `tau=1` compact-domain outer
bound. Per CS005, only three labels are possible — `certified_viable`,
`certified_infeasible_on_declared_domain`, `frontier_unresolved` — and
`frontier_unresolved` is a certification gap, never an infeasibility finding.
The lower/upper capacity gap is not closed to CS005's 1e-4 tolerance, so no
claimed frontier is reported; the full I5 collocation protocol remains
outstanding.

Substantive prototype result, with the qualifications above: 4 stationary
atlas candidates found, 0 matching the inherited EMP005 state; **0 candidates
fully admissible once admissibility includes certified W5 strict viability**
(1 candidate remains admissible under the pre-W5 implemented checks,
`admissible_ex_w5`, but is `frontier_unresolved` on both marks — neither
certified strictly viable nor refuted). One otherwise-inadmissible
high-wealth candidate is `certified_viable`; one is certified infeasible on
the declared domain. A numerical root is a candidate, not evidence of
existence, uniqueness, global optimality, or equilibrium; every
Poisson-branch result remains proof-assurance stage S0_unassessed.

Evidence (preferred, native to this repository):
`runs/RUN-20260902T220418Z-CS005-5a264b83-01.yaml` and
`outputs/cs005-w5-strict-viability/` — the W5 strict-viability rerun from a
clean tree at commit `5a264b83`, with `strict_viability_checked: true`,
`pm08_cs005_tolerance_pass: true`, and candidate counts unchanged.
Superseded records, kept as provenance/history:
`runs/RUN-20260902T212539Z-CS005-d1e3ea99-01.yaml` (PM08-certificate rerun,
preferred post-mark-tail evidence, W5 unchecked),
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
