# Enhancement Case-Aware Gating Implementation Summary

- Scope: enhancement line only. This summary documents the current `ai_reranking v3` gating behavior and its bounded validation status.
- Boundary: this does not modify frozen manuscript / benchmark claims and should not be read as a general cross-target improvement claim.

## What Was Implemented

Case-aware gating is now implemented inside `ai_reranking v3`.

The current minimal gating logic:

- compute a case-level focused-panel profile from prepared library rows
- measure `background_flag_coverage = flagged_background_count / background_count`
- apply a simple two-mode gate:
  - `panel_specific_v3_full`
  - `panel_specific_v3_off`

Current trigger rule:

- `panel_specific_v3_full`
  - when `library_type == focused`
  - and `background_flag_coverage >= 0.8`
- `panel_specific_v3_off`
  - otherwise

Only the panel-specific penalties are gated:

- `simple_aromatic_penalty`
- `polyaryl_hydrophobe_penalty`
- `single_ring_background_penalty`

The following `v3` terms remain ungated:

- artifact penalty
- lightweight non-panel-specific physchem terms

## Current Effective Reading

| Case | Background flag coverage | Expected gating mode | Current effect |
| --- | --- | --- | --- |
| `BRD4_BD1_LIT002_V3EXP` | `1.0` | `panel_specific_v3_full` | `material_on_panel` |
| `BRD4_BD1_LIT001_V3EXP` | `0.478` | `panel_specific_v3_off` | `weak_on_panel` |

## Operational Definitions

- `material_on_panel`
  - known active remains rank `1`
  - known active remains shortlisted
  - bounded audit shows the panel-specific penalty family materially contributes to the active-best-background gap on the current panel
- `weak_on_panel`
  - known active remains rank `1`
  - known active remains shortlisted
  - bounded audit shows the panel-specific penalty family does not materially change the active-best-background gap on the current panel

## Threshold Note

- the current `background_flag_coverage >= 0.8` trigger should be read as an empirical enhancement-line threshold
- it is not a frozen benchmark policy
- it is not yet a generally validated cross-panel or cross-target threshold

## Current Validation Readout

### `BRD4_BD1_LIT002_V3EXP`

- known active: `I-BET762`
- shortlist count: `1`
- shortlist contains only `I-BET762`
- best background: `BG_BIPHENYL`
- active-best-background gap: `6.146`
- interpretation: current gated `v3` remains materially useful on this focused panel

### `BRD4_BD1_LIT001_V3EXP`

- known active: `JQ1`
- shortlist count: `1`
- shortlist contains only `JQ1`
- best background: `BG_ASPIRIN`
- active-best-background gap: `1.859`
- interpretation: current gated `v3` remains compatibility-preserving here, but not materially gap-widening

## Why The Current Result Is Coherent

- `LIT002_V3EXP` exposes the background chemistry targeted by the current penalty family, so keeping the panel-specific penalties active is consistent with the panel profile.
- `LIT001_V3EXP` does not strongly expose those background types, so turning the panel-specific penalties effectively off is consistent with the weak-on-panel audit result.
- This makes the current `v3` behavior easier to explain: it is a bounded, panel-sensitive enhancement rather than a universal reranking improvement.

## What Gating Does Not Change

- current gating only affects the panel-specific penalty terms inside `ai_reranking v3`
- it does not change the frozen filtering logic
- it does not change benchmark schema or truth-table structure
- it does not change overall frozen benchmark policy

## Practical Boundary

Use this implementation summary together with:

- dual-case validation summary
- panel profile summary
- bounded rule audit
- bounded frozen-case compatibility checks

Do not use the generic single-case `LIT001` comparison headline as the primary decision surface.

## Current Recommendation

- keep the frozen line untouched
- keep current `v3` conclusions bounded to the enhancement line
- do not resume same-panel tuning immediately
- if we continue, prefer either:
  - a third enhancement-only validation surface
  - or a broader bounded validation pass before any stronger claim
