# Enhancement Line Cross-Case Compatibility Check

- Generated at: `2026-04-16T10:04:43.657762+00:00`
- Scope: Enhancement-line cross-case compatibility check only. This does not modify or replace frozen benchmark/manuscript claims.
- Remote root: `/shared/shen/cpu_ai_drug_design`
- Case id: `BRD4_BD1_LIT001`

## Current Enhancement Tuning

- `{"aromatic_fraction_threshold": 0.75, "aromatic_fraction_weight": 2.35, "atom_delta_weight": 0.015, "hetero_floor": 2.0, "hetero_weight": 0.55, "missing_ligand_penalty": 0.35, "missing_pose_penalty": 0.65, "polyaryl_hydrophobe_penalty": 0.7, "simple_aromatic_penalty": 1.3, "single_ring_background_penalty": 2.1, "small_mw_floor": 180.0, "small_mw_weight": 0.01, "torsdof_threshold": 12.0, "torsdof_weight": 0.025}`

## Reference vs Simulated v3

| Dimension | Reference frozen/root line | Simulated current v3 tuning |
| --- | --- | --- |
| Known active rank | `1` | `1` |
| Known active shortlisted | `True` | `True` |
| Filter keep count | `1` | `1` |
| Shortlist count | `1` | `1` |
| Shortlist ids | `JQ1` | `JQ1` |
| Best background | `BG_ANILINE` | `BG_BENZOIC_ACID` |
| Active-best-background gap | `3.8` | `7.039` |

## Compatibility Gates

- Known active rank preserved: `True`
- Known active shortlisted preserved: `True`
- Shortlist count not expanded: `True`
- Overall pass: `True`

## Delta vs Reference

- Active-best-background gap delta: `3.239`
- Filter keep count delta: `0`
- Shortlist count delta: `0`

## Simulated v3 Top Preview

- `JQ1` rank `1` score `-7.4` flags `none`
- `BG_BENZOIC_ACID` rank `2` score `-0.361` flags `single_ring_background`
- `BG_PYRIDINE` rank `3` score `0.05` flags `single_ring_background`
