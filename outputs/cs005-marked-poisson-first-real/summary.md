# RUN-20260902T203112Z-CS005-4f27d1d7-01

First real prototype: a reduced-coverage computational pass under the draft
specification, **not** a decision-grade CS005 pass.

- Outcome: `computational_pass` in the reduced-coverage prototype sense above
- Profile: `P-CS005-REAL-01` (spec CS005 v0.7, status draft -- exploratory first attempt)
- Post-mark blocks: L and H structural checks (PM01-PM07) pass at solver
  tolerance; **PM08 tail/transversality does not pass CS005-level tolerance**
  (forward-shooting unstable-eigenvector projections of order 5e-3 to 5e-2
  against the 1e-8 bound at the specified T_j horizons -- see the run record's
  limitations for why, and for what PM01-PM04 do and do not establish instead)
- Candidates found: 4 (discarded non-convergent brackets: 5)
- Fully admissible under the implemented checks: 1
- Date-zero (inherited-EMP005-state-matching) candidates: 0
- Out of scope for this first pass: W2 (two-tranche rank), W3 (tax-span cone),
  W4 (fixed-mark diagnostic), W5 (strict-viability frontiers) -- a candidate's
  admissibility here does not include fiscal-capacity viability

Interpretation: every candidate is a conditional rest point/atlas entry unless
explicitly marked otherwise; a numerical root is not evidence of existence,
uniqueness, global optimality, or equilibrium. See report.json and the run
record's `limitations` for what this run does and does not establish.

*(Revised at import into `tai-public-finance-poisson` on 2026-09-02 to correct
status language only; all numerical content is unchanged from the run. The
original wording had sha256
`ee301527a82638cb672db33bc7e115351bb28c2979d5a35fcc827da66df8929b`.)*
