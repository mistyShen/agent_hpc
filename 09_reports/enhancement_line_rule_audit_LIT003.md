# Enhancement Line Rule Audit

- Generated at: `2026-04-16T13:13:48.764793+00:00`
- Scope: Enhancement-line rule audit only. Results are limited to BRD4_BD1_LIT003_V3EXP and must not be promoted to frozen benchmark/manuscript claims.
- Current label: `current`
- Current best background: `BG_BENZAMIDE`
- Current active-best-background gap: `6.159`
- Current shortlist ids: `I-BET762`
- Reproduces existing comparison gap: `True`

## Current Tuning

- Known active rank: `1`
- Filter keep count: `1`
- Shortlist count: `1`
- Best background flags: `single_ring_background`

## Ablation Table

| Variant | Overrides | Gap | Gap loss vs current | Best background | Flags | Keep count | Shortlist count | Shortlist ids | Contribution |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ablate_all_background_penalties` | `{"polyaryl_hydrophobe_penalty": 0.0, "simple_aromatic_penalty": 0.0, "single_ring_background_penalty": 0.0}` | `4.059` | `2.1` | `BG_BENZAMIDE` | `single_ring_background` | `1` | `1` | `I-BET762` | `dominant_on_current_panel` |
| `ablate_single_ring_background_penalty` | `{"single_ring_background_penalty": 0.0}` | `4.059` | `2.1` | `BG_BENZAMIDE` | `single_ring_background` | `1` | `1` | `I-BET762` | `dominant_on_current_panel` |
| `ablate_simple_aromatic_penalty` | `{"simple_aromatic_penalty": 0.0}` | `5.246` | `0.913` | `BG_BIPHENYL` | `simple_aromatic_background, polyaryl_hydrophobe_background` | `1` | `1` | `I-BET762` | `material_on_current_panel` |
| `ablate_polyaryl_hydrophobe_penalty` | `{"polyaryl_hydrophobe_penalty": 0.0}` | `5.846` | `0.313` | `BG_BIPHENYL` | `simple_aromatic_background, polyaryl_hydrophobe_background` | `1` | `1` | `I-BET762` | `modest_on_current_panel` |

## Audit Reading

- Treat larger `gap loss vs current` as stronger evidence that the ablated rule is materially contributing on the current focused panel.
- Treat stable `shortlist_count = 1` under ablation as evidence that the shortlisted active remains robust even when a rule is removed.
- Do not generalize these findings beyond this single enhancement panel without cross-case validation.
