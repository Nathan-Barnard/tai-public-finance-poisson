# Status

Live "who's doing what" board for the concurrent Claude Code sessions that
work on this repository (`tai-public-finance-poisson`). Update your own row
when you start and when you finish; don't edit anyone else's. This is a
convenience, not a lock — use `ListAgents` and message the owning session
directly before touching a branch someone else's row claims.

| Session | Location | Branch | Task | Status |
|---|---|---|---|---|
| tai-poisson-import-01 | primary checkout | `main` | Import the CS005 marked-Poisson first-real implementation from the legacy worktree `../TAI public finnace claude-cs005-marked-poisson-first-real` into this dedicated repository, with status language corrected at import | done 2026-09-02: imported `src/tai_public_finance/cs005_marked_poisson/`, `tests/cs005_marked_poisson/`, `configs/cs005/`, run record `RUN-20260902T203112Z-CS005-4f27d1d7-01`, and `outputs/cs005-marked-poisson-first-real/`. The run is a **first real prototype / reduced-coverage computational pass, not a decision-grade CS005 pass**: PM08 tail/transversality diagnostics do not pass CS005-level tolerance, and W2 (two-tranche rank), W3 (tax-span cone), W4 (fixed-mark), and W5 (strict viability) remain out of scope. Substantive result retained with those qualifications: 4 stationary atlas candidates, 1 admissible under the implemented checks, 0 matching the inherited EMP005 state. |

| tai-poisson-native-rerun-01 | primary checkout | `main` | Native CS005 first-real rerun: fix the run-record repository URL, add machine-readable decision-grade/coverage fields, rerun the prototype from a clean tree at a commit resolvable in this repository, write a new immutable run record | done 2026-09-02: run `RUN-20260902T211134Z-CS005-45f5d452-01` executed from a clean tree at `45f5d452` (this repository, `main`); numerically identical to the imported legacy run (same run fingerprint, zero field-level differences). Record and reports now carry `decision_grade: false`, `coverage: reduced`, `pm08_cs005_tolerance_pass: false`, `strict_viability_checked: false`; still **not a decision-grade CS005 pass** (PM08 tail below CS005 tolerance; W2/W3/W4/W5 out of scope). Legacy record kept as provenance. `runs/README.md` and `README.md` point to the native run as preferred evidence. |

*Seeded 2026-09-02 at the first import; keep it current from here.*
