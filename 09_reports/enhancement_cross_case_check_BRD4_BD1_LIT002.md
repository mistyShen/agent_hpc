# Enhancement Line Cross-Case Compatibility Check

- Generated at: `2026-04-16T10:04:59.357231+00:00`
- Scope: Enhancement-line cross-case compatibility check only. This does not modify or replace frozen benchmark/manuscript claims.
- Remote root: `/shared/shen/cpu_ai_drug_design`
- Case id: `BRD4_BD1_LIT002`

## Current Enhancement Tuning

- `{"aromatic_fraction_threshold": 0.75, "aromatic_fraction_weight": 2.35, "atom_delta_weight": 0.015, "hetero_floor": 2.0, "hetero_weight": 0.55, "missing_ligand_penalty": 0.35, "missing_pose_penalty": 0.65, "polyaryl_hydrophobe_penalty": 0.7, "simple_aromatic_penalty": 1.3, "single_ring_background_penalty": 2.1, "small_mw_floor": 180.0, "small_mw_weight": 0.01, "torsdof_threshold": 12.0, "torsdof_weight": 0.025}`

## Reference vs Simulated v3

| Dimension | Reference frozen/root line | Simulated current v3 tuning |
| --- | --- | --- |
| Known active rank | `1` | `1` |
| Known active shortlisted | `True` | `True` |
| Filter keep count | `2` | `2` |
| Shortlist count | `2` | `1` |
| Shortlist ids | `I-BET762, BG_BIPHENYL` | `I-BET762` |
| Best background | `BG_BIPHENYL` | `BG_BENZAMIDE` |
| Active-best-background gap | `0.81` | `5.959` |

## Compatibility Gates

- Known active rank preserved: `True`
- Known active shortlisted preserved: `True`
- Shortlist count not expanded: `True`
- Overall pass: `True`

## Delta vs Reference

- Active-best-background gap delta: `5.149`
- Filter keep count delta: `0`
- Shortlist count delta: `-1`

## Simulated v3 Top Preview

- `I-BET762` rank `1` score `-8.8` flags `none`
- `BG_BENZAMIDE` rank `2` score `-2.841` flags `single_ring_background`
- `BG_BIPHENYL` rank `3` score `-2.754` flags `simple_aromatic_background, polyaryl_hydrophobe_background`
