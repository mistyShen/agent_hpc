# Enhancement Line V2 vs V3 Comparison

This report is an enhancement-line comparison only. It does not modify or replace the frozen manuscript / benchmark result line.

Source context:

- frozen baseline case: `BRD2_BD1_LIT002`
- enhancement experiment case: `BRD2_BD1_LIT002_V3EXP`
- isolated execution root: `/Users/a1234/Documents/coding/projects/agent_hpc/11_tmp/enhancement_case_fetch/current_v3exp`

## Scope

The comparison focuses on three questions:

1. does `ai_reranking v3` change rerank ordering relative to `v2`
2. does `clustering_and_prioritization v2` convert that extra score separation into a tighter shortlist
3. does the enhancement remain lightweight enough for CPU-only iterative work

## Headline Result

`ai_reranking v3` plus `clustering_and_prioritization v2` improved shortlist selectivity on the current focused validation panel without changing the frozen baseline line.

- baseline `BRD2_BD1_LIT002`
  - `filter_keep_count = 0`
  - `shortlist_count = 0`
  - shortlist: ``
- enhancement `BRD2_BD1_LIT002_V3EXP`
  - `filter_keep_count = 0`
  - `shortlist_count = 0`
  - shortlist: ``

This means the new prioritization layer is now consuming the extra separation introduced by `v3`, rather than leaving the shortlist unchanged.

## Comparison Table

| Dimension | `BRD2_BD1_LIT002` | `BRD2_BD1_LIT002_V3EXP` |
| --- | --- | --- |
| Rerank model | `cpu_docking_rerank_v2` | `cpu_docking_rerank_v3` |
| Top 1 | `BG_BENZAMIDE` | `I-BET762` |
| Top 1 rerank score | `-4.76` | `-5.4` |
| Top 2 | `BG_BIPHENYL` | `BG_BENZAMIDE` |
| Top 2 rerank score | `-4.4` | `-1.041` |
| Top 3 | `BG_NAPHTHALENE` | `BG_QUINOLINE` |
| Top 3 rerank score | `-4.22` | `-0.284` |
| Filter keep count | `0` | `0` |
| Shortlist count | `0` | `0` |
| Shortlist ids | `` | `` |
| Known active id | `I-BET762` | `I-BET762` |
| Best background id | `BG_BENZAMIDE` | `BG_BENZAMIDE` |
| Active-best-background gap | `-1.45` | `4.359` |
| Known active in shortlist | `false` | experimental line, no separate truth row |
| Best known active rank | `None` | experimental line, no separate truth row |

## Reranking Interpretation

The enhancement line changed reranking in two useful ways:

1. it preserved `I-BET762` as the top-ranked compound
2. it widened the separation between the active and hard aromatic backgrounds through explicit `physchem_penalty`

Top `v3` diagnostics:

- `I-BET762`
  - `docking_core = -5.4`
  - `artifact_penalty = 0.0`
  - `physchem_penalty = 0.0`
  - `physchem_snapshot = {"aromatic_atom_count": 0, "aromatic_fraction": 0.0, "hetero_atom_count": 8, "molecular_weight_estimate": 401.725, "ring_index_count": 4}`
- `BG_BENZAMIDE`
  - `docking_core = -3.8`
  - `artifact_penalty = 0.0`
  - `physchem_penalty = 2.759`
  - `physchem_flags = single_ring_background`
  - `physchem_snapshot = {"aromatic_atom_count": 6, "aromatic_fraction": 0.667, "hetero_atom_count": 2, "molecular_weight_estimate": 114.083, "ring_index_count": 1}`
- `BG_QUINOLINE`
  - `docking_core = -4.0`
  - `artifact_penalty = 0.0`
  - `physchem_penalty = 3.716`
  - `physchem_flags = simple_aromatic_background, polyaryl_hydrophobe_background`
  - `physchem_snapshot = {"aromatic_atom_count": 10, "aromatic_fraction": 1.0, "hetero_atom_count": 1, "molecular_weight_estimate": 122.106, "ring_index_count": 2}`

Mean top-window `v3` penalties:

- `artifact_penalty = 0.0`
- `physchem_penalty = 2.961`

Interpretation:

- in this focused panel, the useful new signal came mainly from lightweight physicochemical separation
- artifact quality did not drive the observed difference in this case

## Active Margin Interpretation

- Baseline best background: `BG_BENZAMIDE` with gap `-1.45`
- Enhancement best background: `BG_BENZAMIDE` with gap `4.359`
- Enhancement known active shortlisted: `False`

## Prioritization Interpretation

The enhancement-line prioritization policy for `BRD2_BD1_LIT002_V3EXP` was:

- `filter_keep_then_v3_rerank_margin_then_vina_v2`

Observed values:

- `filter_keep_input_count = 0`
- `shortlist_count = 0`
- `shortlist_cap = 0`
- `top_score_gap = 0.0`
- `v3_priority_tuning = {"mid_gap_shortlist_cap": 2, "top1_only_gap": 0.75, "top2_gap": 0.35}`

Interpretation:

- the shortlist became tighter not because filtering changed, but because prioritization consumed the stronger rerank margin
- this supports the earlier conclusion that the bottleneck had shifted from filtering to shortlist/prioritization

## Performance Snapshot

### `ai_reranking`

- Latest phase timings: `read = 0.015215` | `scoring = 0.083376` | `output = 0.01464`
- Latest cache-hit cases: `none observed in current summary`

### `clustering_and_prioritization`

- Latest phase timings: `read = 0.020522` | `scoring = 0.001799` | `output = 0.003668`
- Latest cache-hit cases: `none observed in current summary`

## Current Conclusion

v3 improves rerank separation and clustering v2 converts that difference into a tighter shortlist without touching the frozen baseline line.

## Recommended Next Step

Use the enhancement-line iteration tracker after each v3 tweak to verify that rerank gap or shortlist compression still improves before expanding the experiment scope.
