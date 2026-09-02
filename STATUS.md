# Status

Live "who's doing what" board for the concurrent Claude Code sessions that
work on this repository (`tai-public-finance-poisson`). Update your own row
when you start and when you finish; don't edit anyone else's. This is a
convenience, not a lock — use `ListAgents` and message the owning session
directly before touching a branch someone else's row claims.

| Session | Location | Branch | Task | Status |
|---|---|---|---|---|
| tai-poisson-import-01 | primary checkout | `main` | Import the CS005 marked-Poisson first-real implementation from the legacy worktree `../TAI public finnace claude-cs005-marked-poisson-first-real` into this dedicated repository, with status language corrected at import | done 2026-09-02: imported `src/tai_public_finance/cs005_marked_poisson/`, `tests/cs005_marked_poisson/`, `configs/cs005/`, run record `RUN-20260902T203112Z-CS005-4f27d1d7-01`, and `outputs/cs005-marked-poisson-first-real/`. The run is a **first real prototype / reduced-coverage computational pass, not a decision-grade CS005 pass**: PM08 tail/transversality diagnostics do not pass CS005-level tolerance, and W2 (two-tranche rank), W3 (tax-span cone), W4 (fixed-mark), and W5 (strict viability) remain out of scope. Substantive result retained with those qualifications: 4 stationary atlas candidates, 1 admissible under the implemented checks, 0 matching the inherited EMP005 state. |

*Seeded 2026-09-02 at the first import; keep it current from here.*
