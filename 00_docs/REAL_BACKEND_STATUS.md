# Real Backend Status

Snapshot date:

- `2026-04-15`

Scope:

- current local project state under `~/Documents/coding/projects/agent_hpc`
- current formal server project root under `/shared/shen/cpu_ai_drug_design`

## Module Status Table

| Module | Current status | Backend class | Real output consumed or produced | Notes |
| --- | --- | --- | --- | --- |
| `target_preparation` | runnable | hybrid_lightweight | produces target manifest and receptor `pdbqt` paths | target structure prep is still lightweight but sufficient for current docking wiring |
| `compound_library_preparation` | runnable | hybrid_lightweight | produces standardized SMILES library | no heavy chemistry standardization yet |
| `classical_docking` | runnable | real_backend | produces real `vina_affinity_kcal_mol`, ligand `pdbqt`, pose `pdbqt` | heuristic fallback preserved |
| `ai_reranking` | runnable | hybrid_lightweight | consumes real Vina affinity and docking artifacts | lightweight CPU-only rerank v2 |
| `filtering` | runnable | hybrid_lightweight | consumes real docking and reranking outputs for lightweight rule-based filtering | literature-backed comparison cases now use a case-aware `v2.1` policy; still not benchmark-grade chemistry filtering |
| `clustering_and_prioritization` | runnable | hybrid_lightweight | consumes filtering keep set plus rerank score and Vina affinity for shortlist ordering | ranking policy is still lightweight and provisional |
| `report_generation` | runnable | scaffold | aggregates module summaries | wording should be updated over time as real backends expand |
| `benchmark_evaluation` | runnable | scaffold | computes lightweight completion metrics only | not yet publication-grade benchmarking |
| `run_state_checker` | runnable | hybrid_lightweight | checks module state against real backend expectations | operational trust layer, not scientific scoring |

## What Is Actually Real Today

Confirmed real backend surfaces:

- `classical_docking` with `backend=vina_cpu`
- real `ligand_pdbqt_path`
- real `pose_pdbqt_path`
- real `vina_affinity_kcal_mol`
- `ai_reranking` consuming those real docking artifacts
- `filtering` consuming real `vina_affinity_kcal_mol` and `rerank_score` with a literature-backed case-aware branch

Not yet real in the scientific-comparison sense:

- benchmark case diversity
- literature-backed benchmark labels
- chemistry-aware filtering
- similarity-driven clustering
- benchmark-grade evaluation metrics

Current fixed literature-backed evidence boundary:

- `BRD4_BD1_LIT001`
  - known active `JQ1`
  - `filter_keep_count = 1`
  - `shortlist_count = 1`
  - `shortlist_contains_known_active = true`
  - `best_known_active_rank = 1`
- `BRD4_BD1_LIT002`
  - known active `I-BET762`
  - `filter_keep_count = 2`
  - `shortlist_count = 2`
  - `shortlist_contains_known_active = true`
  - `best_known_active_rank = 1`

Interpretation:

- the current literature-backed layer now supports two minimal focused recovery cases
- `filtering v2.1` is enabled only when:
  - `case_type == literature_backed`
  - `run_purpose == comparison`
- the active filter branch is no longer a single absolute-threshold policy
- the current fixed `v2.1` policy for literature-backed comparison cases is:
  - `vina_affinity <= -6.5`
  - `vina_affinity >= best_vina - 2.0`
  - `rerank_rank <= 3`
- this policy is compatible with both current BRD4 literature-backed cases
- this is a narrow fixed evidence boundary, not a broad cross-target benchmark claim

## Current Benchmark Case Classification

Current active cases:

- `DEMO_CASE_001`
  - type: `toy`
  - operational role: `debug`
  - scientific role: `not literature-backed`
  - current value: validates wiring, artifact generation, and partial ranking behavior
- `DEMO_CASE_002`
  - type: `debug`
  - operational role: `debug`
  - scientific role: `not literature-backed`
  - current value: validates heterogeneous-target and heterogeneous-library two-case behavior
- `DEMO_CASE_003`
  - type: `debug`
  - operational role: `debug`
  - scientific role: `not literature-backed`
  - current value: validates three-active-case merge and partial rerun isolation in a mixed target/library setup

Interpretation:

- these three cases are sufficient for backend bring-up, pipeline recovery tests, and demo-scale multi-case state validation
- they are not sufficient for meaningful model comparison or paper claims

## Multi-Case Validation Status

Demo-scale multi-case validation completed on `2026-04-14`:

- single-case runtime-state behavior is validated
- a heterogeneous-target two-case run is validated
- a heterogeneous-library two-case run is validated
- a three-active-case run is validated
- `run_manifest.execution_state.cases` recorded both `DEMO_CASE_001` and `DEMO_CASE_002`
- `run_manifest.execution_state.cases` now also records `DEMO_CASE_003`
- `classical_docking`, `ai_reranking`, `filtering`, and `clustering_and_prioritization` preserved per-case rows without cross-case mixing
- a partial rerun scoped to `DEMO_CASE_002` did not alter untouched `case`, `target`, or `library` rows in the main TSV outputs
- a partial rerun scoped to `DEMO_CASE_003` did not alter untouched `DEMO_CASE_001`, `DEMO_CASE_002`, `DEMO_TARGET_002`, or `DEMO_LIB_001` rows

Current boundary:

- multi-case merge is validated at demo scale for two-case and three-case runs, including heterogeneous target and heterogeneous library variants
- partial rerun isolation is validated at demo scale for untouched cases, targets, and libraries
- larger-scale benchmark behavior is still not empirically validated

## Current Trust Boundary

What can be claimed now:

- the workflow runs end to end
- `classical_docking` can use a real CPU-only backend
- `ai_reranking` can consume real docking artifacts without breaking downstream modules
- local and server layouts are consistent enough for module-level reruns
- demo-scale multi-case merge and case-level execution state have been empirically validated on the server
- two-case heterogeneous target and heterogeneous library validation has been completed on the server
- three-active-case validation has been completed on the server
- partial rerun isolation has been validated for untouched cases, targets, and libraries

What should not yet be claimed:

- benchmark superiority
- prospective hit quality
- literature recovery performance
- robust cross-target generalization
- larger-scale benchmark behavior across many heterogeneous targets and libraries

## Immediate Upgrade Priority

Recommended next layers, in order:

1. keep the current BRD4 literature-backed evidence boundary frozen in docs and handoff summaries
2. strengthen benchmark evaluation metrics beyond toy/debug completion counts
3. expand evidence cautiously beyond the two current BRD4 literature-backed cases
4. validate larger-scale multi-case behavior across more heterogeneous targets and libraries
