# Benchmark Result Table Draft

This file is a manuscript-facing result-expression draft derived only from the frozen reference documents listed below:

- `00_docs/REAL_BACKEND_STATUS.md`
- `09_reports/manuscript_draft.md`
- `09_reports/workflow_summary_draft.md`
- `09_reports/benchmark_comparison.md`
- `09_reports/benchmark_summary.md`
- `09_reports/FREEZE_SUMMARY.md`

No new computation is performed here. This file should be treated as an expression-layer summary of the current frozen state.

## 1. Current Validated Scope

| Layer | Current fixed status | Claim boundary |
| --- | --- | --- |
| Workflow execution | end-to-end CPU-only workflow is runnable | operational claim supported |
| Real backend | `classical_docking` runs real `vina_cpu` and writes real docking artifacts | supported |
| Downstream consumption | `ai_reranking`, `filtering`, and `clustering_and_prioritization` consume real docking-derived signals in a lightweight way | supported |
| Multi-case execution | single-case, heterogeneous-target two-case, heterogeneous-library two-case, and three-active-case execution are validated at demo scale | supported at demo scale only |
| Partial rerun isolation | untouched cases, targets, and libraries remain isolated under partial rerun at demo scale | supported at demo scale only |
| Literature-backed recovery | two BRD4 BD1 focused recovery cases are fixed | narrow evidence boundary only |
| Benchmark-grade comparison | not yet established | not supported |

## 2. Fixed BRD4 BD1 Literature-Backed Comparison

| Case | Target | Library | Known Active | Filter Keep Count | Shortlist Count | Top 1 | Top 2 | Shortlist Contains Known Active | Best Known Active Rank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `BRD4_BD1_LIT001` | `BRD4_BD1_4QZS` | `BRD4_LIT_FOCUSED_001` | `JQ1` | `1` | `1` | `JQ1` | `-` | `true` | `1` |
| `BRD4_BD1_LIT002` | `BRD4_BD1_4C66` | `BRD4_LIT_FOCUSED_002` | `I-BET762` | `2` | `2` | `I-BET762` | `BG_BIPHENYL` | `true` | `1` |

## 3. Fixed Filtering v2.1 Boundary

Current fixed `filtering v2.1` branch:

- active only when `case_type == literature_backed`
- active only when `run_purpose == comparison`
- current rules:
  - `vina_affinity <= -6.5`
  - `vina_affinity >= best_vina - 2.0`
  - `rerank_rank <= 3`

Interpretation:

- this branch is frozen because it is compatible with both current BRD4 literature-backed cases
- this branch should currently be described as a case-aware focused recovery rule
- this branch should not yet be described as a broadly validated cross-target benchmark filter

## 4. Current Non-Overclaim Boundary

Claims that are currently safe:

- the workflow is a reproducible CPU-only execution framework
- real `vina_cpu` docking is integrated into the main path
- lightweight downstream ranking/filtering/shortlisting can consume real docking artifacts
- demo-scale multi-case merge and case-aware partial rerun isolation are validated
- two BRD4 BD1 literature-backed focused cases recover the known active at shortlist rank `1`

Claims that should not be made now:

- benchmark superiority
- broad literature recovery performance
- robust cross-target generalization
- prospective hit quality
- larger-scale multi-case benchmark robustness

## 5. Suggested Figure / Table Mapping

| Output need | Recommended source from this draft |
| --- | --- |
| manuscript scope table | section `1. Current Validated Scope` |
| literature-backed comparison table | section `2. Fixed BRD4 BD1 Literature-Backed Comparison` |
| filtering boundary box | section `3. Fixed Filtering v2.1 Boundary` |
| limitations / non-overclaim box | section `4. Current Non-Overclaim Boundary` |

## 6. Recommended Next Evidence Layer

The next evidence-layer expansion should remain narrow and controlled:

1. keep the current BRD4 literature-backed boundary frozen
2. add one new realistic or literature-backed evidence layer only after defining the exact claim boundary in advance
3. avoid changing the frozen `v2.1` filter branch unless a new comparison need clearly requires it
