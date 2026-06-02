# Benchmark Comparison

This file is the fixed manuscript-facing comparison snapshot for the current literature-backed evidence boundary. Auto-generated comparison summaries may lag behind the current validated state; this markdown file is the frozen reference for the two BRD4 literature-backed claims.

## Fixed Literature-Backed Comparison Table

| Case | Target | Library | Keep | Shortlist | Top 1 | Top 2 | Shortlist Contains Known Active | Best Known Active Rank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `BRD4_BD1_LIT001` | `BRD4_BD1_4QZS` | `BRD4_LIT_FOCUSED_001` | `1` | `1` | `JQ1` | `-` | `true` | `1` |
| `BRD4_BD1_LIT002` | `BRD4_BD1_4C66` | `BRD4_LIT_FOCUSED_002` | `2` | `2` | `I-BET762` | `BG_BIPHENYL` | `true` | `1` |

## Frozen Filtering Branch

- active only when `case_type == literature_backed`
- active only when `run_purpose == comparison`
- current fixed `v2.1` rules:
  - `vina_affinity <= -6.5`
  - `vina_affinity >= best_vina - 2.0`
  - `rerank_rank <= 3`

## Interpretation Boundary

- these two cases provide a minimal focused BRD4 BD1 recovery boundary
- they support a narrow claim that the known active remains rank `1` under the current frozen literature-backed filtering branch
- they do not support a broad cross-target benchmark claim
