# Enhancement Case-Aware Gating Design

- Scope: design only. This document does not change current tuning, frozen benchmark/manuscript claims, or workflow behavior.
- Boundary: conclusions below are limited to the current enhancement line evidence.

## Why Gating Is Needed

Current enhancement-only evidence is asymmetric across the two BRD4 validation surfaces:

| Case | Current effect | Active-best-background gap | Reading |
| --- | --- | --- | --- |
| `BRD4_BD1_LIT002_V3EXP` | `material_on_panel` | `6.146` | current v3 penalties materially widen the margin |
| `BRD4_BD1_LIT001_V3EXP` | `weak_on_panel` | `1.859` | current v3 penalties mainly preserve shortlist/rank, but do not materially change the gap |

Current panel-profile evidence explains the asymmetry:

| Case | Background flag coverage | Best background | Panel reading |
| --- | --- | --- | --- |
| `BRD4_BD1_LIT002_V3EXP` | `1.0` | `BG_BIPHENYL` | best background is directly captured by current aromatic/hydrophobe rules |
| `BRD4_BD1_LIT001_V3EXP` | `0.478` | `BG_ASPIRIN` | best background is not directly captured by current background flags |

This means the current v3 penalty family behaves like a panel-sensitive enhancer, not like a broadly validated universal improvement.

## Design Goal

Keep the current v3 gain on panels like `LIT002_V3EXP`, while avoiding unnecessary panel-specific penalties on panels like `LIT001_V3EXP` where the same rules do not materially help.

## Non-Goals

- Do not change the frozen result line.
- Do not change benchmark schema or truth-table structure.
- Do not promote current enhancement behavior into manuscript claims.
- Do not introduce a target-specific hardcoded whitelist.

## Recommended Minimal Gating Design

Gate only the panel-specific v3 penalties:

- `simple_aromatic_penalty`
- `polyaryl_hydrophobe_penalty`
- `single_ring_background_penalty`

Do **not** gate the core v3 terms:

- `artifact_penalty`
- size / hetero / aromatic-fraction lightweight physchem terms

### Panel Profile Inputs

Compute these at case level from the prepared library rows already consumed by the workflow:

- `background_count`
- `flagged_background_count`
- `background_flag_coverage = flagged_background_count / background_count`
- `simple_aromatic_background_count`
- `polyaryl_hydrophobe_background_count`
- `single_ring_background_count`

This uses only fields already present in `prepared_library.tsv` and current v3 flag logic. No new descriptors or heavy dependencies are needed.

### Minimal Gating Modes

Recommended first version:

1. `panel_specific_v3_full`
   - enable current panel-specific penalties at full weight
   - trigger when:
     - `library_type == focused`
     - `background_flag_coverage >= 0.8`

2. `panel_specific_v3_off`
   - zero out current panel-specific penalties
   - trigger when:
     - `background_flag_coverage < 0.8`

### Why This Is the Best Minimal Cut

- `LIT002_V3EXP` would stay in `panel_specific_v3_full`
  - current coverage is `1.0`
  - current panel materially benefits from the penalty family
- `LIT001_V3EXP` would move to `panel_specific_v3_off`
  - current coverage is `0.478`
  - current audit already shows the penalty family is weak on this panel

This is intentionally simpler than introducing a three-way mode (`full/reduced/off`) on the first pass. It keeps the decision boundary easy to inspect and easy to audit.

## Proposed Runtime Behavior

Within `ai_reranking v3`:

1. Compute the case-level panel profile before row scoring.
2. Select a gating mode from the panel profile.
3. Apply the selected multiplier only to the three panel-specific penalties.

Suggested first-pass multipliers:

- `panel_specific_v3_full`
  - `simple_aromatic_penalty`: `1.0x`
  - `polyaryl_hydrophobe_penalty`: `1.0x`
  - `single_ring_background_penalty`: `1.0x`
- `panel_specific_v3_off`
  - `simple_aromatic_penalty`: `0.0x`
  - `polyaryl_hydrophobe_penalty`: `0.0x`
  - `single_ring_background_penalty`: `0.0x`

## Expected Effect

If this design works as intended:

- `LIT002_V3EXP` should retain most of its current active/background separation.
- `LIT001_V3EXP` should remain compatible, but the panel-specific rules should no longer pretend to be the source of improvement.
- The system will behave more like a tool with explicit applicability conditions, and less like a one-panel-tuned scorer.

## Diagnostics To Add When Implementing

If implemented later, the reranking summary should expose:

- `panel_specific_gating_mode`
- `background_flag_coverage`
- `simple_aromatic_background_count`
- `polyaryl_hydrophobe_background_count`
- `single_ring_background_count`
- applied penalty multipliers

These should be enhancement-line diagnostics only until the behavior is more broadly validated.

## Recommended Validation Sequence

Before adopting this design in code:

1. Keep the current frozen line untouched.
2. Implement gating only on the enhancement line.
3. Re-run:
   - `BRD4_BD1_LIT002_V3EXP`
   - `BRD4_BD1_LIT001_V3EXP`
4. Rebuild:
   - dual-case validation summary
   - panel profile summary
   - rule audit / compatibility reports as needed
5. Accept the gating design only if:
   - `LIT002_V3EXP` keeps a strong margin
   - `LIT001_V3EXP` remains compatible
   - the resulting interpretation becomes cleaner rather than more ad hoc

## Current Recommendation

Proceed with this as the **first implementation candidate** for case-aware gating.

Reason:

- it directly matches the current dual-case evidence
- it uses only existing fields
- it does not require schema changes
- it gives us a clear bounded hypothesis to test next
