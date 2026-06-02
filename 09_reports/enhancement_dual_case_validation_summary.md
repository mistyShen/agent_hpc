# Enhancement Dual-Case Validation Summary

- Generated at: `2026-04-16T10:03:16.172582+00:00`
- Scope: Enhancement-line synthesis only. This does not modify or replace frozen benchmark/manuscript claims.
- Boundary: Conclusions below are limited to the explicitly checked BRD4 enhancement-only cases and bounded frozen-case compatibility checks.

## Current Readout

- Current validation status: `bounded_cross_case_pass`
- Expansion readiness: `can_expand_with_existing_case`
- Recommended next action: `pause_same_panel_tuning_and_prepare_case-aware_or_additional_validation`

## Case Table

| Case | Known active | Shortlist count | Best background | Active-best-background gap | Effect class | Dominant driver |
| --- | --- | --- | --- | --- | --- | --- |
| `BRD4_BD1_LIT002_V3EXP` | `I-BET762` | `1` | `BG_BIPHENYL` | `6.146` | `material_on_panel` | `ablate_single_ring_background_penalty` |
| `BRD4_BD1_LIT001_V3EXP` | `JQ1` | `1` | `BG_ASPIRIN` | `1.859` | `weak_on_panel` | `none` |

## Case Reading

### `BRD4_BD1_LIT002_V3EXP`

- Interpretation: Current v3 penalties materially widen the active-best-background gap on this focused panel.
- Known active rank/shortlist: `1` / `True`
- Best background: `BG_BIPHENYL`
- Best background flags: `simple_aromatic_background, polyaryl_hydrophobe_background`
- Dominant driver: `ablate_single_ring_background_penalty` (gap loss `2.087`)
- Additional material drivers: `ablate_simple_aromatic_penalty` (1.3), `ablate_polyaryl_hydrophobe_penalty` (0.7)
- Top rerank preview: `I-BET762` rank `1` score `-8.9`, `BG_BIPHENYL` rank `2` score `-2.754`, `BG_BENZAMIDE` rank `3` score `-2.741`

### `BRD4_BD1_LIT001_V3EXP`

- Interpretation: Current v3 penalties preserve shortlist/rank on this panel, but the audited penalty family does not materially change the gap.
- Known active rank/shortlist: `1` / `True`
- Best background: `BG_ASPIRIN`
- Best background flags: `none`
- Dominant driver: `none`
- Additional material drivers: `none`
- Top rerank preview: `JQ1` rank `1` score `-7.4`, `BG_ASPIRIN` rank `2` score `-5.541`, `BG_PARACETAMOL` rank `3` score `-5.121`

## Synthesis

- Current v3 behavior is panel-sensitive: it materially widens the active margin on `BRD4_BD1_LIT002_V3EXP`, but behaves mainly as a compatibility-preserving reranker on `BRD4_BD1_LIT001_V3EXP`.
- Both explicitly checked frozen cases (`BRD4_BD1_LIT001` and `BRD4_BD1_LIT002`) still pass bounded cross-case compatibility under the current v3 tuning.
- The current penalty family should therefore be treated as enhancement-line, bounded, and panel-aware rather than as a generally validated improvement.
- Do not use the generic single-case LIT001 comparison headline as the main decision surface; use this dual-case synthesis plus rule audit instead.

## Boundary Notes

- This summary remains bounded to the enhancement line and the explicitly checked BRD4 literature-backed cases.
- The observed benefit on `BRD4_BD1_LIT002_V3EXP` should not be generalized as a cross-target or universal reranking improvement.
- The weak-on-panel result for `BRD4_BD1_LIT001_V3EXP` argues against broad claims and supports either case-aware gating or further validation before rollout.
