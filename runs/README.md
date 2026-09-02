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

- [`RUN-20260902T220418Z-CS005-5a264b83-01.yaml`](RUN-20260902T220418Z-CS005-5a264b83-01.yaml)
  — **preferred evidence record (W5 strict viability).** Rerun of the CS005
  first real prototype under the same provisional calibration
  `P-CS005-REAL-01` (EMP005), executed 2026-09-02 from a clean tree at commit
  `5a264b83` (branch `cs005/w5-strict-viability-frontiers`), adding W5 strict
  support-based fiscal viability: each candidate's successor public wealth
  `f_j^+` is certified against the branch-specific lower frontier
  `underline_f_j(k, ell) = -C_j(k, ell)` via a certified-inner constant-tax
  witness lower bound on capacity (feasible paths on the rescaled certified
  zero-tax stable manifold, independently re-integrated at four-times-finer
  tolerance) and CS005's coarse `tau=1` compact-domain outer bound. Labels:
  1 `certified_viable` (an otherwise-inadmissible high-wealth candidate),
  2 `frontier_unresolved`, 1 `certified_infeasible_on_declared_domain`.
  **The previously admissible candidate is `frontier_unresolved` on both
  marks** (successor wealth ≈ −61.9 (L) / −115.7 (H) against certified
  capacity lower bounds ≈ 17.4 / 46.1 and outer bounds ≈ 152 / 1076): it is
  neither certified strictly viable nor refuted, so `n_admissible: 0` under
  the new W5-inclusive definition while `n_admissible_ex_w5: 1` preserves the
  pre-W5 count. Candidate counts otherwise unchanged (4 atlas, 0 date-zero);
  `pm08_cs005_tolerance_pass: true`; still `decision_grade: false`,
  `coverage: reduced` (reduced-coverage root search; W2/W3/W4 out of scope;
  the W5 lower/upper capacity gap is not closed to CS005's 1e-4 tolerance, so
  no claimed frontier is reported). The run fingerprint differs from earlier
  records because the experiment now includes the W5 method. Bundle under
  `../outputs/cs005-w5-strict-viability/`.
- [`RUN-20260902T212539Z-CS005-d1e3ea99-01.yaml`](RUN-20260902T212539Z-CS005-d1e3ea99-01.yaml)
  — **preferred post-mark-tail evidence record; superseded as the overall
  preferred record by the W5 run above.** Rerun of the CS005 first
  real prototype under the same provisional calibration `P-CS005-REAL-01`
  (EMP005), executed 2026-09-02 from a clean tree at commit `d1e3ea99`
  (branch `cs005/pm08-tail-certificate`), after replacing the decisive PM08
  tail/transversality check: backward true-time integration from a local
  linear tail attached at the anchor (contracting in the unstable direction)
  instead of forward saddle-path shooting (amplifying; retained as a
  warning-level diagnostic). `pm08_cs005_tolerance_pass: true` — the
  certificate meets the 1e-8 independent tolerance for both marks
  (manifold-match residuals ~1e-12, saddle-path exclusion bounds ~1e-12).
  Everything else is unchanged: same run fingerprint as the earlier records,
  4 stationary atlas candidates, 1 admissible, 0 matching the inherited
  EMP005 state; still `decision_grade: false`, `coverage: reduced`,
  `strict_viability_checked: false` (reduced-coverage root search; W2/W3/W4/W5
  out of scope). Bundle under `../outputs/cs005-pm08-tail-certificate/`.
- [`RUN-20260902T211134Z-CS005-45f5d452-01.yaml`](RUN-20260902T211134Z-CS005-45f5d452-01.yaml)
  — Native rerun of the CS005 first real
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
  `../outputs/cs005-marked-poisson-first-real-rerun/`. Kept as
  provenance/history; superseded as the preferred evidence record by the
  PM08-certificate rerun above (its `pm08_cs005_tolerance_pass: false`
  reflects the old forward-shooting check, since repaired).
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
