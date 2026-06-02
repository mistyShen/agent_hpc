# Workflow Summary Draft

This file is the narrative source for manuscript/report writing. It should stay aligned with:

- `09_reports/benchmark_comparison.md`
- `09_reports/project_summary.md`
- `00_docs/REAL_BACKEND_STATUS.md`

## What This System Is

`cpu_ai_drug_design` is a CPU-only, Snakemake-based workflow for staged target preparation, ligand library preparation, docking, reranking, filtering, clustering, reporting, and benchmark evaluation.

## What Is Already Real

- `classical_docking` can run a real `vina_cpu` backend and write real docking artifacts
- `ai_reranking` can consume real docking outputs in a lightweight CPU-only reranking stage
- `filtering` and `clustering_and_prioritization` now consume real upstream ranking signals in a lightweight way
- `filtering v2.1` is now frozen for `literature_backed` + `comparison` cases only
  - `vina_affinity <= -6.5`
  - `vina_affinity >= best_vina - 2.0`
  - `rerank_rank <= 3`
- the workflow runs both locally and on the formal HPC project root with the same relative layout
- demo-scale multi-case merge and case-level execution state have been validated on the HPC side through three active cases
- heterogeneous-target two-case and heterogeneous-library two-case validation have both passed
- three-active-case validation has passed
- partial rerun isolation has been validated for untouched cases, targets, and libraries
- minimal literature-backed focused recovery is now fixed on two BRD4 BD1 cases:
  - `BRD4_BD1_LIT001`: `filter_keep_count = 1`, `shortlist_count = 1`, `JQ1 rank = 1`
  - `BRD4_BD1_LIT002`: `filter_keep_count = 2`, `shortlist_count = 2`, `I-BET762 rank = 1`

## What Is Still Provisional

- benchmark coverage is still narrow even though two literature-backed BRD4 cases are now fixed
- filtering, clustering, and evaluation logic remain lightweight rather than benchmark-grade
- current reports are operationally useful but not yet benchmark-grade
- larger-scale benchmark behavior is not yet validated

## Current Scientific Position

The system is no longer just a dry scaffold, but it is not yet a publication-ready benchmark. It is best described as a reproducible CPU-only workflow with real docking integration, lightweight downstream consumption of those real artifacts, a demo-scale multi-case recovery path, and a narrow literature-backed recovery boundary fixed on two BRD4 BD1 cases.

## Current Validation Boundary

- validated now:
  - end-to-end real `vina_cpu` docking on the server
  - downstream reranking, filtering, and shortlist generation consuming real docking outputs
  - single-case runtime-state behavior
  - two-case and three-case manifest state, case-level execution tracking, and case-aware output merge under partial rerun
  - heterogeneous-target two-case validation
  - heterogeneous-library two-case validation
  - three-active-case validation
  - partial rerun isolation for untouched cases, targets, and libraries
  - `BRD4_BD1_LIT001` retains `JQ1` in filter keep and shortlist at rank `1`
  - `BRD4_BD1_LIT002` retains `I-BET762` in filter keep and shortlist at rank `1`
  - `filtering v2.1` is compatible with both current literature-backed BRD4 cases
- not yet validated:
  - larger-scale multi-case benchmark behavior
  - literature-backed benchmark claims outside the current two BRD4 cases

## Current Capability Matrix

| Capability | Current status | Evidence boundary |
| --- | --- | --- |
| `single-case` | validated | local plus HPC execution-state checks |
| `heterogeneous-target two-case` | validated | HPC two-case run with distinct `target_id` values |
| `heterogeneous-library two-case` | validated | HPC two-case run with distinct `library_id` values |
| `three active cases` | validated | HPC three-case run with isolated partial rerun on `DEMO_CASE_003` |
| `partial rerun isolation` | validated | untouched case, target, and library rows remained unchanged |
| `multi-case merge` | validated at demo scale | up to three active cases |
| `current backend status` | partial real integration | real `vina_cpu` docking plus lightweight downstream consumers |

## Current Comparison Template

The current manuscript-facing comparison layer now uses a fixed case-level table with these columns:

| Case | Target | Library | Type | Tier | Purpose | Metric | Docking | Reranked | Filtered | Keep | Shortlist | Top 1 | Top 2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `DEMO_CASE_001` | `DEMO_TARGET_001` | `DEMO_LIB_001` | `toy` | `bringup` | `debug` | `none` | case-level count | case-level count | case-level count | case-level keep count | case-level shortlist count | top shortlist compound | second shortlist compound |
| `DEMO_CASE_002` | `DEMO_TARGET_002` | `DEMO_LIB_002` | `debug` | `smoke` | `debug` | `none` | case-level count | case-level count | case-level count | case-level keep count | case-level shortlist count | top shortlist compound | second shortlist compound |
| `DEMO_CASE_003` | `DEMO_TARGET_001` | `DEMO_LIB_002` | `debug` | `smoke` | `debug` | `none` | case-level count | case-level count | case-level count | case-level keep count | case-level shortlist count | top shortlist compound | second shortlist compound |
| `BRD4_BD1_LIT001` | `BRD4_BD1_4QZS` | `BRD4_LIT_FOCUSED_001` | `literature_backed` | `comparison` | `comparison` | `shortlist_contains_known_active` | `24` | `24` | `24` | `1` | `1` | `JQ1` | `-` |
| `BRD4_BD1_LIT002` | `BRD4_BD1_4C66` | `BRD4_LIT_FOCUSED_002` | `literature_backed` | `comparison` | `comparison` | `shortlist_contains_known_active` | `6` | `6` | `6` | `2` | `2` | `I-BET762` | `BG_BIPHENYL` |

Current report entry points:

- `09_reports/benchmark_comparison.md`
- `09_reports/benchmark_comparison.json`
- `09_reports/benchmark_summary.md`
- `09_reports/project_summary.md`

## Manuscript-Ready Core Claims

Claims that are currently supported by local and HPC evidence:

- the workflow can execute end to end under a CPU-only constraint
- `classical_docking` can produce real `vina_cpu` outputs
- downstream reranking, filtering, and shortlist generation can consume those real docking outputs
- case-aware partial rerun does not contaminate untouched cases, targets, or libraries at demo scale
- demo-scale multi-case merge is validated through three active cases with heterogeneous target and library coverage
- `filtering v2.1` is compatible with both current literature-backed BRD4 cases
- `BRD4_BD1_LIT001` and `BRD4_BD1_LIT002` both recover the known active at shortlist rank `1`

Claims that are still out of scope:

- benchmark superiority
- realistic prospective performance
- literature recovery performance
- larger-scale multi-case robustness

## Suggested Figures And Tables

Minimum manuscript/report set using current artifacts:

1. workflow schematic
2. module/backend status table
3. runtime-state and recovery boundary table
4. benchmark comparison table
5. per-case shortlist table
6. limitations and validated-boundary table

Current source artifacts for those items:

- workflow/system narrative: `09_reports/workflow_summary_draft.md`
- backend status: `00_docs/REAL_BACKEND_STATUS.md`
- benchmark comparison table: `09_reports/benchmark_comparison.md`
- top-level operational summary: `09_reports/project_summary.md`

## Immediate Path To A Trustworthy Benchmark

1. freeze the current manuscript-style comparison table and summary wording
2. freeze a concise handoff summary so the current validated state is not lost
3. extend validation from the two BRD4 literature-backed cases to broader realistic or literature-backed panels
4. define benchmark-grade evaluation metrics and comparison tables
5. extend validation from three active cases to larger multi-case benchmarks
