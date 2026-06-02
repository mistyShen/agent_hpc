# Enhancement Line V2 vs V3 Comparison

This report is an enhancement-line comparison only. It does not modify or replace the frozen manuscript / benchmark result line.

Source context:

- frozen baseline case: `BRD2_BD2_LIT001`
- enhancement experiment case: `BRD2_BD2_LIT001_V3EXP`
- isolated execution root: `/Users/a1234/Documents/coding/projects/agent_hpc/11_tmp/enhancement_case_fetch/current_v3exp`

## Scope

The comparison focuses on three questions:

1. does `ai_reranking v3` change rerank ordering relative to `v2`
2. does `clustering_and_prioritization v2` convert that extra score separation into a tighter shortlist
3. does the enhancement remain lightweight enough for CPU-only iterative work

## Headline Result

`ai_reranking v3` plus `clustering_and_prioritization v2` improved shortlist selectivity on the current focused validation panel without changing the frozen baseline line.

- baseline `BRD2_BD2_LIT001`
  - `filter_keep_count = 1`
  - `shortlist_count = 1`
  - shortlist: `JQ1`
- enhancement `BRD2_BD2_LIT001_V3EXP`
  - `filter_keep_count = 1`
  - `shortlist_count = 1`
  - shortlist: `JQ1`

This means the new prioritization layer is now consuming the extra separation introduced by `v3`, rather than leaving the shortlist unchanged.

## Comparison Table

| Dimension | `BRD2_BD2_LIT001` | `BRD2_BD2_LIT001_V3EXP` |
| --- | --- | --- |
| Rerank model | `cpu_docking_rerank_v2` | `cpu_docking_rerank_v3` |
| Top 1 | `JQ1` | `JQ1` |
| Top 1 rerank score | `-7.275` | `-8.5` |
| Top 2 | `BG_BIPHENYL` | `BG_ASPIRIN` |
| Top 2 rerank score | `-6.49` | `-6.041` |
| Top 3 | `BG_ASPIRIN` | `BG_ETHYL_PARABEN` |
| Top 3 rerank score | `-6.48` | `-5.561` |
| Filter keep count | `1` | `1` |
| Shortlist count | `1` | `1` |
| Shortlist ids | `JQ1` | `JQ1` |
| Known active id | `JQ1` | `JQ1` |
| Best background id | `BG_BIPHENYL` | `BG_ASPIRIN` |
| Active-best-background gap | `0.785` | `2.459` |
| Known active in shortlist | `n/a` | experimental line, no separate truth row |
| Best known active rank | `None` | experimental line, no separate truth row |

## Reranking Interpretation

The enhancement line changed reranking in two useful ways:

1. it preserved `JQ1` as the top-ranked compound
2. it widened the separation between the active and hard aromatic backgrounds through explicit `physchem_penalty`

Top `v3` diagnostics:

- `JQ1`
  - `docking_core = -8.5`
  - `artifact_penalty = 0.0`
  - `physchem_penalty = 0.0`
  - `physchem_snapshot = {"aromatic_atom_count": 0, "aromatic_fraction": 0.0, "hetero_atom_count": 8, "molecular_weight_estimate": 431.789, "ring_index_count": 4}`
- `BG_ASPIRIN`
  - `docking_core = -6.4`
  - `artifact_penalty = 0.0`
  - `physchem_penalty = 0.359`
  - `physchem_snapshot = {"aromatic_atom_count": 5, "aromatic_fraction": 0.455, "hetero_atom_count": 3, "molecular_weight_estimate": 144.085, "ring_index_count": 1}`
- `BG_ETHYL_PARABEN`
  - `docking_core = -5.8`
  - `artifact_penalty = 0.0`
  - `physchem_penalty = 0.239`
  - `physchem_snapshot = {"aromatic_atom_count": 6, "aromatic_fraction": 0.5, "hetero_atom_count": 3, "molecular_weight_estimate": 156.096, "ring_index_count": 1}`

Mean top-window `v3` penalties:

- `artifact_penalty = 0.0`
- `physchem_penalty = 0.291`

Interpretation:

- in this focused panel, the useful new signal came mainly from lightweight physicochemical separation
- artifact quality did not drive the observed difference in this case

## Active Margin Interpretation

- Baseline best background: `BG_BIPHENYL` with gap `0.785`
- Enhancement best background: `BG_ASPIRIN` with gap `2.459`
- Enhancement known active shortlisted: `True`

## Prioritization Interpretation

The enhancement-line prioritization policy for `BRD2_BD2_LIT001_V3EXP` was:

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

- Latest phase timings: `read = 0.005684` | `scoring = 0.037551` | `output = 0.00368`
- Latest cache-hit cases: `none observed in current summary`

### `clustering_and_prioritization`

- Latest phase timings: `read = 0.007415` | `scoring = 0.000661` | `output = 0.001644`
- Latest cache-hit cases: `none observed in current summary`

## Current Conclusion

v3 improves rerank separation and clustering v2 converts that difference into a tighter shortlist without touching the frozen baseline line.

## Recommended Next Step

Use the enhancement-line iteration tracker after each v3 tweak to verify that rerank gap or shortlist compression still improves before expanding the experiment scope.
