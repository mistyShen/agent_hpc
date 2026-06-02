# Project Summary

This file is a frozen narrative summary for the current validated project state. Auto-generated summary files may contain stale counts after selective reruns; use this file and `09_reports/benchmark_comparison.md` as the fixed reference for current literature-backed claims.

## Current Fixed Literature-Backed State

- `BRD4_BD1_LIT001`: `filter_keep_count = 1`, `shortlist_count = 1`, `JQ1 rank = 1`
- `BRD4_BD1_LIT002`: `filter_keep_count = 2`, `shortlist_count = 2`, `I-BET762 rank = 1`
- `filtering v2.1` is active only for `literature_backed + comparison` cases

## Current Fixed Filtering Branch

- `vina_affinity <= -6.5`
- `vina_affinity >= best_vina - 2.0`
- `rerank_rank <= 3`

## Boundary

- fixed now:
  - real `vina_cpu` docking is wired into the main workflow
  - lightweight reranking, filtering, and shortlist generation consume real docking outputs
  - demo-scale multi-case merge and partial rerun isolation are validated
  - two BRD4 BD1 literature-backed focused recovery cases are fixed
- not fixed yet:
  - larger-scale multi-case benchmark behavior
  - cross-target literature-backed comparison evidence
  - benchmark-grade metrics

## Reference Files

- backend status: `00_docs/REAL_BACKEND_STATUS.md`
- workflow narrative: `09_reports/workflow_summary_draft.md`
- manuscript narrative: `09_reports/manuscript_draft.md`
- comparison summary: `09_reports/benchmark_comparison.md`
