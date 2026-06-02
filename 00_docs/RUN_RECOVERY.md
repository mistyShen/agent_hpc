# Run Recovery

## Purpose

This document defines how to reason about run state and how to recover from partial failures without redesigning the workflow.

## State Layers

There are four operational state layers:

1. `07_results/run_manifest.json`
   - defines intended run scope and input manifests
2. `07_results/logs/<module>.log`
   - records the exact stdout and stderr from a module run
3. `07_results/modules/<module>/done.json`
   - marks module completion and validates expected outputs
4. module payload files such as TSV, JSON, and Markdown reports
   - contain the actual scientific or operational results

## How These Layers Relate

- `run_manifest.json` answers: what was supposed to run
- module log answers: what actually happened during execution
- `done.json` answers: did the module finish and write its declared outputs
- payload files answer: what data was actually produced

## Failure Diagnosis Order

When a module looks wrong, inspect in this order:

1. `07_results/logs/<module>.log`
2. `07_results/modules/<module>/done.json`
3. the module summary JSON
4. the module TSV payload
5. `07_results/run_manifest.json`

## Recovery Modes

### Mode 1: Module failed and `done.json` is missing

Interpretation:

- the module did not complete successfully

Action:

- read the module log
- fix the smallest upstream cause
- rerun only that module
- rerun downstream modules only if they consume its outputs

### Mode 2: `done.json` exists but payload is stale or inconsistent

Interpretation:

- the module may have been rerun partially
- the payload may not match the current code or current upstream state

Action:

- compare timestamps across log, `done.json`, and summary JSON
- if there is doubt, rerun that module explicitly

### Mode 3: Upstream changed, downstream still reflects old outputs

Interpretation:

- interface compatibility may still hold, but comparisons are no longer clean

Action:

- rerun the changed module
- rerun all downstream modules in dependency order

## Current Partial Rerun Strategy

Smallest safe rerun chain:

1. rerun the module you changed
2. rerun only downstream modules that consume its outputs

Current minimal case-level partial rerun entry:

- `WORKFLOW_CASE_ID=<case_id> python3 06_scripts/modules/<module>.py ...`
- `WORKFLOW_CASE_IDS=<case_a>,<case_b> python3 06_scripts/modules/<module>.py ...`

Current semantics:

- the module still reads the full input manifest
- execution scope is narrowed in-memory to the selected cases
- runtime-state fields in `done.json` and `run_manifest.json` must reflect the narrowed scope
- when the module supports case-aware output merge, non-selected case rows should be preserved in the main TSV payload

Current examples:

- after changing `classical_docking`:
  - rerun `classical_docking`
  - rerun `ai_reranking`
  - rerun `filtering`
  - rerun `clustering_and_prioritization`
  - rerun `report_generation`
  - rerun `benchmark_evaluation`

- after changing `ai_reranking` only:
  - rerun `ai_reranking`
  - rerun `filtering`
  - rerun `clustering_and_prioritization` if it starts consuming rerank outputs later
  - rerun `report_generation`
  - rerun `benchmark_evaluation`

## Lightweight State Checks

Recommended checks before claiming a rerun is valid:

- `run_manifest.json` exists
- target module log exists and ends without a Python traceback
- target module `done.json` exists
- target module summary JSON exists
- expected primary TSV exists and is non-empty
- backend mode in summary JSON matches expectation for that run
- if partial rerun was requested, `selected_case_ids` matches the requested scope
- if execution was skipped, `skip_reason` is present
- if cached artifacts were reused, `cache_hit_artifact` is true

## Current Weak Points

- `run_manifest.mode` still says `scaffold_only` even though some modules now use real backends
- `done.json` does not yet store code version or input file hashes
- downstream modules still vary in how much real upstream state they consume
- larger-scale multi-case benchmark behavior is still not empirically validated

## Current Empirical Validation Boundary

Validated on `2026-04-14`:

- single-case runtime-state behavior
- demo-scale dual-case benchmark with `DEMO_CASE_001` and `DEMO_CASE_002`
- heterogeneous-target two-case validation
- heterogeneous-library two-case validation
- three-active-case validation with `DEMO_CASE_003`
- both cases active in the same run manifest
- all three active cases persisted in the same run manifest
- case-level `execution_state` persisted for both cases
- case-level `execution_state` persisted across all three cases
- partial rerun scoped to `DEMO_CASE_002` preserved untouched `case`, `target`, and `library` rows in:
  - `prepared_targets.tsv`
  - `target_file_manifest.tsv`
  - `prepared_library.tsv`
  - `docking_results.tsv`
  - `reranked_candidates.tsv`
  - `filtered_candidates.tsv`
  - `clustered_priorities.tsv`
- partial rerun scoped to `DEMO_CASE_003` preserved untouched rows for:
  - `DEMO_CASE_001`
  - `DEMO_CASE_002`
  - `DEMO_TARGET_002`
  - `DEMO_LIB_001`

Still not validated:

- article-grade claims about general multi-case recovery behavior
- larger-scale mixed target and mixed library benchmarks

## Recommended Next Small Step

Without changing scientific logic, formalize and verify:

- `selected_case_ids`
- `skip_reason`
- `cache_hit_artifact`
- case-aware output merge behavior on larger multi-case benchmarks beyond three active cases

## Module Recovery Matrix

### `target_preparation`

Success:

- `prepared_targets.tsv` exists and has rows
- `target_file_manifest.tsv` exists and has rows
- `target_summary.json` exists
- `done.json` validation is all true

Pseudo-success:

- `done.json` exists but `target_file_manifest.tsv` is missing or empty
- `receptor_pdbqt_path` fields exist in the manifest but point to missing files

Local rerun:

- rerun `target_preparation`
- then rerun `classical_docking` and all downstream modules

Partial rerun:

- use `WORKFLOW_CASE_ID` or `WORKFLOW_CASE_IDS`
- selected cases are mapped to target IDs internally
- verify `selected_case_ids` in `done.json`
- verify preserved non-selected `target_id` rows if multi-case output merge is being relied on

### `compound_library_preparation`

Success:

- `prepared_library.tsv` exists and has rows
- `library_summary.json` exists
- `done.json` validation is all true

Pseudo-success:

- `done.json` exists but `prepared_library.tsv` is empty
- `standardized_smiles` is missing or blank for one or more rows

Local rerun:

- rerun `compound_library_preparation`
- then rerun `classical_docking` and all downstream modules

Partial rerun:

- use `WORKFLOW_CASE_ID` or `WORKFLOW_CASE_IDS`
- selected cases are mapped to library IDs internally
- verify `selected_case_ids` in `done.json`
- verify preserved non-selected library rows if multi-case output merge is being relied on

### `classical_docking`

Success:

- `docking_results.tsv` exists and has rows
- `docking_summary.json` exists
- when config requests `vina_cpu`, summary `requested_backend` and `engine_mode` both equal `vina_cpu`
- real rows contain non-empty `ligand_pdbqt_path`, `pose_pdbqt_path`, and `vina_affinity_kcal_mol`

Pseudo-success:

- `done.json` exists but summary `engine_mode` falls back unexpectedly
- `docking_results.tsv` exists but real-backend fields are blank
- summary and `done.json` disagree on backend mode

Local rerun:

- rerun `classical_docking`
- then rerun `ai_reranking`, `filtering`, `clustering_and_prioritization`, `report_generation`, `benchmark_evaluation`, and `run_state_checker`

Partial rerun:

- use `WORKFLOW_CASE_ID` or `WORKFLOW_CASE_IDS`
- verify `execution_state.cases.<case_id>.classical_docking`
- if `execution_status=skipped_cache`, expect `skip_reason` and `cache_hit_artifact`
- if multi-case benchmark is active, verify non-selected rows remain in `docking_results.tsv`

### `ai_reranking`

Success:

- `reranked_candidates.tsv` exists and has rows
- `reranking_summary.json` exists
- `rerank_model` is present
- when upstream docking is real, `real_docking_rows_consumed` is greater than zero

Pseudo-success:

- `done.json` exists but `reranked_candidates.tsv` is empty
- summary says docking engine mode that does not match upstream docking summary
- reranking completed but still reflects stale scaffold-only assumptions

Local rerun:

- rerun `ai_reranking`
- then rerun `filtering`, `clustering_and_prioritization`, `report_generation`, `benchmark_evaluation`, and `run_state_checker`

Partial rerun:

- use `WORKFLOW_CASE_ID` or `WORKFLOW_CASE_IDS`
- verify `selected_case_ids` in `done.json`
- if multi-case benchmark is active, verify non-selected rows remain in `reranked_candidates.tsv`

### `filtering`

Success:

- `filtered_candidates.tsv` exists and has rows
- `filter_summary.json` exists
- `filtering_report.md` exists
- summary `decision_counts` is present and coherent with the TSV

Pseudo-success:

- `done.json` exists but candidate table is empty
- summary candidate count does not match the TSV row count
- all candidates are excluded because upstream real fields are missing or stale

Local rerun:

- rerun `filtering`
- then rerun `report_generation`, `benchmark_evaluation`, and `run_state_checker`

Partial rerun:

- use `WORKFLOW_CASE_ID` or `WORKFLOW_CASE_IDS`
- verify `selected_case_ids` in `done.json`
- if multi-case benchmark is active, verify non-selected rows remain in `filtered_candidates.tsv`

### `clustering_and_prioritization`

Success:

- `clustered_priorities.tsv` exists and has rows
- `clustering_summary.json` exists
- `clustering_report.md` exists

Pseudo-success:

- `done.json` exists but clustered TSV is empty
- summary cluster counts disagree with the TSV

Local rerun:

- rerun `clustering_and_prioritization`
- then rerun `report_generation` and `run_state_checker`

Partial rerun:

- use `WORKFLOW_CASE_ID` or `WORKFLOW_CASE_IDS`
- verify `selected_case_ids` in `done.json`
- if multi-case benchmark is active, verify non-selected rows remain in `clustered_priorities.tsv`

### `report_generation`

Success:

- `09_reports/benchmark_summary.json` exists
- `09_reports/project_summary.json` exists
- markdown reports exist and are non-empty

Pseudo-success:

- reports exist but still contain stale scaffold-only backend wording after upstream real-backend changes
- report counts do not match current module summaries

Local rerun:

- rerun `report_generation`
- then rerun `benchmark_evaluation` and `run_state_checker`

### `benchmark_evaluation`

Success:

- `09_reports/benchmark_evaluation.json` exists
- `09_reports/benchmark_evaluation.md` exists
- `done.json` validation is all true

Pseudo-success:

- evaluation files exist but reflect stale counts from older filter or report outputs
- evaluation status claims completeness while upstream summaries are missing

Local rerun:

- rerun `benchmark_evaluation`
- then rerun `run_state_checker`

### `run_state_checker`

Success:

- `workflow_health_summary.json` exists
- `workflow_health_report.md` exists
- summary lists all enabled upstream modules
- real backend checks match current config and upstream summaries

Pseudo-success:

- checker ran before all upstream modules finished
- checker summary exists but omits enabled modules
- checker passes while upstream outputs were not actually refreshed after a code change

Local rerun:

- rerun `run_state_checker` after all intended upstream reruns complete
