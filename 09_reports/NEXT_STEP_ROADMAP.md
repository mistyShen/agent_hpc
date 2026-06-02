# Next Step Roadmap

## Frozen Now

The following parts are now frozen and should not be changed casually:

- the current BRD4 literature-backed evidence boundary
- `BRD4_BD1_LIT001`: `filter_keep_count = 1`, `shortlist_count = 1`, `JQ1 rank = 1`
- `BRD4_BD1_LIT002`: `filter_keep_count = 2`, `shortlist_count = 2`, `I-BET762 rank = 1`
- the current fixed `filtering v2.1` applicability boundary:
  - active only for `literature_backed + comparison` cases
  - `vina_affinity <= -6.5`
  - `vina_affinity >= best_vina - 2.0`
  - `rerank_rank <= 3`
- the current non-overclaim boundary
- the current manuscript-facing comparison wording

## Recommended Single Next Action

Use the frozen result-expression package to prepare the final manuscript-facing tables, figure panels, and figure legends without changing workflow logic or expanding the scientific claim boundary.

## Actions Not Recommended Yet

- adding a new benchmark case before the current expression layer is fully stabilized
- changing `filtering v2.1`
- changing benchmark schema, truth-table, or workflow interfaces
- changing scientific logic in docking, reranking, filtering, or clustering
- making broader benchmark or cross-target claims
- rerunning tasks only to refresh presentation files
