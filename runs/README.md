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

- [`RUN-20260906T015330Z-CS012-e6ef83e5-01.yaml`](RUN-20260906T015330Z-CS012-e6ef83e5-01.yaml)
  — **CS012 block I2a: literal laissez-faire boundary and the positive-prefunding
  family (exploratory only).** A new block, not a replacement: every earlier
  record stays valid and unchanged. Executed 2026-09-06 from a clean tree at
  commit `e6ef83e5`, same unchanged CS011 pin `6b457682…`. **The substantive
  result is a structural contrast at the boundary.** On the full-AK branch
  productive human wealth exactly offsets installed-capital value, so worker
  resources are just the inherited buffer, `X_F = F`; consumption is `ρF` and the
  successor marginal value `1/(ρF)` diverges like `1/F`, with a log-log
  elasticity of exactly −1 at all seven frozen points. Partial automation retains
  `H_P(K₀) − q_P(K₀)K₀ = 4.867098006` of worker human wealth, so its marginal
  value has a **finite** limit near 5.1365 and its elasticity approaches zero
  (−0.1055 → −0.00037). At `F = 0` exactly, full-AK worker consumption is zero
  and the successor marginal value is a tagged positive infinity — never a
  sentinel, never logged, never floored. **The block deliberately stops short of
  a government kernel.** The read-only closure audit reports
  `unavailable_missing_optimized_pre_event_value_gradient`: the pinned dependency
  supplies the pre-arrival costate system as equations only and defers the solve
  to CS011 block N4, so no `k^G` and no `γ` are computed rather than
  approximated. Also lands `P-CS012-SYN-02`, a directly constructed and genuinely
  stationary-compatible analytic benchmark replacing the false label carried by
  `P-CS012-SYN-01`, which is quarantined and unmodified. Output
  `outputs/cs012-i2a-successor-prefunding-eco02/` (`347250aa…`, 23 790 bytes,
  plus `summary.md`). Ready for independent review; not accepted, not merged, not
  pushed.

- [`RUN-20260906T011740Z-CS012-c42cbfd3-01.yaml`](RUN-20260906T011740Z-CS012-c42cbfd3-01.yaml)
  — **CS012 I1 parameter-only rerun under `P-CS012-ECO-02` (exploratory only).**
  A companion to the ECO-01 run below, not a replacement: ECO-01 and its outputs
  remain valid and byte-for-byte unchanged, and the two together are a two-point
  comparison of one primitive, never a sweep or a calibrated range. Executed
  2026-09-06 from a clean tree at commit `c42cbfd3` (parameter commit
  `b1726ba0`), same pinned CS011 dependency `6b457682…`. ECO-02 differs from
  ECO-01 in exactly one operative field, `technology.A_bar` (0.10 →
  0.10329029481590953), derived by inverting the zero-tax world-user-cost
  equation at a target full-AK growth `g_F = 0.026` — a provisional illustrative
  choice, not an estimate. The consequence is economically substantive: full-AK
  growth now exceeds partial growth (`g_F = 0.026 > g_P = 0.0252 > 0`,
  `q_F > q_P > q_0`), both marked payoffs turn positive
  (`J_P = +0.0786`, `J_F = +0.0811`), and the domestic owner's optimal exposure
  reverses from a levered long `+11.02` under ECO-01 to an interior short
  `-4.7887390064`, with both wealth multipliers strictly positive and the owner
  residual at 4.3e-19. The AK block still enumerates two roots and accepts only
  the lower strict-TVC branch, whose margin is exactly `r_F_bar - g_F = 0.004`.
  Output `outputs/cs012-i1-provisional-owner-successors-eco02/` (`d9e70c60…`,
  42 619 bytes, plus `summary.md`). **The synthetic subsection is quarantined**
  for a known provenance defect in `P-CS012-SYN-01` and supports nothing; its
  repair is bundled with I2. **Still no government kernel, prefunding path, time
  path, portfolio direction, welfare number, equilibrium claim, or optimal
  policy.** Ready for independent review; not accepted, not merged, not pushed.

- [`RUN-20260906T001240Z-CS012-ca8a63a6-01.yaml`](RUN-20260906T001240Z-CS012-ca8a63a6-01.yaml)
  — **CS012 block I1: successor services and the laissez-faire owner branch
  (exploratory only).** A different block from the I0 records below; it extends
  and does not supersede them. Executed 2026-09-06 from a clean tree at commit
  `ca8a63a6` under draft CS012 v0.1, SHA-256 `d345f07c…`. The reviewed CS011 N1
  successor package is consumed as a uv VCS dependency pinned by full commit
  `6b457682c4eed8ad4e3bdd867d1292abac38f424`, verified at runtime against the
  installed distribution rather than the request; its N2/N3 stationary machinery
  and its own private-portfolio solver are deliberately not imported and no CS011
  equation is copied. Under the frozen provisional illustrative packet
  `P-CS012-ECO-01`, at `K_0 = 1`: the AK block enumerates two roots and selects
  the lower strict-TVC branch `q_F = 1.1517472652` with the upper root retained
  and its rejection reason; the partial stable manifold covers the whole declared
  `K ∈ [0.5, 2.0]` and refuses extrapolation; payoff jumps are
  `J_P = +0.0786243` and `J_F = -0.0379798`; and the owner exposure
  `pi = 11.0160820` solves the unmultiplied owner FOC to a 2.2e-19 normalized
  residual. Output `outputs/cs012-i1-provisional-owner-successors/`
  (`e078541c…`, 42 406 bytes, plus `summary.md`). **No government kernel,
  prefunding path, time path, portfolio direction, welfare number, equilibrium
  claim, or optimal policy** — those are I2 onward, and DEV-01 records that I1
  ran before their inputs were frozen precisely because none of them enters this
  calculation. Ready for independent review; not accepted, not merged, not
  pushed.

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
