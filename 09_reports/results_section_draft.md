# Results Section Draft

## Results

### Real docking is integrated into a reproducible CPU-only workflow

The current `cpu_ai_drug_design` workflow has progressed beyond a dry scaffold because `classical_docking` now runs a real `vina_cpu` backend and writes real docking artifacts, including `vina_affinity_kcal_mol`, ligand `pdbqt`, and pose `pdbqt` outputs. Downstream modules remain lightweight, but `ai_reranking`, `filtering`, and `clustering_and_prioritization` now consume real docking-derived signals rather than purely scaffold placeholders. At the operational level, the workflow has been validated for single-case execution, heterogeneous-target two-case execution, heterogeneous-library two-case execution, three-active-case execution, demo-scale multi-case merge, and case-aware partial rerun isolation.

### The current literature-backed evidence boundary is narrow and fixed

The current literature-backed evidence boundary consists of two focused BRD4 BD1 recovery cases only: `BRD4_BD1_LIT001` and `BRD4_BD1_LIT002`. This boundary is intentionally narrow and should be interpreted as a fixed recovery snapshot rather than as a broad benchmark layer. In `BRD4_BD1_LIT001`, the known active `JQ1` is retained with `filter_keep_count = 1`, `shortlist_count = 1`, and best known active rank `1`. In `BRD4_BD1_LIT002`, the known active `I-BET762` is retained with `filter_keep_count = 2`, `shortlist_count = 2`, and best known active rank `1`. In both cases, `shortlist_contains_known_active = true`.

### The current literature-backed filtering branch is case-aware but narrowly scoped

For literature-backed comparison cases only, the frozen `filtering v2.1` branch is active when `case_type == literature_backed` and `run_purpose == comparison`. The current fixed rules are `vina_affinity <= -6.5`, `vina_affinity >= best_vina - 2.0`, and `rerank_rank <= 3`. This branch is compatible with both current BRD4 literature-backed cases and provides a case-aware focused recovery rule within the present evidence boundary. It should not yet be described as a broadly validated cross-target benchmark filter.

### Current interpretation boundary

Taken together, the current results support the claim that `cpu_ai_drug_design` is a reproducible CPU-only workflow with real docking integration and lightweight downstream consumers of real docking artifacts, and that it can recover the known active at shortlist rank `1` in two focused BRD4 BD1 literature-backed cases. The current results do not support claims of benchmark superiority, broad literature recovery performance, robust cross-target generalization, prospective hit quality, or larger-scale benchmark robustness.
