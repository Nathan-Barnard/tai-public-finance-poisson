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

- [`RUN-20260905T222042Z-CS012-8c738c6d-01.yaml`](RUN-20260905T222042Z-CS012-8c738c6d-01.yaml)
  — **preferred CS012 I0 evidence record (bounded independent-review repair;
  exploratory only).** Supersedes `RUN-20260905T210214Z-CS012-09830d98-01`
  without withdrawing it. Executed 2026-09-05 from a clean tree at commit
  `8c738c6d` under CS012 v0.1, SHA-256
  `d345f07cdeaf6901fd1ea985cb2566d8c717e4b4dce5ba9fa489375b895d0498`. Two
  defects repaired: the owner-root solver decided existence by searching 200
  geometric doublings and so reported a root at `1e100` as absent — existence is
  now decided analytically from strict monotonicity plus the residual limit,
  with bracketing that exhausts every FP64 binade and a new
  `finite_root_not_representable` status for a root proven to exist beyond
  double precision; and `project_fiscal_gap`'s "catastrophic cancellation" guard
  was unreachable, since a sum of nonnegative weighted squares is never below its
  largest term — it is removed and replaced by an honest underflow case kept
  distinct from a structurally zero payoff vector. The six manufactured
  fixtures, all kernel values, both identity discrepancies, every status count,
  and all five reported maxima are unchanged (one root moved two units in the
  last place, toward its analytic value, because the bracket changed; explained
  in the record). Output
  `outputs/cs012-i0-pricing-kernel-identities-repair-01/identity_report.json`
  (`f1ee44f4…`, 38 673 bytes). **Still no economic calibration, successor,
  transition, prefunding family, portfolio grid, or plot.** Ready for
  independent review; not accepted, not merged, not pushed.

- [`RUN-20260905T210214Z-CS012-09830d98-01.yaml`](RUN-20260905T210214Z-CS012-09830d98-01.yaml)
  — **superseded by `RUN-20260905T222042Z-CS012-8c738c6d-01`; retained and still
  valid as historical exploratory evidence under the CS012 hash it records,
  `275cf384…`.** CS012 I0 pricing-kernel identity core (exploratory only; separate
  specification from CS005, so it neither supersedes nor is superseded by the
  records below).** Parameter-free manufactured-fixture run executed 2026-09-05
  from a clean tree at commit `09830d98` (branch
  `cs012/i0-pricing-kernel-identities`, based on `74c736f8`) under draft
  CS012 v0.1, SHA-256
  `275cf384a6aa8f12831bd0e7b8b8ea4291e49402f3578a9c301baf91fe2930e8`. It checks
  the three jump pricing-kernel definitions, the exact `D_G = D_K + D_GK`
  decomposition and its relative-kernel form, the owner exposure interval and
  portfolio-pricing root, the intensity-weighted marketed projection and
  orthogonal fiscal gap, the exact safe-account payoff rank, and the literal
  laissez-faire extended-real boundary, each reconstructed term by term by a
  standard-library-only independent checker. Maximum discrepancies 1.4e-17
  (identity), 1.0e-17 (production versus independent), 6.7e-18 (owner-root
  residual), 1.7e-17 (weighted orthogonality). Output
  `outputs/cs012-i0-pricing-kernel-identities/identity_report.json`
  (`2ce7e59d…`, 38 087 bytes). **No economic calibration, successor, transition,
  prefunding family, portfolio grid, or plot**, and nothing here supports a
  finite government kernel path, a portfolio sign, a welfare conclusion, an
  existence result, or an optimal portfolio. Ready for independent review; not
  accepted, not merged, not pushed.

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
