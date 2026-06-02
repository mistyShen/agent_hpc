# Enhancement Line V2 vs V3 Comparison

This report is an enhancement-line comparison only. It does not modify or replace the frozen manuscript / benchmark result line.

Source context:

- frozen baseline case: `BRD4_BD1_LIT003`
- enhancement experiment case: `BRD4_BD1_LIT003_V3EXP`
- isolated execution root: `/shared/shen/cpu_ai_drug_design_v3exp`

## Scope

The comparison focuses on three questions:

1. does `ai_reranking v3` change rerank ordering relative to `v2`
2. does `clustering_and_prioritization v2` convert that extra score separation into a tighter shortlist
3. does the enhancement remain lightweight enough for CPU-only iterative work

## Headline Result

`ai_reranking v3` plus `clustering_and_prioritization v2` improved shortlist selectivity on the BRD4 BD1 focused hard panel without changing the frozen baseline line.

- baseline `BRD4_BD1_LIT003`
  - `filter_keep_count = 1`
  - `shortlist_count = 1`
  - shortlist: `I-BET762`
- enhancement `BRD4_BD1_LIT003_V3EXP`
  - `filter_keep_count = 1`
  - `shortlist_count = 1`
  - shortlist: `I-BET762`

This means the new prioritization layer is now consuming the extra separation introduced by `v3`, rather than leaving the shortlist unchanged.

## Comparison Table

| Dimension | `BRD4_BD1_LIT003` | `BRD4_BD1_LIT003_V3EXP` |
| --- | --- | --- |
| Rerank model | `cpu_docking_rerank_v2` | `cpu_docking_rerank_v3` |
| Top 1 | `I-BET762` | `I-BET762` |
| Top 1 rerank score | `-7.585` | `-8.7` |
| Top 2 | `BG_BIPHENYL` | `BG_BENZAMIDE` |
| Top 2 rerank score | `-6.205` | `-2.541` |
| Top 3 | `BG_BENZAMIDE` | `BG_BIPHENYL` |
| Top 3 rerank score | `-6.185` | `-2.154` |
| Filter keep count | `1` | `1` |
| Shortlist count | `1` | `1` |
| Shortlist ids | `I-BET762` | `I-BET762` |
| Known active id | `I-BET762` | `I-BET762` |
| Best background id | `BG_BIPHENYL` | `BG_BENZAMIDE` |
| Active-best-background gap | `1.38` | `6.159` |
| Known active in shortlist | `true` | experimental line, no separate truth row |
| Best known active rank | `1` | experimental line, no separate truth row |

## Reranking Interpretation

The enhancement line changed reranking in two useful ways:

1. it preserved `I-BET762` as the top-ranked compound
2. it widened the separation between the active and hard aromatic backgrounds through explicit `physchem_penalty`

Top `v3` diagnostics:

- `I-BET762`
  - `docking_core = -8.7`
  - `artifact_penalty = 0.0`
  - `physchem_penalty = 0.0`
  - `physchem_snapshot = {"aromatic_atom_count": 0, "aromatic_fraction": 0.0, "hetero_atom_count": 8, "molecular_weight_estimate": 401.725, "ring_index_count": 4}`
- `BG_BENZAMIDE`
  - `docking_core = -5.3`
  - `artifact_penalty = 0.0`
  - `physchem_penalty = 2.759`
  - `physchem_flags = single_ring_background`
  - `physchem_snapshot = {"aromatic_atom_count": 6, "aromatic_fraction": 0.667, "hetero_atom_count": 2, "molecular_weight_estimate": 114.083, "ring_index_count": 1}`
- `BG_BIPHENYL`
  - `docking_core = -6.2`
  - `artifact_penalty = 0.0`
  - `physchem_penalty = 4.046`
  - `physchem_flags = simple_aromatic_background, polyaryl_hydrophobe_background`
  - `physchem_snapshot = {"aromatic_atom_count": 12, "aromatic_fraction": 1.0, "hetero_atom_count": 0, "molecular_weight_estimate": 144.132, "ring_index_count": 2}`

Mean top-window `v3` penalties:

- `artifact_penalty = 0.0`
- `physchem_penalty = 2.872`

Interpretation:

- in this focused panel, the useful new signal came mainly from lightweight physicochemical separation
- artifact quality did not drive the observed difference in this case

## Active Margin Interpretation

- Baseline best background: `BG_BIPHENYL` with gap `1.38`
- Enhancement best background: `BG_BENZAMIDE` with gap `6.159`
- Enhancement known active shortlisted: `True`

## Prioritization Interpretation

The enhancement-line prioritization policy for `BRD4_BD1_LIT003_V3EXP` was:

- `filter_keep_then_v3_rerank_margin_then_vina_v2`

Observed values:

- `filter_keep_input_count = 1`
- `shortlist_count = 1`
- `shortlist_cap = 1`
- `top_score_gap = 0.0`
- `v3_priority_tuning = {"mid_gap_shortlist_cap": 2, "top1_only_gap": 0.75, "top2_gap": 0.35}`

Interpretation:

- the shortlist became tighter not because filtering changed, but because prioritization consumed the stronger rerank margin
- this supports the earlier conclusion that the bottleneck had shifted from filtering to shortlist/prioritization

## Performance Snapshot

### `ai_reranking`

- Latest phase timings: `read = 0.006051` | `scoring = 0.011448` | `output = 0.002888`
- Latest cache-hit cases: `none observed in current summary`

### `clustering_and_prioritization`

- Latest phase timings: `read = 0.006355` | `scoring = 0.000629` | `output = 0.001613`
- Latest cache-hit cases: `none observed in current summary`

## Current Conclusion

v3 improves rerank separation and clustering v2 converts that difference into a tighter shortlist without touching the frozen baseline line.

## Recommended Next Step

Use the enhancement-line iteration tracker after each v3 tweak to verify that rerank gap or shortlist compression still improves before expanding the experiment scope.
