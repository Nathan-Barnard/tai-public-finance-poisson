# Canonical references: fingerprints

Exact Codex-workspace files this repository depends on, with the SHA-256, mtime, and
(for Overleaf mirrors) the mirror commit observed when this workspace was set up. Paths
are relative to `/Users/nathanbarnard/Documents/TAI public finnace codex`. The Codex
workspace is canonical and read-only; this table is a staleness detector, not a copy.

**Observed:** 2026-09-01, 23:00–23:10 BST, while Codex was actively editing. A changed
hash means the record moved on and must be re-read before it is relied on. Re-hash with:

```bash
cd "/Users/nathanbarnard/Documents/TAI public finnace codex" && shasum -a 256 <path>
```

## Workstream charter and notebooks

| File | SHA-256 | mtime |
|---|---|---|
| `poisson-model/README.md` | `2aec71bdb36d558e45487404e3604f5f902947e991a26780ae776848a5b1aa97` | 23:03:41 |
| `poisson-model/AGENTS.md` | `7a574b750d2f99d76ef0cb0b908838e5fd8d96f5eaf556857cd6f420a3efde9c` | 23:03:41 |
| `research-notes/poisson-model-complete-and-incomplete-markets.md` | `468bb3ae4743b4c1bd4d89d9dfffa7795ead0149e0ad0ce0f21fc47283d33107` | 23:03:41 |
| `research-notes/single-poisson-shock-and-complete-markets-genealogy.md` | `81c73866fb0d4863738c338bf9d45c1e8855505bd47a8b76770b21836b92b8ee` | 15:38:28 |

## Specification and computation system

| File | SHA-256 | mtime |
|---|---|---|
| `computation/specifications/marked-poisson-commitment-and-fiscal-capacity--CS005.md` (v0.1, `draft`, unfingerprinted, 6 unresolved) | `e6872b0481d0f61da49ae0e88dc796bcf288c9c3c20dde56e0feb15e81b58f4c` | 14:48:10 |
| `computation/computation_registry.yaml` (CP005 `proposed`, CA008 `candidate`, CB005, CS005; repository binding to the legacy Claude repo) | `f57afba0c4d984b1a94604008a42409062d5f855b17c28917d3d8da7db9607d6` | 22:23:01 |
| `computation/README.md` | `d1feb50a22e5bf48784d31695704cb9a497cf7ee61bbd7dcdb1c6775ec1cb2fb` | 22:31:47 |
| `computation/AGENTS.md` | `5a6a2c6b97b0d8acfa65349eecab03ef97014d939eb83b849ca25499fd5fa360` | 20:22:37 |
| `computation/roadmap.md` (section "Separate branch — marked-Poisson commitment") | `72c1a032a9e4cf246659c9973e0cfc1473dddeca7b431567f083296ae71a21d9` | 22:31:47 |
| `computation/decisions/smaller-sequential-implementation-blocks-with-early-progress-updates--CD002.md` | `8d86fadf1bd4530dd1fe763fadcc355e2b9fe4c0f22615098ea56e404613297a` | 20:23:50 |
| `computation/templates/run_record.yaml` | `3952c66bc79ae109ae958dd29a6f72f8e5de29fa71db2d3dfd336fda24ad15b3` | 13:13:02 |

## Economics reviews (both `sound_with_qualification`)

| File | SHA-256 | mtime |
|---|---|---|
| `economics-verification/reviews/poisson-branch-genealogy-tax-timing-portfolios-and-safe-debt--EV07.md` | `7fccf012970469cf44373c6f09c7d395a874e554322ebccb0c7dd7ac59c16877` | 16:11:04 |
| `economics-verification/reviews/ramsey-counterfactual-design-inherited-state-rents-and-interpretation--EV09.md` | `786d946e037e5b39021b2cb04aaee3682ef22d7906ac8284892deaa0305416ab` | 19:54:08 |

## Maintained claims, project map, naming, chat style

| File | SHA-256 | mtime |
|---|---|---|
| `model-tracker/model_setup_results_tracker.md` (`A14`–`A21`, `R26`–`R37`, `Q09`, `Q11`–`Q15`, `Q17`–`Q18`) | `1eb6309f85c670435401bcfe4326e88b99223ea5c0e3949d9e01ec65b32b7eee` | 19:52:58 |
| `model-tracker/model_setup_results_ledger.yaml` | `e03f305578d22fea6e205e5b3e7fb5a4343fd52c11c13df0ebf37ad548d99bf1` | 19:52:58 |
| `CURRENT_PROJECT_CONTEXT.md` (section "Poisson branch: audited hierarchy and result scope") | `01a06ef0f4634e915b47e800494a5ffe46db65cf00f937f81857d1c345d43ab1` | 23:06:20 |
| `PROJECT_NAMING.md` | `c354baeba77438c69f57286ce6ae4a008188b26163fed40e16c7c383ee16baab` | 14:40:09 |
| `overleaf/README.md` | `dd09c3550f070113a7cabf1e6e9f876e7e06a6de56bf190518e79387d23a14c4` | 15:45:48 |
| `voice_specs/chat_style.md` (v0.4) | `9933ad3a502ac6c61f387bc2686119dac2d1304eacaa12514179313e934bea0b` | 18:06:41 |

## Manuscripts (read-only Overleaf mirrors)

| Role | File | SHA-256 | Mirror commit |
|---|---|---|---|
| Primary derivation: *Commitment Ramsey Policy in a Marked-Poisson Small Open Economy* (June 2026) | `overleaf/commitment-ramsey-marked-poisson-small-open-economy/main.tex` | `699ba07a0dffa15f599c559e5a899264756b3dcde0dec59010ba451ca83affc9` | `c1bce87e1df76396a0d280467ac10c1f2107e683` |
| Fixed-mark, later same-day draft (22 June, 17:23 UTC): regular post-arrival zero-tax tail only, promise state retained | `overleaf/commitment-ramsey-automation-risk-complete-markets-balanced-growth/main.tex` | `95bb2a05998942dfaf076ef6724affce9015bbaafe473a99e5c79bf4b89245a8` | `c3dcf68447afb9a301f73bbc7c7b2f3d2723109a` |
| Fixed-mark, earlier same-day draft (16:30 UTC): sharper conditional pre-arrival zero-tax claim | `overleaf/commitment-ramsey-bgp-complete-markets/main.tex` | `586d3b365ea9b23891a530aedcde833dac84024511bc07d240fd1c0603e852af` | `4c0b5f2d47c3b998c8e94c3d789e597ded5cdbc5` |
| Setup conventions for the complete-spanning benchmark | `overleaf/setup-conventions-complete-spanning-ramsey/setup_conventions_complete_markets.tex` | `284a8b192bfa85602c851b58db06f76529cb8ffef455afc3d620d465857314b4` | `a6ffd20317507624831da8203c065dea2a9568bb` |
| Tax-timing companion | `overleaf/non-anticipatory-capital-taxation-at-poisson-shocks/nonanticipatory_capital_taxation_poisson.tex` | `39b0dd4955c4dd0c94fc1357d5c9d31430f1436fd35ad383adc324ab263f104d` | `374cba46b386a599eff4aa1463979c0f34ba6d26` |
| Safe-debt companion | `overleaf/value-safe-government-debt-poisson-automation/safe_debt_mit_note.tex` | `17e9f927bace67f0a6c10bc031a14036165e8c6960f4225da23bf251eb841e1c` | `83aa15446bab497e554a199530678a17ff62522f` |
| Poisson versus absorbed diffusion companion | `overleaf/automation-poisson-arrival-or-absorbed-diffusion/main.tex` | `db63fd1b5df1325b8990a853d2c5de82d4fae5ea0893992f41d09a76e4fbaecd` | `e175e29569e4ae98c46fde1364a72c1707242ff4` |

The `commitment-ramsey-marked-poisson-small-open-economy-original/` mirror is
byte-identical to the primary derivation; cite the primary. `tank-poisson-arrival-
government-debt-v1-12/` is a historical Markov-perfect predecessor whose equations must
not be imported. `poisson-vs-brownian-risk/` and `complete-markets-conditions-v1/` are
empty shells and not evidence for anything.
