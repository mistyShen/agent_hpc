# Manuscript Results Package

This file is a layout-oriented manuscript results package assembled only from the current frozen expression-layer documents:

- `09_reports/benchmark_result_table_final.md`
- `09_reports/figure_caption_draft.md`
- `09_reports/results_section_draft.md`
- `09_reports/claim_consistency_check.md`

It does not introduce any new computation, claim, or evidence boundary.

## Results Text

### Real docking is integrated into a reproducible CPU-only workflow

The current `cpu_ai_drug_design` workflow has progressed beyond a dry scaffold because `classical_docking` now runs a real `vina_cpu` backend and writes real docking artifacts, including `vina_affinity_kcal_mol`, ligand `pdbqt`, and pose `pdbqt` outputs (Figure 1). Downstream modules remain lightweight, but `ai_reranking`, `filtering`, and `clustering_and_prioritization` now consume real docking-derived signals rather than purely scaffold placeholders. At the operational level, the workflow has been validated for single-case execution, heterogeneous-target two-case execution, heterogeneous-library two-case execution, three-active-case execution, demo-scale multi-case merge, and case-aware partial rerun isolation (Figure 1).

### The current literature-backed evidence boundary is narrow and fixed

The current literature-backed evidence boundary consists of two focused BRD4 BD1 recovery cases only: `BRD4_BD1_LIT001` and `BRD4_BD1_LIT002` (Table 1). In `BRD4_BD1_LIT001`, the known active `JQ1` is retained with `filter_keep_count = 1`, `shortlist_count = 1`, and best known active rank `1`. In `BRD4_BD1_LIT002`, the known active `I-BET762` is retained with `filter_keep_count = 2`, `shortlist_count = 2`, and best known active rank `1`. In both cases, `shortlist_contains_known_active = true` (Table 1).

### The current literature-backed filtering branch is case-aware but narrowly scoped

For literature-backed comparison cases only, the frozen `filtering v2.1` branch is active when `case_type == literature_backed` and `run_purpose == comparison`. The current fixed rules are `vina_affinity <= -6.5`, `vina_affinity >= best_vina - 2.0`, and `rerank_rank <= 3` (Figure 1; Supplementary Boundary Note). This branch is compatible with both current BRD4 literature-backed cases and provides a case-aware focused recovery rule within the present evidence boundary.

### Current interpretation boundary

Taken together, the current results support the claim that `cpu_ai_drug_design` is a reproducible CPU-only workflow with real docking integration and lightweight downstream consumers of real docking artifacts, and that it can recover the known active at shortlist rank `1` in two focused BRD4 BD1 literature-backed cases (Table 1; Figure 1). The current results do not support claims of benchmark superiority, broad literature recovery performance, robust cross-target generalization, prospective hit quality, or larger-scale benchmark robustness (Supplementary Boundary Note).

## Table 1. Fixed BRD4 BD1 Literature-Backed Recovery Table

Table 1 should be the main manuscript comparison table for the current fixed literature-backed evidence boundary.

| Case | Target | Library | Known Active | Filter Keep Count | Shortlist Count | Top 1 | Top 2 | Shortlist Contains Known Active | Best Known Active Rank |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `BRD4_BD1_LIT001` | `BRD4_BD1_4QZS` | `BRD4_LIT_FOCUSED_001` | `JQ1` | `1` | `1` | `JQ1` | `-` | `true` | `1` |
| `BRD4_BD1_LIT002` | `BRD4_BD1_4C66` | `BRD4_LIT_FOCUSED_002` | `I-BET762` | `2` | `2` | `I-BET762` | `BG_BIPHENYL` | `true` | `1` |

## Figure 1. Current validated scope and fixed literature-backed recovery boundary

Figure 1 should summarize the current validated workflow scope plus the narrow literature-backed recovery boundary.

`cpu_ai_drug_design` is a CPU-only modular workflow in which `classical_docking` now runs a real `vina_cpu` backend and downstream reranking, filtering, and shortlisting consume real docking-derived signals. The currently validated operational scope includes single-case execution, heterogeneous two-case execution, three-active-case execution, demo-scale multi-case merge, and case-aware partial rerun isolation. The current literature-backed evidence boundary is intentionally narrow and consists of two focused BRD4 BD1 recovery cases only. `BRD4_BD1_LIT001` retains `JQ1` with `filter_keep_count = 1`, `shortlist_count = 1`, and best known active rank `1`. `BRD4_BD1_LIT002` retains `I-BET762` with `filter_keep_count = 2`, `shortlist_count = 2`, and best known active rank `1`. For these literature-backed comparison cases, the frozen `filtering v2.1` branch applies only when `case_type == literature_backed` and `run_purpose == comparison`, using `vina_affinity <= -6.5`, `vina_affinity >= best_vina - 2.0`, and `rerank_rank <= 3`. These results support a minimal focused recovery claim for the two BRD4 cases and do not support broad cross-target benchmark claims.

## Citation Placement Guide

- `Table 1` should be cited in:
  - `The current literature-backed evidence boundary is narrow and fixed`
  - `Current interpretation boundary`
- `Figure 1` should be cited in:
  - `Real docking is integrated into a reproducible CPU-only workflow`
  - `The current literature-backed filtering branch is case-aware but narrowly scoped`
  - `Current interpretation boundary`

## Supplementary Boundary Note

The following content should remain outside the main result body or be placed in a supplementary boundary note:

- the explicit non-overclaim list:
  - no benchmark superiority claim
  - no broad literature recovery claim
  - no robust cross-target generalization claim
  - no prospective hit-quality claim
  - no larger-scale benchmark robustness claim
- the claim-consistency statement:
  - current frozen documents pass internal consistency review for:
    - `BRD4_BD1_LIT001` key numbers
    - `BRD4_BD1_LIT002` key numbers
    - `filtering v2.1` applicability and rule wording
    - current validated scope
    - current non-overclaim boundary

## Boundary Note Text

The current manuscript-facing results are intentionally restricted to a narrow evidence boundary. The workflow supports operational claims for CPU-only execution, real `vina_cpu` docking integration, lightweight downstream consumption of docking-derived signals, demo-scale multi-case validation, and focused literature-backed recovery in two BRD4 BD1 cases. These results should not be expanded into broad benchmark or cross-target claims without additional separately validated evidence.
