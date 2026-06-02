# Enhancement Line Rule Audit

- Generated at: `2026-04-17T03:22:22.689100+00:00`
- Scope: Enhancement-line rule audit only. Results are limited to BRD2_BD1_LIT002_V3EXP and must not be promoted to frozen benchmark/manuscript claims.
- Current label: `current`
- Current best background: `BG_BENZAMIDE`
- Current active-best-background gap: `4.359`
- Current shortlist ids: ``
- Reproduces existing comparison gap: `True`

## Current Tuning

- Known active rank: `1`
- Filter keep count: `0`
- Shortlist count: `0`
- Best background flags: `single_ring_background`

## Ablation Table

| Variant | Overrides | Gap | Gap loss vs current | Best background | Flags | Keep count | Shortlist count | Shortlist ids | Contribution |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ablate_all_background_penalties` | `{"polyaryl_hydrophobe_penalty": 0.0, "simple_aromatic_penalty": 0.0, "single_ring_background_penalty": 0.0}` | `2.259` | `2.1` | `BG_BENZAMIDE` | `single_ring_background` | `0` | `0` | `` | `dominant_on_current_panel` |
| `ablate_single_ring_background_penalty` | `{"single_ring_background_penalty": 0.0}` | `2.259` | `2.1` | `BG_BENZAMIDE` | `single_ring_background` | `0` | `0` | `` | `dominant_on_current_panel` |
| `ablate_simple_aromatic_penalty` | `{"simple_aromatic_penalty": 0.0}` | `3.816` | `0.543` | `BG_QUINOLINE` | `simple_aromatic_background, polyaryl_hydrophobe_background` | `0` | `0` | `` | `material_on_current_panel` |
| `ablate_polyaryl_hydrophobe_penalty` | `{"polyaryl_hydrophobe_penalty": 0.0}` | `4.359` | `0.0` | `BG_BENZAMIDE` | `single_ring_background` | `0` | `0` | `` | `weak_on_current_panel` |

## Audit Reading

- Treat larger `gap loss vs current` as stronger evidence that the ablated rule is materially contributing on the current focused panel.
- Treat stable `shortlist_count = 1` under ablation as evidence that the shortlisted active remains robust even when a rule is removed.
- Do not generalize these findings beyond this single enhancement panel without cross-case validation.
