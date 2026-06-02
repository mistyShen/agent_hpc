# Manuscript Draft

## Title

CPU-only modular drug-design workflow with real Vina docking, lightweight downstream ranking, and validated demo-scale multi-case recovery

## Abstract-Style Summary

We developed `cpu_ai_drug_design`, a CPU-only Snakemake workflow for target preparation, compound library preparation, classical docking, AI-style reranking, filtering, clustering, reporting, and benchmark evaluation. The system has progressed beyond a dry scaffold because `classical_docking` now runs a real `vina_cpu` backend and downstream modules consume those real docking artifacts. The current trust boundary is operational rather than benchmark-grade: the workflow has been validated for single-case execution, heterogeneous two-case execution, three-active-case execution, demo-scale multi-case merge, and case-aware partial rerun isolation. The current literature-backed evidence boundary now includes two BRD4 BD1 focused recovery cases, `BRD4_BD1_LIT001` and `BRD4_BD1_LIT002`. Under the frozen case-aware `filtering v2.1` branch, `BRD4_BD1_LIT001` retains `JQ1` with `filter_keep_count = 1`, `shortlist_count = 1`, and rank `1`, while `BRD4_BD1_LIT002` retains `I-BET762` with `filter_keep_count = 2`, `shortlist_count = 2`, and rank `1`. The current system is therefore credible as a reproducible CPU-only execution and recovery framework with minimal literature-backed recovery evidence, but not yet as a publication-grade scientific benchmark.

## 1. System Scope

`cpu_ai_drug_design` is organized as a modular Snakemake workflow with the following stages:

- target preparation
- compound library preparation
- classical docking
- AI reranking
- filtering
- clustering and prioritization
- benchmark evaluation
- report generation
- run-state checking

The design goal is strict CPU-only execution with consistent local and HPC layouts, relative-path-friendly project structure, and support for reruns, caching, and partial recovery.

## 2. Current Real Backend Coverage

The workflow is only partially real in the scientific sense, but several key surfaces are now backed by real artifacts rather than scaffolds.

### 2.1 Real backend module

- `classical_docking` runs a real `vina_cpu` backend.
- It writes real `vina_affinity_kcal_mol`, `ligand_pdbqt_path`, and `pose_pdbqt_path`.
- The earlier heuristic fallback remains available but is no longer the only viable path.

### 2.2 Lightweight downstream consumers of real artifacts

- `ai_reranking` consumes real docking outputs and produces a lightweight CPU-only reranking score.
- `filtering` consumes real docking values, reranking values, and basic physicochemical fields.
- for `literature_backed` comparison cases only, `filtering` now applies a frozen case-aware `v2.1` rule using:
  - an absolute docking threshold
  - a within-case docking window relative to the best Vina score
  - a within-case rerank cutoff by `rerank_rank`
- `clustering_and_prioritization` consumes the filtering keep set and orders candidates using `rerank_score` and `vina_affinity_kcal_mol`.

This means the main execution path is now:

`target_preparation -> compound_library_preparation -> classical_docking -> ai_reranking -> filtering -> clustering_and_prioritization`

## 3. Runtime Trust Boundary

The current system has been validated at the runtime and recovery layer for the following scenarios:

- single-case runtime-state behavior
- heterogeneous-target two-case execution
- heterogeneous-library two-case execution
- three-active-case execution
- demo-scale multi-case merge
- partial rerun isolation for untouched cases, targets, and libraries

The current validated interpretation is operational:

- the workflow can execute end to end
- case-level execution state is recorded consistently
- cache and skip behavior do not contaminate untouched outputs at demo scale
- partial rerun can update selected cases without rewriting unrelated case rows
- literature-backed focused recovery can be demonstrated on two BRD4 BD1 minimal cases

The following are still outside the validated boundary:

- larger-scale multi-case benchmark behavior
- cross-target literature-backed benchmark claims
- benchmark-grade scientific ranking claims

## 4. Benchmark Cases And Current Evidence Boundary

The active benchmark set now includes both demo/debug infrastructure cases and two minimal literature-backed focused BRD4 recovery cases.

Current active cases:

| Case | Target | Library | Type | Tier | Purpose | Metric |
| --- | --- | --- | --- | --- | --- | --- |
| `DEMO_CASE_001` | `DEMO_TARGET_001` | `DEMO_LIB_001` | `toy` | `bringup` | `debug` | `none` |
| `DEMO_CASE_002` | `DEMO_TARGET_002` | `DEMO_LIB_002` | `debug` | `smoke` | `debug` | `none` |
| `DEMO_CASE_003` | `DEMO_TARGET_001` | `DEMO_LIB_002` | `debug` | `smoke` | `debug` | `none` |
| `BRD4_BD1_LIT001` | `BRD4_BD1_4QZS` | `BRD4_LIT_FOCUSED_001` | `literature_backed` | `comparison` | `comparison` | `shortlist_contains_known_active` |
| `BRD4_BD1_LIT002` | `BRD4_BD1_4C66` | `BRD4_LIT_FOCUSED_002` | `literature_backed` | `comparison` | `comparison` | `shortlist_contains_known_active` |

These cases are sufficient for:

- backend bring-up
- multi-case state validation
- cache and partial rerun validation
- minimal literature-backed focused recovery evidence for BRD4 BD1
- report and comparison-layer development

They are not sufficient for:

- prospective hit discovery claims
- broad literature recovery claims across targets
- cross-target generalization claims
- benchmark superiority claims

## 5. Current Three-Case Comparison Snapshot

On the validated three-case demo run, each active case completed the same lightweight end-to-end path and produced the following summary:

| Case | Target | Library | Docking | Reranked | Filtered | Keep | Shortlist | Top 1 | Top 2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `DEMO_CASE_001` | `DEMO_TARGET_001` | `DEMO_LIB_001` | `4` | `4` | `4` | `2` | `2` | `DEMO_ETHANOL` | `DEMO_ACETIC_ACID` |
| `DEMO_CASE_002` | `DEMO_TARGET_002` | `DEMO_LIB_002` | `4` | `4` | `4` | `2` | `2` | `DEMO_ETHANOL` | `DEMO_ACETIC_ACID` |
| `DEMO_CASE_003` | `DEMO_TARGET_001` | `DEMO_LIB_002` | `4` | `4` | `4` | `2` | `2` | `DEMO_ETHANOL` | `DEMO_ACETIC_ACID` |

This comparison layer is suitable for:

- project milestone reporting
- workflow debugging and regression tracking
- manuscript planning

It is not yet suitable for:

- scientific benchmark claims
- ranking-quality claims beyond toy/debug evidence

## 6. Operational Strengths

The strongest current properties of the system are operational rather than scientific:

- reproducible CPU-only execution
- real docking integration without breaking downstream modules
- module-level runtime tracking
- cache-aware rerun behavior
- case-aware partial rerun support
- manifest-backed execution-state reporting
- validated multi-case merge at demo scale

## 7. Current Limitations

Several layers remain intentionally lightweight:

- benchmark coverage is still narrow even though two minimal literature-backed BRD4 cases are now fixed
- filtering remains lightweight rule-based filtering, although the literature-backed comparison branch is now frozen as `v2.1`
- clustering and prioritization remain lightweight rather than chemistry- or similarity-rich
- benchmark evaluation focuses on completion and comparison summaries rather than benchmark-grade metrics
- current comparison outputs are report-ready, but not yet enough for publication-grade scientific claims

## 8. Recommended Near-Term Upgrade Path

Recommended next steps, in order:

1. keep the current BRD4 literature-backed evidence boundary and manuscript/report wording frozen
2. add benchmark-grade evaluation metrics
3. expand cautiously beyond the two current BRD4 literature-backed cases
4. validate compatibility of the case-aware literature-backed filtering branch beyond the two BRD4 cases
5. validate larger-scale multi-case behavior
6. strengthen downstream scientific logic only after the benchmark layer is credible

## 9. Reusable Output Entry Points

The current best entry points for writing and reporting are:

- system narrative: `09_reports/workflow_summary_draft.md`
- manuscript/report structure: `09_reports/manuscript_report_outline.md`
- benchmark comparison table: `09_reports/benchmark_comparison.md`
- top-level operational summary: `09_reports/project_summary.md`
- backend trust boundary: `00_docs/REAL_BACKEND_STATUS.md`
- runtime/recovery boundary: `00_docs/RUN_RECOVERY.md`

## 10. Bottom-Line Statement

At the current stage, `cpu_ai_drug_design` should be described as a reproducible CPU-only drug-design workflow with real `vina_cpu` docking, lightweight downstream consumers of real docking artifacts, and a validated demo-scale recovery and multi-case execution layer. It should not yet be described as a benchmark-grade scientific comparison system.
