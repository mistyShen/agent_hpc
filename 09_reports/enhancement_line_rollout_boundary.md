# Enhancement Line Rollout Boundary

- Generated at: `2026-04-28T11:49:43.329855+00:00`
- Scope: rollout-policy summary for the enhancement line only.
- Boundary: this document does not alter frozen manuscript / benchmark claims or default frozen workflow policy.

## Current Rollout Decision

- Rollout status: `enhancement_line_interim_brd4_brd3_boundary_with_challenges_logged`
- Current decision: `promote_to_interim_brd4_brd3_boundary__block_full_bet_family_claim`
- Headline: `bounded_material_gain_supported_in_BRD4_and_BRD3_IBET762_focused_surfaces`

## Allowed Rollout Levels

- Use the current v3 + case-aware gating only inside the enhancement line and isolated enhancement roots.
- Use the current package as the audit/handoff baseline for future bounded validation surfaces.
- Use the interim BRD4+BRD3 I-BET762-focused material evidence as a bounded enhancement-line boundary, not as a full BET-family claim.

## Blocked Rollout Levels

- Do not promote current v3 behavior into frozen manuscript claims or frozen benchmark headline results.
- Do not switch the frozen default reranking backend from v2 to v3 on the basis of the current enhancement evidence.
- Do not describe the current enhancement package as a cross-target general improvement.
- Do not describe the interim BRD4+BRD3 evidence as full BET-family validation.

## Current Evidence Boundary

- Material-on-panel cases: `BRD3_BD1_LIT002_V3EXP, BRD3_BD2_LIT002_V3EXP, BRD4_BD1_LIT002_V3EXP, BRD4_BD1_LIT003_V3EXP`
- Weak-on-panel cases: `BRD2_BD2_LIT001_V3EXP, BRD3_BD1_LIT001_V3EXP, BRD3_BD2_LIT001_V3EXP, BRD4_BD1_LIT001_V3EXP, BRDT_BD1_LIT001_V3EXP, PXR_LBD_LIT001_V3EXP`
- Failed shortlist-preservation cases: `BRD2_BD1_LIT002_V3EXP`
- Non-BRD4 checked surfaces: `BRD2_BD1_LIT002_V3EXP, BRD2_BD2_LIT001_V3EXP, BRD3_BD1_LIT001_V3EXP, BRD3_BD1_LIT002_V3EXP, BRD3_BD2_LIT001_V3EXP, BRD3_BD2_LIT002_V3EXP, BRDT_BD1_LIT001_V3EXP, PXR_LBD_LIT001_V3EXP`

## Current Gating Policy

- Gating mode: `case_aware_two_mode_gate`
- Coverage threshold: `0.8`
- Gated penalties: `simple_aromatic_penalty, polyaryl_hydrophobe_penalty, single_ring_background_penalty`
- Ungated v3 terms: `artifact_penalty, lightweight_non_panel_specific_physchem_terms`

## Preconditions For Broader Rollout

- Keep the frozen line untouched while broader rollout remains unapproved.
- Require additional bounded validation that materially strengthens the evidence boundary before any frozen/default promotion is considered.
- Require that any broader rollout proposal still preserves case-level explainability, rollback ability, and bounded wording.
- Treat the current threshold and gating policy as enhancement-line empirical policy until separately validated.
- Resolve any shortlist/rank preservation failures before using a new surface to expand the rollout boundary.

## Stop Conditions

- Stop any broader rollout attempt if a new bounded validation surface loses known-active shortlist/rank preservation.
- Stop any broader rollout attempt if non-BRD4 surfaces begin showing uncontrolled penalty-driven behavior inconsistent with weak_on_panel audits.
- Stop any broader rollout attempt if the boundary can no longer be stated more narrowly than a cross-target claim.
- Stop any broader rollout attempt if a failed shortlist-preservation surface is being counted as material rollout evidence.

## References

- `baseline_package` -> `09_reports/enhancement_line_baseline_package.md`
- `gating_implementation_summary` -> `09_reports/enhancement_case_aware_gating_implementation_summary.md`
- `multi_case_validation_summary` -> `09_reports/enhancement_multi_case_validation_summary.md`
- `non_brd4_validation_summary` -> `09_reports/enhancement_non_brd4_bounded_validation_summary.md`
- `expansion_readiness` -> `09_reports/enhancement_expansion_readiness.md`
- `boundary_promotion_review_brd3` -> `09_reports/enhancement_boundary_promotion_review_BRD3.md`
