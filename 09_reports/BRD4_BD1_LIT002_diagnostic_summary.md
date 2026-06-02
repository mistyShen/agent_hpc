# BRD4_BD1_LIT002 Diagnostic Summary

## Scope

- Case: `BRD4_BD1_LIT002`
- Target: `BRD4_BD1_4C66`
- Library: `BRD4_LIT_FOCUSED_002`
- Panel size: `6` compounds
- Known active: `I-BET762`

## Case Table

| Compound | Role | Vina Affinity | Rerank Bonus | Rerank Score | Filter | Filter Reason | Cluster | Priority Rank | MW Est. | Heavy Atoms | Hetero Atoms | Aromatic Atoms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| I-BET762 | known active | -8.8 | 1.12 | -7.68 | keep | passes_lightweight_real_filter_v1 | amine_like | 1 | 401.725 | 30 | 8 | 0 |
| BG_BIPHENYL | background | -6.8 | -0.07 | -6.87 | keep | passes_lightweight_real_filter_v1 | aromatic_ring | 2 | 144.132 | 12 | 0 | 12 |
| BG_BENZAMIDE | background | -5.6 | -0.87 | -6.47 | keep | passes_lightweight_real_filter_v1 | aromatic_ring | 3 | 114.083 | 9 | 2 | 6 |
| BG_NAPHTHALENE | background | -6.1 | 0.075 | -6.025 | keep | passes_lightweight_real_filter_v1 | other | 4 | 120.110 | 10 | 0 | 10 |
| BG_QUINOLINE | background | -6.0 | 0.07 | -5.93 | keep | passes_lightweight_real_filter_v1 | other | 5 | 122.106 | 10 | 1 | 10 |
| BG_INDOLE | background | -5.7 | 0.115 | -5.585 | keep | passes_lightweight_real_filter_v1 | other | 6 | 110.095 | 9 | 1 | 9 |

## Interpretation

- `I-BET762` ranks first because it starts with the strongest docking signal by a clear margin.
- The docking gap is the main separator: `I-BET762 = -8.8`, next-best background `BG_BIPHENYL = -6.8`.
- `ai_reranking` does not create the win for `I-BET762`; it mostly preserves the docking order.
- `BG_BENZAMIDE` gets a favorable rerank adjustment, but not enough to overtake the docking lead of `I-BET762`.
- This diagnosis described the pre-`filtering v2.1` state, where all five backgrounds passed filtering because the literature-backed thresholds were still permissive for this already-focused panel.
- `clustering_and_prioritization` is not the bottleneck: it simply sorts the kept set by `rerank_score`, then `vina_affinity`, then `rerank_rank`.

## Bottleneck Call

- Most likely bottleneck layer for case-level discrimination in the pre-`v2.1` state: `filtering`
- Secondary limitation: the panel is still composed of background molecules that produce moderately favorable docking scores in the BRD4 pocket.
- Least likely bottleneck: `clustering_and_prioritization`

## Historical Next Change

- This recommendation has now been actioned through the case-aware literature-backed `filtering v2.1` branch.
- The current historical value of this note is to document why the filtering layer, rather than docking or clustering, was chosen for the next upgrade.
