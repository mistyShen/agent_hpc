# Enhancement Line Iteration Tracker

- Generated at: `2026-04-16T06:31:46.689113+00:00`
- Source report: `09_reports/enhancement_line_v2_vs_v3_comparison.json`
- Baseline case: `BRD4_BD1_LIT002`
- Enhancement case: `BRD4_BD1_LIT002_V3EXP`

## Headline Metrics

| Metric | Baseline | Enhancement | Delta |
| --- | --- | --- | --- |
| Top1-Top2 rerank gap | `0.81` | `6.146` | `5.336` |
| Active-best-background gap | `0.81` | `6.146` | `5.336` |
| Shortlist compression ratio | `1.0` | `0.5` | `0.5` |

## Shortlist Behavior

- Baseline filter keep / shortlist: `2` / `2`
- Enhancement filter keep / shortlist: `2` / `1`
- Baseline shortlist ids: `I-BET762, BG_BIPHENYL`
- Enhancement shortlist ids: `I-BET762`
- Baseline known active shortlisted: `True`
- Enhancement known active shortlisted: `True`

## Cache Behavior

- `ai_reranking` cache-hit runtime seconds: `0.002139`
- `clustering_and_prioritization` cache-hit runtime seconds: `0.00015`

## Decision

- Rerank gap improved: `True`
- Active margin improved: `True`
- Shortlist compressed: `True`
- Continue `v3` line: `True`
