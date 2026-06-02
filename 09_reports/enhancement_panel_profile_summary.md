# Enhancement Panel Profile Summary

- Generated at: `2026-04-16T10:03:16.172582+00:00`
- Scope: Enhancement-line panel-composition summary only. This does not change tuning or frozen benchmark/manuscript claims.
- Input source: workflow-prepared library descriptors plus current v3 tuning.

## Current Tuning

- `hetero_floor = 2.0`
- `aromatic_fraction_threshold = 0.75`
- `simple_aromatic_penalty = 1.3`
- `polyaryl_hydrophobe_penalty = 0.7`
- `single_ring_background_penalty = 2.1`

## Case Table

| Case | Panel size | Background count | Any-flag coverage | Best background | Interpretation |
| --- | --- | --- | --- | --- | --- |
| `BRD4_BD1_LIT001_V3EXP` | `24` | `23` | `0.478` | `BG_ASPIRIN` | `best background is not directly captured by current background flags` |
| `BRD4_BD1_LIT002_V3EXP` | `6` | `5` | `1.0` | `BG_BIPHENYL` | `best background matches simple_aromatic rule; best background matches polyaryl_hydrophobe rule` |

## `BRD4_BD1_LIT001_V3EXP`

- Known active: `JQ1`
- Best background: `BG_ASPIRIN`
- Background flag coverage: `0.478`
- `simple_aromatic_background`: `4` -> `BG_BIPHENYL, BG_NAPHTHALENE, BG_QUINOLINE, BG_INDOLE`
- `polyaryl_hydrophobe_background`: `4` -> `BG_BIPHENYL, BG_NAPHTHALENE, BG_QUINOLINE, BG_INDOLE`
- `single_ring_background`: `7` -> `BG_BENZENE, BG_BENZOIC_ACID, BG_BENZAMIDE, BG_SALICYLIC_ACID, BG_ACETOPHENONE, BG_PYRIDINE, BG_NICOTINAMIDE`
- Best-background interpretation: `best background is not directly captured by current background flags`

## `BRD4_BD1_LIT002_V3EXP`

- Known active: `I-BET762`
- Best background: `BG_BIPHENYL`
- Background flag coverage: `1.0`
- `simple_aromatic_background`: `4` -> `BG_BIPHENYL, BG_NAPHTHALENE, BG_QUINOLINE, BG_INDOLE`
- `polyaryl_hydrophobe_background`: `4` -> `BG_BIPHENYL, BG_NAPHTHALENE, BG_QUINOLINE, BG_INDOLE`
- `single_ring_background`: `1` -> `BG_BENZAMIDE`
- Best-background interpretation: `best background matches simple_aromatic rule ; best background matches polyaryl_hydrophobe rule`

## Reading

- Panel composition is asymmetric across the two enhancement-only BRD4 cases: `BRD4_BD1_LIT002_V3EXP` contains multiple backgrounds that directly match the current v3 aromatic/hydrophobe heuristics, while `BRD4_BD1_LIT001_V3EXP` has much broader and softer background chemistry.
- This explains why the same penalty family is material on `LIT002_V3EXP` but weak on `LIT001_V3EXP` without requiring a change to frozen-line logic.
- Use this panel-profile summary together with the dual-case validation summary before proposing case-aware gating or broader rollout.
