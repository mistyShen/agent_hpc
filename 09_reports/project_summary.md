# Project Summary

- Project: `cpu_ai_drug_design`
- Project root: `/shared/shen/cpu_ai_drug_design`
- Generated at: `2026-04-15T03:14:38.916834+00:00`
- Benchmark cases: `5`
- Enabled benchmark cases: `5`

## Module Status

- `ai_reranking`: `reranking_completed`
- `benchmark_evaluation`: `evaluation_completed`
- `classical_docking`: `docking_completed`
- `clustering_and_prioritization`: `clustering_completed`
- `compound_library_preparation`: `library_preparation_completed`
- `filtering`: `filtering_completed`
- `report_generation`: `report_generated`
- `run_state_checker`: `workflow_health_checked`
- `target_preparation`: `target_preparation_completed`

## Key Outputs

- Targets prepared: `3`
- Library records prepared: `56`
- Docking rows: `28`
- Reranked rows: `28`
- Filtered candidate count: `0`
- Prioritized candidate count: `0`
- Evaluation status: `typed_lightweight_complete`
- Comparison cases summarized: `4`

## Cases

- `DEMO_CASE_001` -> target `DEMO_TARGET_001`, library `DEMO_LIB_001`
- `DEMO_CASE_002` -> target `DEMO_TARGET_002`, library `DEMO_LIB_002`
- `DEMO_CASE_003` -> target `DEMO_TARGET_001`, library `DEMO_LIB_002`
- `BRD4_BD1_LIT001` -> target `BRD4_BD1_4QZS`, library `BRD4_LIT_FOCUSED_001`
- `BRD4_BD1_LIT002` -> target `BRD4_BD1_4C66`, library `BRD4_LIT_FOCUSED_002`

## Comparison Snapshot

| Case | Type | Purpose | Docking | Reranked | Filtered | Keep | Shortlist |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DEMO_CASE_001 | toy | debug | 4 | 4 | 4 | 0 | 0 |
| DEMO_CASE_002 | debug | debug | 0 | 0 | 0 | 0 | 0 |
| DEMO_CASE_003 | debug | debug | 0 | 0 | 0 | 0 | 0 |
| BRD4_BD1_LIT001 | literature_backed | comparison | 0 | 0 | 0 | 0 | 0 |

- Comparison markdown: `09_reports/benchmark_comparison.md`
- Comparison json: `09_reports/benchmark_comparison.json`
