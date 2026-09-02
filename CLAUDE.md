# CLAUDE.md

Guidance for Claude Code in this repository, the **Poisson-shock branch workspace** of
the TAI public-finance project. Read this file first, then the Codex records under
"Canonical references" in the order given, then `STATUS.md` once it exists.

## What this workspace is

This directory was created empty on 2026-09-01 (22:59 BST) and initialised as a Git
repository that evening. Nathan's setup instruction was: new work session; every folder
other than this one is read-only; get acquainted with the materials; write CLAUDE.md.

Role, confirmed by Nathan on 2026-09-02: the dedicated implementation workspace for the
**marked-Poisson commitment branch**: Marked-Poisson commitment branch and fiscal-capacity
diagnostics (computational problem CP005) and its contract, Marked-Poisson commitment
and fiscal-capacity computation (specification CS005). On the Codex side the branch is
coordinated by the Poisson Ramsey model workstream (`poisson-model/`, bootstrapped at
23:02 the same evening).

This is a **fresh repository, not a clone**. The Poisson branch shares no equations,
primitives, welfare objective, or asset definitions with the Brownian Version 5.1 stack,
and the Codex roadmap says not to route it through the Brownian LQ code. Nothing in the
legacy `src/tai_public_finance/primitives/` package applies here. Reuse its
*engineering* patterns (frozen dataclasses, fingerprinted inputs, independent
diagnostics, run records, one CLI per package), never its formulas.

This repository will own executable code, tests, versioned configurations, immutable run
records (`runs/`), small diagnostic outputs (`outputs/`), and a `STATUS.md` session
board. It is an implementation and numerical-verification workspace, **not** a second
theory workspace: a changed assumption, equation, boundary, or acceptance test is a
Codex-side change to the tracker or to CS005, never a local edit.

## Sibling directories (all read-only)

| Directory | Role | Writes |
|---|---|---|
| `/Users/nathanbarnard/Documents/TAI public finnace codex` | **Canonical and read-only.** Nathan's Codex research workspace: model tracker, assurance, economics reviews, computation registry, sources, research notes, voice specs, read-only Overleaf mirrors. Not git-tracked at the root, so cite by path plus SHA-256 and mtime. Its `AGENTS.md` gives Codex the mirror-image rule. | Never edit, move, or delete anything there. Reading freely is invited. |
| `/Users/nathanbarnard/Documents/TAI public finnace claude` | Legacy Claude implementation repository for the Brownian stack (GitHub `Nathan-Barnard/tai-public-finance`, primary checkout on `main`). LQ anchor (CS001) and the UK quasi-empirical pilot (EMP001) continue there. Its conventions are the pattern followed here. | Read-only reference. |
| `/Users/nathanbarnard/Documents/TAI public finnace claude pdes` | Dedicated CS004 five-state PDE workspace (clone of the legacy repo at `1fcf9a8`, branch `cs004/pde-dedicated-workspace`). Its `CLAUDE.md` and `PROJECT_STATUS.md` are the closest template for this file. | Read-only. |
| `/Users/nathanbarnard/Documents/TAI public finnace claude-<slug>` (four) | Legacy worktrees for `cs001/...`, `cs004/...`, and `emp001/...` branches owned by other live sessions. | Read-only. |
| `/Users/nathanbarnard/Documents/TAI public finnace full automation ` (trailing space) | Empty directory created 23:03 on 2026-09-01. Not this workspace's concern. | Do not touch. |

Do **not** copy Codex trackers, registries, the source library, or research architecture
into this repository. Link to the exact canonical file and record its fingerprint.
[`research-context/canonical-references.md`](research-context/canonical-references.md)
holds only that fingerprint table: a staleness detector, never a substitute for the source.

## Canonical references (Codex workspace; re-hash before relying on them)

Paths are relative to the Codex workspace; fingerprints observed at setup are in the
table linked above, and a changed hash means "re-read", not "wrong". Read in this order:

1. **Charter and notebooks:** `poisson-model/README.md` and `poisson-model/AGENTS.md`
   (what is held fixed, the first-stage done test, branch map, research sequence);
   `research-notes/poisson-model-complete-and-incomplete-markets.md` (active reasoning
   surface); `research-notes/single-poisson-shock-and-complete-markets-genealogy.md`
   (manuscript chronology; span versus finance, ownership, and first best).
2. **Contract and computation rules:** CS005 at
   `computation/specifications/marked-poisson-commitment-and-fiscal-capacity--CS005.md`;
   `computation/computation_registry.yaml` (CP005, CA008, CB005, CS005, repository
   binding); `computation/README.md`, `computation/AGENTS.md`, and the "Separate branch —
   marked-Poisson commitment" section of `computation/roadmap.md`; block pacing in
   `computation/decisions/smaller-sequential-implementation-blocks-with-early-progress-updates--CD002.md`;
   the run-record schema `computation/templates/run_record.yaml`.
3. **Economics reviews** under `economics-verification/reviews/`: Poisson branch
   genealogy, tax timing, public portfolios, and safe debt (EV07) and Ramsey
   counterfactual design, inherited-state rents, and interpretation (EV09). Both are
   `sound_with_qualification`; neither raises proof status.
4. **Maintained claims and map:** assumptions `A14`–`A21`, results `R26`–`R37`, and
   questions `Q09`, `Q11`–`Q15`, `Q17`–`Q18` in
   `model-tracker/model_setup_results_tracker.md` (machine form in the ledger); the
   section "Poisson branch: audited hierarchy and result scope" of
   `CURRENT_PROJECT_CONTEXT.md`; `PROJECT_NAMING.md`.
5. **Manuscripts** (read-only mirrors; roles and chronology in `overleaf/README.md`):
   the primary derivation `overleaf/commitment-ramsey-marked-poisson-small-open-economy/main.tex`
   (June 2026); the later (17:23 UTC, regular post-arrival zero-tax tail only, promise
   state retained) and earlier (16:30 UTC, sharper conditional pre-arrival claim)
   same-day fixed-mark drafts in `commitment-ramsey-automation-risk-complete-markets-balanced-growth/`
   and `commitment-ramsey-bgp-complete-markets/`; `setup-conventions-complete-spanning-ramsey/`;
   the tax-timing, safe-debt, and Poisson-versus-diffusion companions. **Not sources:**
   the TANK 1.12 predecessor (never import its equations) and the two empty shells.
6. **How to talk to Nathan:** `voice_specs/chat_style.md`; see the last section here.

`latexmk` is not installed. Read `.tex` for equations and the mirrored PDFs for layout.

## Economic identity of the branch (transcribed, not modifiable here)

Changing any item below is a Codex-side model or specification change (a tracker record
or a new CS005 version), never an implementation edit. Any departure from this baseline
is a *different model*, not evidence about market span.

- **Shock:** one totally inaccessible Poisson arrival with **two absorbing marks** (the
  maintained binary-mark formulation) and one traded risky domestic-equity payoff
  vector. Collapsing the support to **one fixed mark** is a nested diagnostic, not a
  separate institution: jump risk becomes one dimensional, so one nonzero **total-gain**
  jump (never a mere ex-dividend price jump) spans it. That is a payoff-rank result only;
  it does not imply external finance, reassigned productive ownership, admissible
  government positions, complete production markets, or first best (`R29`, `R36`, `A21`).
- **Policy regime:** date-zero commitment with protected inherited claims and a possibly
  nonminimal promise state. Write the inherited augmented state as `(S_0, M_0)`: physical
  and financial stocks in `S_0`; promises, multipliers, and institutional commitments in
  `M_0`. Whether `M_0` can be eliminated (`Q15`) and whether the earlier fixed-mark
  pre-arrival zero-tax theorem survives the later draft's promise state (`Q12`, `Q18`)
  are **open**; never resolve them by assumption in code.
- **Agents and welfare:** hand-to-mouth workers, log-utility domestic capital owners,
  residual foreign investors pricing marginal domestic securities with an exogenous world
  SDF, and a government with **positive Pareto weights on both domestic groups** (`A15`).
- **Assets:** the government holds **domestic installed-capital equity** (not the
  Brownian international hedge) and issues its own **nonnegative safe debt** `B >= 0`;
  riskless public saving through `B < 0` is excluded (`A16`).
- **Tax:** a bounded **predictable** tax `0 <= tau^K <= 1` on **gross rental flows** only:
  no jump levy, no capital-gain tax, no subsidy, no total-return base (`A14`, `A17`).
  Zero tax is the **lower bound**, not an interior control; every zero-tax candidate
  carries a KKT multiplier check (EV07-I03).
- **Technology:** endogenous Tobin's `q` with log installation costs, explicit fiscal and
  specialization constraints, transfers with interiority checks (`A17`).
- **Solution structure** (marked paper, sections 5–8): closed-form absorbing post-mark
  production paths; post-mark transitions from a one-dimensional saddle ODE for `q(k)`
  with `H'(k) = q` and stable-manifold boundary conditions; pre-arrival public saving and
  equity exposure from one linear and one quadratic equation; a private-portfolio
  quadratic; one scalar Ramsey capital residual; tax recovery from world equity pricing;
  then debt-sign, solvency, transfer, tax, transversality, and initial-claim checks.
  Successor `q` comes from the successor stable manifold, never chosen at the jump.
- **Every numerical root is a candidate**, not existence, uniqueness, global optimality,
  a global transition (`Q14`), or a balanced-growth equilibrium. Enumerate roots by
  multi-start and continuation, keep rejected and duplicate roots, filter mark by mark
  (KKT, tax and debt bounds, initial claims, solvency, specialization, transversality),
  and diagnose payoff rank separately from admissibility.
- **Fiscal capacity** is one of four distinct objects, `strict_viability`, `sdf_value`,
  `expected_physical`, or `defaultable` (`A19`, `Q13`): separate runs, never toggle flags
  inside one number. Physical and risk-neutral intensities are never interchanged. A
  convenience-yield or revaluation term is never a public cash resource without its
  service incidence, balance-sheet change, and future obligation. Debt-financed equity
  changes gross composition with net wealth unchanged (`R31`).
- **Counterfactuals** follow `A20` and EV09: name the changed object, decision and
  announcement dates, commitment convention, inherited `(S_0, M_0)`, information and
  shock law, branch selection, horizon, and metric. Common-state instrument values
  `V00..V11` with `Gamma = V11 - V10 - V01 + V00`, forced local directions, sequential
  MIT news, announced reforms, and regime-native endpoints are different experiments
  (`E10`–`E12`).
- **Status:** every Poisson result (`R26`–`R37`) is proof-assurance stage
  `S0_unassessed`. Nothing computed here can raise that; numerical fit is not proof.

## Status and gating (as of 2026-09-01, 23:10 BST)

- CS005 is version 0.1, `draft`, unfingerprinted, with six unresolved items (parameter
  and normalization table; post-mark boundary and transversality normalization;
  equation-to-residual map; root-search domain and coverage; baseline capacity concept;
  proof reviews of `R27`–`R34` and the restart test). CP005 is `proposed`, priority P1,
  tier `T4_hybrid`, default lane `L1_interactive`, maximum `L4_overnight` without a new
  decision. CA008 (post-mark ODE/BVP plus pre-arrival algebraic continuation, SciPy) is
  the only candidate approach, not yet selected. GPU and paid compute are not justified.
- The registry binds `implementation_repository.local_path` to the **legacy** Claude
  repository. Binding the Poisson branch to this directory is a Codex-side edit and
  Nathan's decision; until then every run record here names this repository's path and
  commit explicitly.
- **Default rule:** do not implement CS005's model equations until it is `approved`, or
  until Nathan gives a chat instruction specific enough to function as the approval
  (full parameter vector, explicit scope and exclusions, explicit acceptance standard),
  as he did for CS001 on 2026-09-01. In that case proceed, label every output
  exploratory, state the `draft` status in run records and reports, and say in chat that
  the registry needs a Codex-side update.
- The exploratory-prototype exception in `computation/AGENTS.md` (rule 6) requires an
  **active** problem plus a draft naming provisional primitives, the exact question,
  independent diagnostics, failure categories, repository, and resource ceiling. CP005 is
  `proposed`, so it does not apply on its own.
- Needs no approval: tooling scaffold; solver-independent equation and KKT evaluators on
  manufactured cases; symbolic or numeric checks of manuscript identities (closed-form
  BGP formulas, transformed public budget, fixed-mark rank check). Label it exploratory
  and route any discrepancy to Nathan for the Codex side; never "fix" the manuscript here.

## How work will be structured when it starts

**Blocks (CD002).** Smallest sequential blocks that each leave an independently
reviewable result. Before each: result and non-goals, machine lane, elapsed-time range,
and when to send a progress update. After each: machine runtime and total implementation
time, reported separately. Default sequence, subordinate to whatever CS005 finally
specifies: (0) bind and freeze spec version and hash, parameter and normalization table,
inherited claim and promise convention, capacity concept, source manifest; (1) post-mark
continuation objects: `q(k)` saddle ODE, productive wealth, stable-manifold anchors, and
the post-mark tax, user-cost, transfer, specialization, solvency, and transversality
checks, with no clipping; (2) pre-arrival algebraic block: public saving and exposure,
private-portfolio quadratic, scalar capital residual, tax and balance-sheet recovery,
root enumeration by multi-start and continuation in transformed bounded variables,
admissibility filters mark by mark; (3) fixed-mark collapse, payoff-rank diagnostics,
convergence to the `R30` candidate with every qualification retained, and the
zero-intensity and identical-mark limits; (4) capacity-concept experiments as separate
runs, the commitment restart test, and the common-state nested instrument values.

**Code layout.** Python 3.13 managed with `uv`, src layout, one package for the branch.
Name the package at scaffold time; do not reuse `tai_public_finance` (suggestion:
`tai_poisson`). Inside it: a `primitives/` module (Poisson-branch parameter vector with
fingerprinting, production, installation, world pricing, mark structure) and one package
per specification (`cs005_marked_poisson/`), split into **equation construction, solver,
an independent diagnostics/residual evaluator, and reporting/CLI**. The diagnostics
module recomputes every residual from primitives and final outputs without reusing any
solver intermediate, and is **mutation-tested** before it is called independent: inject
a plausible construction bug in the solver and confirm the diagnostics catch it. The
CS001 review found three independence gaps that way, including one tautological check.

**Configurations:** versioned JSON under `configs/`, fingerprinted (primitive table,
experiment file, complete input), with levels versus balanced-growth ratios explicit.

**Run records.** One immutable `runs/RUN-YYYYMMDDTHHMMSSZ-CS005-<git-short-sha>-NN.yaml`
per material execution, from the Codex template: the commit whose code actually ran from
a clean tree, environment and lock hash, hardware, lane, budget, inputs, independent
diagnostics, artifact hashes and sizes, and interpretation with `A/E/R/Q` links. Never
edit a completed record; supersede and cross-link. Large arrays and figures are
hash-referenced, not committed. Create `runs/README.md` with the first record.

**Compute.** The binary-mark reduction is low dimensional: CPU, FP64, `L1_interactive`
by default, `L2_local_batch` for continuation and coverage sweeps. This machine: Apple
M4 MacBook Air, 10 cores, 16 GB, 4.8 GiB free disk on 2026-09-01; record `df` around
material runs and keep environments small. Paid compute
needs a measured cheaper baseline, cost and admin estimates, a stopping rule, and
Nathan's explicit approval; nothing in CS005 calls for it.

## Commands

Nothing is scaffolded yet. When the first block is authorised, scaffold with `uv`
(Python 3.13; `uv 0.12.5` at `~/.local/bin/uv`) and keep these conventions: `uv sync`
to install; `uv run pytest` for tests; `uv add` / `uv add --dev` for dependencies, never
hand-editing `pyproject.toml`; one CLI per package invoked as
`uv run python -m <package>.<subpackage>.cli --config ... --output-dir ... --run-id ...`.
Never write into an existing immutable output directory; reproduce into scratch and
compare hashes.

## Git and coordination

- **State:** initialised 2026-09-01 on `main`. `origin` is the public GitHub repository
  `https://github.com/Nathan-Barnard/tai-public-finance-poisson`, created at setup on
  Nathan's instruction (2026-09-02). Push only alongside a commit he asked for.
- **Branches:** `cs005/<slug>` for specification work, `chore/<slug>` otherwise; one task,
  one branch, based off `main` unless stacking is deliberate and stated. Machine
  identifiers may be ID-first; prose is name-first.
- **Worktrees:** Nathan runs several Claude Code sessions at once as a matter of course.
  Every task gets its own worktree from the start:
  `git worktree add "../TAI public finnace poisson shock claude-<slug>" -b cs005/<slug>`.
  The primary checkout stays on `main`. The desktop app creates its own worktrees under
  `.claude/worktrees/` (gitignored), branching from the current `main`.
- **Commits:** commit only when asked; one focused commit per block with code, tests,
  outputs, and the run record together; messages explain *why*; never amend, force-push,
  or rewrite shared history; review `git status` and the diff before staging. The legacy
  repository's standing "commit whenever" authorisation does not extend here: Nathan
  said to push once he asks for a commit.
- **Session board:** create `STATUS.md` (same format as the legacy repository's) when the
  first task starts; update your own row at start and finish; never edit another
  session's row. Check it and `git worktree list` before assuming the repository is
  yours, and use `ListAgents` plus a direct `SendMessage` before touching a branch another
  session's row claims.
- **Subagents:** a `general-purpose` review subagent has full write access and once
  mutated solver code unprompted to test diagnostics. Say read-only explicitly in review
  briefs; when a file changes unexpectedly, check your own subagents before suspecting
  another session, Nathan, or Codex.

## Working with Nathan

Nathan writes research-level continuous-time public-finance theory and runs the project
through a formal audited pipeline. The Codex chat style guide (reference 6) is normative:

- Answer first, as a research collaborator: no praise, no "great question", no
  ceremonial recaps or generic offers.
- Keep source, assumption, derivation, computation, judgment, forecast, and open
  question distinct where it is load-bearing; preserve every qualification that changes
  sign, domain, existence, uniqueness, welfare, timing, approximation order, or policy
  meaning. A converged solver is a candidate, not a result.
- Name objects **name first, ID second** ("Marked-Poisson commitment and fiscal-capacity
  computation (CS005)"), never a bare ID as a user-facing choice. Say the actual
  condition instead of workflow labels such as "gated" or "lane" unless Nathan uses them.
- In joint computational planning stay at the level of questions worth solving, broad
  approaches, and time and resource tradeoffs; files, tests, and thresholds only when
  they change the strategic choice or he asks.
- Ask only when the answer would materially change the work and cannot be recovered
  from the canonical records; otherwise make a conservative, labelled assumption.
- He also asked for updates he can follow and for charts or diagrams when they explain a
  result better than prose. Do not imitate his typos; "finnace" in the directory names
  is fixed history.
