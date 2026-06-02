# Benchmark Result Table Final

This file is the final manuscript-facing benchmark result table for the current frozen evidence boundary. It is derived only from the frozen project documents and does not introduce any new computation or claims.

## Current Validated Scope

| Category | Current fixed status | Claim boundary |
| --- | --- | --- |
| Execution framework | CPU-only workflow executes end to end | supported |
| Real backend | `classical_docking` runs real `vina_cpu` and writes real docking artifacts | supported |
| Downstream consumers | `ai_reranking`, `filtering`, and `clustering_and_prioritization` consume real docking-derived signals in a lightweight way | supported |
| Multi-case behavior | single-case, heterogeneous two-case, and three-active-case execution validated at demo scale | supported at demo scale only |
| Partial rerun isolation | untouched cases, targets, and libraries remain isolated under partial rerun | supported at demo scale only |
| Literature-backed recovery | two focused BRD4 BD1 cases fixed | narrow evidence boundary only |
| Benchmark-grade comparison | not established | not supported |

## Fixed Literature-Backed Recovery Table

| Case | Target | Library | Known Active | Filter Keep Count | Shortlist Count | Top 1 | Top 2 | Shortlist Contains Known Active | Best Known Active Rank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `BRD4_BD1_LIT001` | `BRD4_BD1_4QZS` | `BRD4_LIT_FOCUSED_001` | `JQ1` | `1` | `1` | `JQ1` | `-` | `true` | `1` |
| `BRD4_BD1_LIT002` | `BRD4_BD1_4C66` | `BRD4_LIT_FOCUSED_002` | `I-BET762` | `2` | `2` | `I-BET762` | `BG_BIPHENYL` | `true` | `1` |

## Fixed Filtering v2.1 Applicability Boundary

- active only when `case_type == literature_backed`
- active only when `run_purpose == comparison`
- current fixed rules:
  - `vina_affinity <= -6.5`
  - `vina_affinity >= best_vina - 2.0`
  - `rerank_rank <= 3`

## Allowed Interpretation

- the workflow is a reproducible CPU-only execution framework with real docking integration
- lightweight downstream consumers can operate on real docking artifacts
- two BRD4 BD1 literature-backed focused cases recover the known active at shortlist rank `1`

## Disallowed Over-Claim

- benchmark superiority
- broad literature recovery performance
- robust cross-target generalization
- prospective hit quality
- larger-scale multi-case benchmark robustness
