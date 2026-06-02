# Claim Consistency Check

Scope of review:

- `00_docs/REAL_BACKEND_STATUS.md`
- `09_reports/manuscript_draft.md`
- `09_reports/workflow_summary_draft.md`
- `09_reports/benchmark_comparison.md`
- `09_reports/benchmark_summary.md`
- `09_reports/FREEZE_SUMMARY.md`
- `09_reports/benchmark_result_table_draft.md`
- `09_reports/benchmark_result_table_draft.json`

Review basis:

- frozen documents only
- no new computation
- no new run outputs

## Overall Verdict

Claim consistency: `pass`

The reviewed documents are consistent on the current frozen literature-backed evidence boundary, the fixed `filtering v2.1` applicability boundary, the current validated scope, and the current non-overclaim boundary.

## 1. LIT001 / LIT002 Key Numbers

Consistent across reviewed frozen documents:

- `BRD4_BD1_LIT001`
  - `filter_keep_count = 1`
  - `shortlist_count = 1`
  - known active `JQ1`
  - `best_known_active_rank = 1`
- `BRD4_BD1_LIT002`
  - `filter_keep_count = 2`
  - `shortlist_count = 2`
  - known active `I-BET762`
  - `best_known_active_rank = 1`

No contradictory frozen values were found in the reviewed files.

## 2. Filtering v2.1 Rules And Applicability

Consistent across reviewed frozen documents:

- active only when `case_type == literature_backed`
- active only when `run_purpose == comparison`
- current fixed rules:
  - `vina_affinity <= -6.5`
  - `vina_affinity >= best_vina - 2.0`
  - `rerank_rank <= 3`

No reviewed file expands the applicability boundary beyond the current frozen scope.

## 3. Validated Scope

Consistent reviewed interpretation:

- workflow is runnable end to end under a CPU-only constraint
- `classical_docking` runs real `vina_cpu`
- lightweight downstream consumers operate on real docking artifacts
- single-case, heterogeneous two-case, and three-active-case execution are validated at demo scale
- partial rerun isolation is validated at demo scale
- literature-backed recovery evidence is fixed on two BRD4 BD1 cases only

No reviewed file converts the current scope into a benchmark-grade claim.

## 4. Non-Overclaim Boundary

Consistent reviewed exclusions:

- no benchmark superiority claim
- no broad literature recovery claim
- no robust cross-target generalization claim
- no prospective hit-quality claim
- no larger-scale benchmark robustness claim

## 5. Remaining Caution

The reviewed frozen documents are internally consistent, but they intentionally describe a narrow evidence boundary. New writing should continue to preserve this narrow boundary unless new evidence is added and separately frozen.
