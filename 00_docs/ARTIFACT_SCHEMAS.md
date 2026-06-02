# Artifact Schemas

## `07_results/run_manifest.json`

Purpose:

- defines the run scope shared by every module
- records input manifests and case counts for reproducibility
- acts as the top-level run identity for local and HPC executions

Required top-level keys:

- `project_name`
- `project_root`
- `generated_at_utc`
- `inputs`
- `counts`
- `mode`
- `execution_state`

Required `inputs` keys:

- `datasets_manifest`
- `targets_manifest`
- `compound_libraries_manifest`
- `benchmark_cases_manifest`

Required `counts` keys:

- `datasets`
- `targets`
- `compound_libraries`
- `benchmark_cases`

Recommended additional keys:

- `enabled_benchmark_cases` under `counts`
- `schemas`

Required `execution_state` keys:

- `modules`
- `cases`

`execution_state.modules.<module>` current runtime contract:

- `runtime_seconds`
- `execution_status`
- `backend_mode`
- `updated_at_utc`

`execution_state.cases.<case_id>.<module>` current runtime contract:

- `runtime_seconds`
- `execution_status`
- `backend_mode`
- `updated_at_utc`

Current recommended case-level runtime fields:

- `skipped_cache`
- `skip_reason`
- `cache_hit_artifact`

Module-specific optional case-level fields:

- `result_row_count`
- `evaluated_candidate_count`
- `kept_candidate_count`
- `prioritized_candidate_count`
- `artifact_cache_hit_count`

Current note:

- the current `mode` may still read `scaffold_only` even though some modules now use real backends
- backend reality should be interpreted from module summaries and `00_docs/REAL_BACKEND_STATUS.md`

## `07_results/modules/<module>/done.json`

Purpose:

- marks module completion for Snakemake dependency tracking
- records whether the expected artifacts were written
- captures enough context to support partial reruns and postmortem debugging

Required top-level keys:

- `module`
- `status`
- `config`
- `project_root`
- `run_manifest`
- `input_manifest`
- `timestamp_utc`
- `validation`
- `run_context`
- `module_profile`
- `input_summary`
- `notes`

Current recommended additional top-level keys:

- `execution`
- `cache`

Minimum required `validation` keys:

- `run_manifest_exists`
- `input_manifest_exists`

Current recommended `execution` keys:

- `runtime_seconds`
- `execution_status`
- `backend_mode`

Current recommended optional `execution` keys:

- `skipped_cache`
- `skip_reason`
- `selected_case_ids`
- `partial_rerun_active`

Current recommended `cache` keys:

- `signature`
- `cache_scope`
- `cache_hit`

Current recommended optional `cache` keys:

- `cache_hit_artifact`
- `cached_case_count`
- `cached_result_count`
- `ligand_cache_hit_count`

Recommended `module_profile` keys:

- `stage_type`
- `primary_inputs`
- `primary_outputs`
- `next_action_hint`

Allowed current statuses:

- `target_preparation_completed`
- `library_preparation_completed`
- `docking_completed`
- `reranking_completed`
- `filtering_completed`
- `clustering_completed`
- `report_generated`
- `evaluation_completed`
- `workflow_health_checked`

Interpretation:

- `done.json` says the module completed and wrote its declared outputs
- it does not by itself prove scientific validity
- scientific trust should be assessed from the module summary, the backend mode, and the benchmark case type
- for partial reruns, `selected_case_ids` defines which case subset the module was asked to refresh
- `skipped_cache=true` means the module accepted existing outputs as valid for the requested scope

## Module Log Files

Path pattern:

- `07_results/logs/<module>.log`

Purpose:

- capture stdout and stderr for the exact module invocation
- provide first-line evidence when a module exits non-zero
- preserve backend error messages that are too detailed for `done.json`

Recovery rule:

- if `done.json` is missing or stale, read the module log first
- if `done.json` exists but outputs look inconsistent, compare the log timestamp and summary timestamp

## `classical_docking/docking_results.tsv`

Current required columns:

- `case_id`
- `target_id`
- `library_id`
- `compound_id`
- `prepared_structure_path`
- `standardized_smiles`
- `docking_protocol`
- `receptor_pdbqt_path`
- `ligand_pdbqt_path`
- `pose_pdbqt_path`
- `docking_score`
- `vina_affinity_kcal_mol`
- `pose_rank`
- `backend_name`
- `engine_mode`

Column semantics:

- `docking_score` is the downstream sort key and currently equals Vina affinity when the real backend is used
- `vina_affinity_kcal_mol` should be blank only when the heuristic fallback is active
- `ligand_pdbqt_path` and `pose_pdbqt_path` should be non-empty for real `vina_cpu` rows
- `engine_mode` distinguishes `vina_cpu` from fallback execution

## `ai_reranking/reranked_candidates.tsv`

Current required columns:

- `case_id`
- `target_id`
- `library_id`
- `compound_id`
- `standardized_smiles`
- `docking_score`
- `rerank_bonus`
- `rerank_score`
- `rerank_rank`
- `rerank_model`

Column semantics:

- `docking_score` is copied through from docking results
- `rerank_bonus` is the additive adjustment applied by the reranker
- `rerank_score` is the final ordering score
- `rerank_model` identifies the reranking policy version

Compatibility rule:

- this column set is currently frozen
- richer diagnostics should go to `reranking_summary.json` before adding TSV columns

## Summary JSON Files

Each module summary JSON should provide:

- module name
- generation timestamp
- row or candidate counts
- the active backend or model name when relevant
- top-hit or aggregate output preview
- main output table path

Current recommended runtime additions for summaries when relevant:

- `runtime_seconds`
- `execution_status`
- `selected_case_ids`
- `partial_rerun_active`

Current examples:

- `classical_docking/docking_summary.json`
- `ai_reranking/reranking_summary.json`
- `filtering/filter_summary.json`
- `clustering_and_prioritization/clustering_summary.json`
- `run_state_checker/workflow_health_summary.json`

`run_state_checker/workflow_health_summary.json` current machine-readable validation fields:

- `runtime_state_validation.single_case_runtime_state_validated`
- `runtime_state_validation.multi_case_merge_validated`
- `runtime_state_validation.multi_case_merge_validation_status`

## Recovery Relationship

The intended operational relationship is:

1. `run_manifest.json` defines what the run is supposed to cover.
2. `07_results/logs/<module>.log` records how a module actually ran.
3. `07_results/modules/<module>/done.json` records whether the module completed and which outputs should exist.
4. module-specific summary JSON and TSV outputs record the scientific payload.

For partial reruns:

1. `run_manifest.json` still defines the full intended benchmark scope.
2. `done.json` and summary JSON define the effective execution scope through `selected_case_ids`.
3. module TSV payloads should preserve non-selected case rows when case-aware output merge is active.

When these disagree, trust order should usually be:

1. log file for failure diagnosis
2. output files for actual produced payload
3. `done.json` for completion bookkeeping
4. run manifest for intended scope only
