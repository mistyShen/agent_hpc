# Enhancement Boundary Challenge Report

- Generated at: `2026-04-17T03:36:31.084741+00:00`
- Base case: `BRD2_BD1_LIT002`
- Enhancement case: `BRD2_BD1_LIT002_V3EXP`
- Scope: enhancement-line diagnostic only. This report is for boundary review and must not be promoted into frozen claims.

## Challenge Readout

- Challenge class: `filter_gated_after_rerank_gain`
- Effective filter policy: `literature_comparison_filter_v2`
- Configured case filter_policy field: `lightweight_real_filter_v1`
- Rollout preserved: `False`
- Boundary impact: `exclude_from_current_approved_boundary`

## Baseline vs Enhancement

| Case | Known active rank | Known active shortlisted | Filter keep count | Shortlist count | Best background | Gap |
| --- | --- | --- | --- | --- | --- | --- |
| `BRD2_BD1_LIT002` | `6` | `False` | `0` | `0` | `BG_BENZAMIDE` | `-1.45` |
| `BRD2_BD1_LIT002_V3EXP` | `1` | `False` | `0` | `0` | `BG_BENZAMIDE` | `4.359` |

## Root Cause

- Enhancement reranking clearly improves ordering: `BRD2_BD1_LIT002_V3EXP` moves `I-BET762` from baseline rank `6` to enhancement rank `1` and raises the active-best-background gap from `-1.45` to `4.359`.
- Filtering blocks the gain because the effective policy is `literature_comparison_filter_v2`, not the literal metadata field `lightweight_real_filter_v1`.
- The first hard gate is `vina_affinity <= -6.5`; the best enhancement vina in this surface is only `-5.4`, so every candidate is excluded before shortlist construction.
- All enhancement candidates were excluded for the same reason: `vina_affinity_above_threshold=6`.
- Clustering is therefore downstream-empty rather than independently failing: it receives `filter_keep_input_count = 0`, so shortlist generation never gets a candidate set to prioritize.

## Filter Thresholds

- `max_vina_affinity = -6.5`
- `relative_vina_window = 2.0`
- `max_rerank_rank = 3`

## Enhancement Candidate Decisions

| Compound | Rerank rank | Rerank score | Vina affinity | Filter decision | Filter reason |
| --- | --- | --- | --- | --- | --- |
| `I-BET762` | `1` | `-5.4` | `-5.4` | `exclude_by_rule` | `vina_affinity_above_threshold` |
| `BG_BENZAMIDE` | `2` | `-1.041` | `-3.8` | `exclude_by_rule` | `vina_affinity_above_threshold` |
| `BG_QUINOLINE` | `3` | `-0.284` | `-4.0` | `exclude_by_rule` | `vina_affinity_above_threshold` |
| `BG_BIPHENYL` | `4` | `-0.154` | `-4.2` | `exclude_by_rule` | `vina_affinity_above_threshold` |
| `BG_NAPHTHALENE` | `5` | `0.086` | `-4.2` | `exclude_by_rule` | `vina_affinity_above_threshold` |
| `BG_INDOLE` | `6` | `0.137` | `-3.7` | `exclude_by_rule` | `vina_affinity_above_threshold` |

## Audit Context

- Current best background: `BG_BENZAMIDE`
- Current best-background flags: `single_ring_background`
- Current shortlist ids: `none`

## Recommendation

- Keep this surface logged as a boundary challenge rather than a rollout-safe material case.
- Do not use its rerank gain alone to expand the approved enhancement-line boundary while shortlist preservation is still broken.
- If we revisit it later, the right review surface is the literature-comparison filtering gate on this target/panel pairing, not more v3 rerank tuning.
