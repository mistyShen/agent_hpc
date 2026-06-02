# Workflow Health Report

- Workflow status: `failed`
- Failed modules: `1`
- Warning modules: `7`

## Module Health

| Module | Status | Key checks |
| --- | --- | --- |
| `target_preparation` | `warning` | done, summary, outputs |
| `compound_library_preparation` | `warning` | done, summary, outputs |
| `classical_docking` | `failed` | done, summary, outputs |
| `ai_reranking` | `warning` | done, summary, outputs |
| `filtering` | `warning` | done, summary, outputs |
| `clustering_and_prioritization` | `warning` | done, summary, outputs |
| `report_generation` | `warning` | done, summary, outputs |
| `benchmark_evaluation` | `warning` | done, summary, outputs |

## Findings

### `target_preparation`
- warning: `missing_log`

### `compound_library_preparation`
- warning: `missing_log`

### `classical_docking`
- issue: `classical_docking_engine_mode_mismatch:config=vina_cpu,summary=scaffold_heuristic`
- warning: `missing_log`

### `ai_reranking`
- warning: `missing_log`

### `filtering`
- warning: `missing_log`

### `clustering_and_prioritization`
- warning: `missing_log`
- warning: `one_or_more_tsv_outputs_have_no_data_rows`

### `report_generation`
- warning: `missing_log`

### `benchmark_evaluation`
- warning: `missing_log`
