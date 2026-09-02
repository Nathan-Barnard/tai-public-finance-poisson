# RUN-20260902T220418Z-CS005-5a264b83-01

- Outcome: **computational_pass** (prototype / reduced-coverage pass; decision_grade: false, coverage: reduced, pm08_cs005_tolerance_pass: true, strict_viability_checked: true)
- Profile: `P-CS005-REAL-01` (spec CS005 v0.7, status draft -- exploratory first attempt)
- Post-mark blocks: L and H both `pass`
- PM08 tail certificate (L): **pass** (method `backward_time_integration_from_local_linear_tail`, tolerance 1.0e-08, manifold-match residual 1.258e-12, saddle-path exclusion bound 3.103e-12)
- PM08 tail certificate (H): **pass** (method `backward_time_integration_from_local_linear_tail`, tolerance 1.0e-08, manifold-match residual 6.127e-13, saddle-path exclusion bound 4.422e-13)
- Candidates found: 4 (discarded non-convergent brackets: 5)
- Fully admissible candidates (implemented checks AND certified W5 strict viability): 0
- Admissible under pre-W5 implemented checks only (`admissible_ex_w5`): 1
- W5 strict-viability labels (method `constant_tax_rescaled_stable_manifold_witness_lower_bound_with_tau1_compact_domain_outer_bound`): 1 certified_viable / 2 frontier_unresolved / 1 certified_infeasible_on_declared_domain
- `frontier_unresolved` means the certified-inner capacity lower bound (constant-tax witness) could not certify viability AND the tau=1 compact-domain outer bound could not certify infeasibility -- a certification gap of this conservative method, **not** an infeasibility finding.
- Date-zero (inherited-state-matching) candidates: 0

Interpretation: every candidate is a conditional rest point/atlas entry unless explicitly marked otherwise; a numerical root is not evidence of existence, uniqueness, global optimality, or equilibrium. See report.json's `limitations` for what this run does and does not establish.
