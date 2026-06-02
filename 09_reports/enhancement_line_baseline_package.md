# Enhancement Line Baseline Package

- Generated at: `2026-04-28T11:49:43.329855+00:00`
- Scope: enhancement-line only. This package is a formal baseline snapshot for ongoing enhancement validation and tool evolution.
- Boundary: this package must not modify or replace frozen manuscript / benchmark claims.

## Fixed Reading

- Package status: `formal_enhancement_line_baseline`
- Frozen line untouched: `True`
- Gating status: `implemented_and_bounded`
- Current validation status: `bounded_multi_surface_readout_with_boundary_challenge`
- Current bounded headline: `bounded_material_gain_supported_in_BRD4_and_BRD3_IBET762_focused_surfaces`

## Current Case Classes

- Material-on-panel cases: `BRD3_BD1_LIT002_V3EXP, BRD3_BD2_LIT002_V3EXP, BRD4_BD1_LIT002_V3EXP, BRD4_BD1_LIT003_V3EXP`
- Weak-on-panel cases: `BRD2_BD2_LIT001_V3EXP, BRD3_BD1_LIT001_V3EXP, BRD3_BD2_LIT001_V3EXP, BRD4_BD1_LIT001_V3EXP, BRDT_BD1_LIT001_V3EXP, PXR_LBD_LIT001_V3EXP`
- Failed shortlist-preservation cases: `BRD2_BD1_LIT002_V3EXP`
- Non-BRD4 bounded surfaces: `BRD2_BD1_LIT002_V3EXP, BRD2_BD2_LIT001_V3EXP, BRD3_BD1_LIT001_V3EXP, BRD3_BD1_LIT002_V3EXP, BRD3_BD2_LIT001_V3EXP, BRD3_BD2_LIT002_V3EXP, BRDT_BD1_LIT001_V3EXP, PXR_LBD_LIT001_V3EXP`

## Surface Table

| Case | Target | Known active | Gap | Rollout preserved | Effect class | Dominant driver |
| --- | --- | --- | --- | --- | --- | --- |
| `BRD2_BD1_LIT002_V3EXP` | `BRD2_BD1_2YEK` | `I-BET762` | `4.359` | `False` | `failed_shortlist_preservation` | `ablate_single_ring_background_penalty` |
| `BRD2_BD2_LIT001_V3EXP` | `BRD2_BD2_3ONI` | `JQ1` | `2.459` | `True` | `weak_on_panel` | `none` |
| `BRD3_BD1_LIT001_V3EXP` | `BRD3_BD1_3S91` | `JQ1` | `1.759` | `True` | `weak_on_panel` | `none` |
| `BRD3_BD1_LIT002_V3EXP` | `BRD3_BD1_24OS` | `I-BET762` | `6.559` | `True` | `material_on_panel` | `ablate_single_ring_background_penalty` |
| `BRD3_BD2_LIT001_V3EXP` | `BRD3_BD2_3S92` | `JQ1` | `2.259` | `True` | `weak_on_panel` | `none` |
| `BRD3_BD2_LIT002_V3EXP` | `BRD3_BD2_3S92` | `I-BET762` | `7.459` | `True` | `material_on_panel` | `promotion_review_material_signal` |
| `BRD4_BD1_LIT001_V3EXP` | `BRD4_BD1_4QZS` | `JQ1` | `1.859` | `True` | `weak_on_panel` | `none` |
| `BRD4_BD1_LIT002_V3EXP` | `BRD4_BD1_4C66` | `I-BET762` | `6.146` | `True` | `material_on_panel` | `ablate_single_ring_background_penalty` |
| `BRD4_BD1_LIT003_V3EXP` | `BRD4_BD1_4QZS` | `I-BET762` | `6.159` | `True` | `material_on_panel` | `ablate_single_ring_background_penalty` |
| `BRDT_BD1_LIT001_V3EXP` | `BRDT_BD1_4FLP` | `JQ1` | `2.959` | `True` | `weak_on_panel` | `none` |
| `PXR_LBD_LIT001_V3EXP` | `PXR_LBD_8F5Y` | `JQ1` | `3.159` | `True` | `weak_on_panel` | `none` |

## Current Interpretation

- Current v3 behavior remains bounded and panel-aware rather than generally validated across targets.
- Material-on-panel behavior is currently limited to `BRD3_BD1_LIT002_V3EXP, BRD3_BD2_LIT002_V3EXP, BRD4_BD1_LIT002_V3EXP, BRD4_BD1_LIT003_V3EXP`.
- BRD3 I-BET762-focused surfaces now support the interim boundary `bounded material gain supported in BRD4 and BRD3 I-BET762-focused surfaces`.
- Boundary-challenge surfaces `BRD2_BD1_LIT002_V3EXP` currently improve rerank separation without preserving shortlist/rank, so they are excluded from rollout-safe material evidence.
- Current non-BRD4 evidence is mixed: BRD3 I-BET762-focused surfaces are material, while other checked non-BRD4 surfaces remain weak or challenge cases.
- The interim BRD4+BRD3 boundary is not a full BET-family or cross-target claim.

## Allowed Uses

- Use as the current enhancement-line handoff and audit baseline.
- Use as the reference point for future bounded validation surfaces.
- Use to justify pausing same-panel tuning while preserving current enhancement evidence.

## Disallowed Uses

- Do not move these results into frozen manuscript or benchmark claims.
- Do not describe the current enhancement result as cross-target generalization.
- Do not use this package as evidence that v3 is a generally validated reranking improvement.
- Do not count failed shortlist-preservation surfaces as rollout-safe material evidence.

## Included Components

- `gating_implementation_summary` -> `09_reports/enhancement_case_aware_gating_implementation_summary.md`
- `non_brd4_bounded_validation_summary` -> `09_reports/enhancement_non_brd4_bounded_validation_summary.md`
- `multi_case_validation_summary` -> `09_reports/enhancement_multi_case_validation_summary.md`
- `expansion_readiness` -> `09_reports/enhancement_expansion_readiness.md`
- `boundary_promotion_review_brd3` -> `09_reports/enhancement_boundary_promotion_review_BRD3.md`
- `pxr_bounded_surface_comparison` -> `09_reports/enhancement_line_v2_vs_v3_comparison_PXR_LBD_LIT001.md`
- `pxr_bounded_surface_rule_audit` -> `09_reports/enhancement_line_rule_audit_PXR_LBD_LIT001.md`

## Next Recommended Action

- `formalize_interim_brd4_brd3_boundary_then_validate_non_brd3_surface`
