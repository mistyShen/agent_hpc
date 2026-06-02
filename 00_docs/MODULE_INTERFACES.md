# Module Interfaces

## Common Contract

All module paths are relative to project root unless `config.yaml` says otherwise.

All modules accept the same CLI contract:

- `--module`
- `--config`
- `--project-root`
- `--run-manifest`
- `--input-manifest`
- `--output`

All modules write:

- a module artifact at `07_results/modules/<module>/done.json`
- a module log at `07_results/logs/<module>.log`

All modules depend on the shared run manifest at `07_results/run_manifest.json`.

The canonical field and file expectations are defined in `00_docs/ARTIFACT_SCHEMAS.md`.

## Runtime Scope Contract

Current minimal runtime-scope control is environment-based:

- `WORKFLOW_CASE_ID=<case_id>`
- `WORKFLOW_CASE_IDS=<case_a>,<case_b>,...`

Current interpretation:

- if neither variable is set, the module processes all enabled cases in its input manifest
- if either variable is set, the module treats the selected case set as a partial rerun scope
- partial rerun state is written to `run_manifest.json`, `done.json`, and selected summary JSON fields

Current runtime-state fields expected across active modules:

- `execution_status`
- `runtime_seconds`
- `backend_mode`
- `skipped_cache`
- `skip_reason`
- `cache_hit_artifact`

## Backend Status Legend

- `real_backend`: the module uses a real executable backend or real upstream artifacts in the current workflow.
- `hybrid_lightweight`: the module consumes real upstream outputs but still uses lightweight CPU-only scoring or selection logic.
- `scaffold`: the module keeps placeholder or heuristic internals.

## target_preparation

- Interface status: `stable_v1`
- Backend status: `hybrid_lightweight`
- Input manifest: `04_metadata/targets.tsv`
- Primary outputs:
  - `07_results/modules/target_preparation/prepared_targets.tsv`
  - `07_results/modules/target_preparation/target_file_manifest.tsv`
  - `07_results/modules/target_preparation/target_summary.json`
  - `07_results/modules/target_preparation/target_preparation_report.md`
- Current behavior:
  - copies example target structures into the standardized results layout
  - computes lightweight structural metadata
  - writes docking box center and size fields
  - prepares receptor `pdbqt` path bookkeeping for downstream docking
- Downstream contract:
  - `classical_docking` reads `target_file_manifest.tsv`
  - `receptor_pdbqt_path`, `center_*`, and `size_*` are required by real `vina_cpu` runs
- Runtime note:
  - partial rerun is case-driven and internally mapped to the selected target set
  - TSV outputs are merged by `target_id` when partial rerun is active

## compound_library_preparation

- Interface status: `stable_v1`
- Backend status: `hybrid_lightweight`
- Input manifest: `04_metadata/compound_libraries.tsv`
- Primary outputs:
  - `07_results/modules/compound_library_preparation/prepared_library.tsv`
  - `07_results/modules/compound_library_preparation/library_summary.json`
  - `07_results/modules/compound_library_preparation/library_preparation_report.md`
- Current behavior:
  - reads a small SMILES library
  - normalizes SMILES by whitespace cleanup
  - removes exact duplicate standardized SMILES
  - computes lightweight approximate properties
- Downstream contract:
  - `classical_docking` reads `compound_id`, `library_id`, and `standardized_smiles`
- Runtime note:
  - partial rerun is case-driven and internally mapped to the selected library set
  - TSV outputs are merged by `library_id + compound_id` when partial rerun is active

## classical_docking

- Interface status: `stable_v1`
- Backend status: `real_backend`
- Input manifest: `04_metadata/benchmark_cases.tsv`
- Primary outputs:
  - `07_results/modules/classical_docking/docking_results.tsv`
  - `07_results/modules/classical_docking/docking_summary.json`
  - `07_results/modules/classical_docking/classical_docking_report.md`
- Current behavior:
  - joins benchmark cases, prepared library rows, and prepared target rows
  - preserves heuristic fallback behavior when the configured backend is unavailable
  - when `backend=vina_cpu` and the backend environment is available:
    - prepares or reuses receptor `pdbqt`
    - converts ligand SMILES to ligand `pdbqt`
    - runs AutoDock Vina in CPU-only mode
    - records affinity and pose artifacts
- Real-output fields now relied on downstream:
  - `vina_affinity_kcal_mol`
  - `ligand_pdbqt_path`
  - `pose_pdbqt_path`
  - `backend_name`
  - `engine_mode`
- Compatibility note:
  - the heuristic fallback remains part of the contract and must not be removed casually
- Runtime note:
  - partial rerun filters benchmark cases directly
  - `docking_results.tsv` is merged by `case_id + compound_id` when partial rerun is active

## ai_reranking

- Interface status: `stable_v1`
- Backend status: `hybrid_lightweight`
- Input manifest: `04_metadata/benchmark_cases.tsv`
- Primary outputs:
  - `07_results/modules/ai_reranking/reranked_candidates.tsv`
  - `07_results/modules/ai_reranking/reranking_summary.json`
  - `07_results/modules/ai_reranking/ai_reranking_report.md`
- Current behavior:
  - consumes `classical_docking/docking_results.tsv`
  - uses real docking fields when available, especially:
    - `vina_affinity_kcal_mol`
    - `ligand_pdbqt_path`
    - `pose_pdbqt_path`
  - applies lightweight CPU-only reranking features derived from:
    - docking affinity
    - ligand and pose artifact presence
    - simple `pdbqt` content signals such as atom counts and `TORSDOF`
    - small chemistry heuristics
- Output compatibility:
  - `reranked_candidates.tsv` column set remains unchanged
  - downstream modules are not required to understand the internal rerank logic
- Runtime note:
  - partial rerun filters benchmark cases directly
  - `reranked_candidates.tsv` is merged by `case_id + compound_id` when partial rerun is active

## filtering

- Interface status: `stable_v1`
- Backend status: `hybrid_lightweight`
- Input manifest: `04_metadata/benchmark_cases.tsv`
- Primary outputs:
  - `07_results/modules/filtering/filtered_candidates.tsv`
  - `07_results/modules/filtering/filter_summary.json`
  - `07_results/modules/filtering/filtering_report.md`
- Current behavior:
  - consumes benchmark case metadata, docking results, reranked candidates, and prepared library properties
  - distinguishes kept candidates from missing/anomalous exclusions and rule-based exclusions
  - applies lightweight CPU-only thresholds using real docking affinity, rerank score, and approximate physicochemical fields
- Compatibility note:
  - interface is stable enough for pipeline wiring and comparison-layer iteration
  - decision logic remains intentionally lightweight and not yet benchmark-grade
- Runtime note:
  - partial rerun filters benchmark cases directly
  - `filtered_candidates.tsv` is merged by `case_id + candidate_id` when partial rerun is active

## clustering_and_prioritization

- Interface status: `stable_v1`
- Backend status: `hybrid_lightweight`
- Input manifest: `04_metadata/benchmark_cases.tsv`
- Primary outputs:
  - `07_results/modules/clustering_and_prioritization/clustered_priorities.tsv`
  - `07_results/modules/clustering_and_prioritization/clustering_summary.json`
  - `07_results/modules/clustering_and_prioritization/clustering_report.md`
- Current behavior:
  - consumes filtered candidates, reranked candidates, and docking results
  - applies lightweight rule-based cluster labels
  - ranks by rerank score first and Vina affinity second
- Compatibility note:
  - shortlist generation now follows the real chain `docking -> reranking -> filtering -> clustering`
  - cluster logic is still lightweight and not yet chemistry-aware
- Runtime note:
  - partial rerun filters benchmark cases directly
  - `clustered_priorities.tsv` is merged by `case_id + compound_id` when partial rerun is active

## report_generation

- Interface status: `stable_v1`
- Backend status: `scaffold`
- Input manifest: `04_metadata/benchmark_cases.tsv`
- Primary outputs:
  - `09_reports/benchmark_summary.json`
  - `09_reports/benchmark_summary.md`
  - `09_reports/project_summary.json`
  - `09_reports/project_summary.md`
- Current behavior:
  - aggregates module summaries into project-level summary views
  - reports pipeline status, counts, and top-level artifact paths
- Compatibility note:
  - content is useful for operational reporting
  - wording still assumes a more scaffold-oriented project state in some places

## benchmark_evaluation

- Interface status: `stable_v1`
- Backend status: `scaffold`
- Input manifest: `04_metadata/benchmark_cases.tsv`
- Primary outputs:
  - `09_reports/benchmark_evaluation.json`
  - `09_reports/benchmark_evaluation.md`
- Current behavior:
  - computes lightweight aggregate completion metrics
  - does not yet calculate benchmark-grade enrichment, pose quality, or literature recovery metrics

## run_state_checker

- Interface status: `stable_v1`
- Backend status: `hybrid_lightweight`
- Input manifest: `04_metadata/benchmark_cases.tsv`
- Primary outputs:
  - `07_results/modules/run_state_checker/workflow_health_summary.json`
  - `07_results/modules/run_state_checker/workflow_health_report.md`
- Current behavior:
  - checks enabled module `done.json`, summary JSON, logs, and primary outputs
  - flags missing or empty artifacts
  - checks that real backend mode aligns with current config and upstream summaries
  - produces an operational workflow health view for recovery decisions
- Compatibility note:
  - this module does not change upstream outputs
  - it is for trust and recovery, not for scientific scoring

## Freeze Policy

The current module interfaces should be treated as frozen for the next iteration:

- keep file names stable
- keep top-level TSV column sets stable unless a change is strictly necessary
- prefer adding fields to summaries and documentation before changing existing outputs
- treat `classical_docking` and `ai_reranking` outputs as current reference interfaces for downstream work
