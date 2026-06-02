# Enhancement Line Diagnostic Checklist

- Generated at: `2026-04-16T06:31:46.754399+00:00`
- Baseline case: `BRD4_BD1_LIT002`
- Enhancement case: `BRD4_BD1_LIT002_V3EXP`

## Headline

- Baseline active-best-background gap: `0.81`
- Enhancement active-best-background gap: `6.146`
- Enhancement shortlist count: `1`
- Enhancement shortlist ids: `I-BET762`
- Current best background: `BG_BIPHENYL`

## Best Background Diagnostic

- `compound_id = BG_BIPHENYL`
- `docking_core = -6.8`
- `physchem_penalty = 4.046`
- `physchem_flags = simple_aromatic_background, polyaryl_hydrophobe_background`
- `physchem_snapshot = {"aromatic_atom_count": 12, "aromatic_fraction": 1.0, "hetero_atom_count": 0, "molecular_weight_estimate": 144.132, "ring_index_count": 2}`

## Consistency Checks

- `active_margin_matches_tracker = True`
- `shortlist_count_matches_tracker = True`
- `known_active_shortlisted_matches_tracker = True`

## Quality Gates

- `known_active_remains_rank_1 = True`
- `known_active_still_shortlisted = True`
- `active_margin_improved = True`
- `shortlist_compressed = True`
- `best_background_explained = True`
- `diagnostic_outputs_consistent = True`

## Attention Items

- none

## Recommendation

- Continue enhancement-line tuning; current outputs are aligned and explanatory.
