# Enhancement Non-BRD4 Bounded Validation Summary

- Generated at: `2026-04-28T11:49:43.054123+00:00`
- Scope: Enhancement-line only. This summary must not be promoted into frozen benchmark/manuscript claims.
- Boundary: This is a bounded synthesis of the currently checked non-BRD4, literature-backed validation surfaces.

## Surface Table

| Enhancement case | Target | Known active | Baseline gap | Enhancement gap | Gap gain | Rollout preserved | Effect class | Dominant driver |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `BRD2_BD1_LIT002_V3EXP` | `BRD2_BD1_2YEK` | `I-BET762` | `-1.45` | `4.359` | `5.809` | `False` | `failed_shortlist_preservation` | `ablate_all_background_penalties` |
| `BRD2_BD2_LIT001_V3EXP` | `BRD2_BD2_3ONI` | `JQ1` | `0.785` | `2.459` | `1.674` | `True` | `weak_on_panel` | `none` |
| `BRD3_BD1_LIT001_V3EXP` | `BRD3_BD1_3S91` | `JQ1` | `0.12` | `1.759` | `1.639` | `True` | `weak_on_panel` | `none` |
| `BRD3_BD1_LIT002_V3EXP` | `BRD3_BD1_24OS` | `I-BET762` | `1.0` | `6.559` | `5.559` | `True` | `material_on_panel` | `ablate_all_background_penalties` |
| `BRD3_BD2_LIT001_V3EXP` | `BRD3_BD2_3S92` | `JQ1` | `0.215` | `2.259` | `2.044` | `True` | `weak_on_panel` | `none` |
| `BRD3_BD2_LIT002_V3EXP` | `BRD3_BD2_3S92` | `I-BET762` | `2.52` | `7.459` | `4.939` | `True` | `material_on_panel` | `promotion_review_material_signal` |
| `BRDT_BD1_LIT001_V3EXP` | `BRDT_BD1_4FLP` | `JQ1` | `0.88` | `2.959` | `2.079` | `True` | `weak_on_panel` | `none` |
| `PXR_LBD_LIT001_V3EXP` | `PXR_LBD_8F5Y` | `JQ1` | `1.165` | `3.159` | `1.994` | `True` | `weak_on_panel` | `none` |

## Synthesis

- Current non-BRD4 bounded surfaces split across weak/material/failure behavior: weak on `BRD2_BD2_LIT001_V3EXP, BRD3_BD1_LIT001_V3EXP, BRD3_BD2_LIT001_V3EXP, BRDT_BD1_LIT001_V3EXP, PXR_LBD_LIT001_V3EXP`, material on `BRD3_BD1_LIT002_V3EXP, BRD3_BD2_LIT002_V3EXP`, failed shortlist preservation on `BRD2_BD1_LIT002_V3EXP`.
- Even where panel-specific penalties stay weak_on_panel, v3 still shows modest positive gap improvement on `BRD2_BD1_LIT002_V3EXP, BRD2_BD2_LIT001_V3EXP, BRD3_BD1_LIT001_V3EXP, BRD3_BD1_LIT002_V3EXP, BRD3_BD2_LIT001_V3EXP, BRD3_BD2_LIT002_V3EXP, BRDT_BD1_LIT001_V3EXP, PXR_LBD_LIT001_V3EXP` through ungated lightweight terms.
- The checked non-BRD4 surfaces support an interim BRD3-specific material reading while still falling short of a full cross-target or BET-family policy.

## Boundary Notes

- These non-BRD4 surfaces remain bounded enhancement-line evidence only and must not be read as cross-target generalization.
- Weak or failed behavior outside the approved BRD3 I-BET762-focused set remains evidence that panel-specific penalties have not become an uncontrolled cross-target policy.
- Any non-BRD4 surface that fails known-active shortlist/rank preservation must be excluded from rollout-safe material evidence, even if its rerank gap increases.
- Frozen filtering logic, benchmark schema, truth-table structure, and manuscript claims remain unchanged.
