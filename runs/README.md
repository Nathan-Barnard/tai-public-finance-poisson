# Runs

Immutable records of material executions for this repository's computational
work, using the naming convention shared with the codex workspace's
`computation/runs/`:

```text
RUN-YYYYMMDDTHHMMSSZ-CS###-<git-short-sha>-NN.yaml
```

One file per execution that informs a model choice, result, figure,
calibration, benchmark, cost estimate, or publication claim. Smoke runs used
only while coding don't need one.

Never edit a completed record; supersede with a new one and cross-link. Keep
large arrays, checkpoints, and figures out of git — reference them by content
hash and size instead.

- [`RUN-20260902T211134Z-CS005-45f5d452-01.yaml`](RUN-20260902T211134Z-CS005-45f5d452-01.yaml)
  — **preferred evidence record.** Native rerun of the CS005 first real
  prototype under the same provisional calibration `P-CS005-REAL-01` (EMP005),
  executed 2026-09-02 in this repository from a clean tree at commit
  `45f5d452` (resolvable here; identical run fingerprint
  `f3582297…`, and every numerical quantity matches the imported legacy run
  exactly). Still a **first real prototype / reduced-coverage computational
  pass, not a decision-grade CS005 pass** — machine-readable in the record as
  `decision_grade: false`, `coverage: reduced`,
  `pm08_cs005_tolerance_pass: false`, `strict_viability_checked: false`;
  W2/W3/W4/W5 out of scope. 4 stationary atlas candidates, 1 admissible under
  the implemented checks, 0 matching the inherited EMP005 state. Bundle under
  `../outputs/cs005-marked-poisson-first-real-rerun/`.
- [`RUN-20260902T203112Z-CS005-4f27d1d7-01.yaml`](RUN-20260902T203112Z-CS005-4f27d1d7-01.yaml)
  — CS005 first real prototype / reduced-coverage computational pass under the
  provisional calibration `P-CS005-REAL-01` (EMP005), executed 2026-09-02 in
  the legacy worktree and imported here the same day (the recorded commit
  `4f27d1d7` belongs to the legacy `tai-public-finance` history and is not
  resolvable in this repository; see the record's import provenance note).
  **Not a decision-grade CS005 pass**: PM08 tail/transversality diagnostics do
  not pass CS005-level tolerance, the root search is reduced-coverage, and
  W2/W3/W4/W5 are out of scope. 4 stationary atlas candidates found, 1
  admissible under the implemented checks, 0 matching the inherited EMP005
  state. Bundle under `../outputs/cs005-marked-poisson-first-real/`. Kept as
  provenance/history; superseded as the preferred evidence record by the
  native rerun above.
