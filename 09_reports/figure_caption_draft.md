# Figure Caption Draft

## Figure 1. Current validated scope and fixed literature-backed recovery boundary

`cpu_ai_drug_design` is a CPU-only modular workflow in which `classical_docking` now runs a real `vina_cpu` backend and downstream reranking, filtering, and shortlisting consume real docking-derived signals. The currently validated operational scope includes single-case execution, heterogeneous two-case execution, three-active-case execution, demo-scale multi-case merge, and case-aware partial rerun isolation. The current literature-backed evidence boundary is intentionally narrow and consists of two focused BRD4 BD1 recovery cases only. `BRD4_BD1_LIT001` retains `JQ1` with `filter_keep_count = 1`, `shortlist_count = 1`, and best known active rank `1`. `BRD4_BD1_LIT002` retains `I-BET762` with `filter_keep_count = 2`, `shortlist_count = 2`, and best known active rank `1`. For these literature-backed comparison cases, the frozen `filtering v2.1` branch applies only when `case_type == literature_backed` and `run_purpose == comparison`, using `vina_affinity <= -6.5`, `vina_affinity >= best_vina - 2.0`, and `rerank_rank <= 3`. These results support a minimal focused recovery claim for the two BRD4 cases and do not support broad cross-target benchmark claims.

## Table 1. Fixed literature-backed comparison table

Comparison of the two frozen BRD4 BD1 literature-backed focused recovery cases under the current manuscript-facing evidence boundary. Both cases retain the known active in the final shortlist at rank `1`, with `JQ1` ranked first in `BRD4_BD1_LIT001` and `I-BET762` ranked first in `BRD4_BD1_LIT002`. This table should be interpreted as a narrow fixed recovery snapshot rather than a benchmark-grade comparison across targets.

## Supplementary Note. Current non-overclaim boundary

The current frozen results support operational workflow claims and narrow focused recovery claims only. They do not yet support benchmark superiority, broad literature recovery performance, robust cross-target generalization, prospective hit-quality claims, or larger-scale benchmark robustness.
