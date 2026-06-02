# Enhancement Expansion Readiness

- Generated at: `2026-04-28T11:49:42.953631+00:00`
- Scope: Planning/readiness only. This does not change enhancement tuning or frozen benchmark/manuscript claims.

## Current Validation Position

- Validation status: `bounded_multi_surface_readout_with_boundary_challenge`
- Material-on-panel cases: `BRD3_BD1_LIT002_V3EXP, BRD3_BD2_LIT002_V3EXP, BRD4_BD1_LIT002_V3EXP, BRD4_BD1_LIT003_V3EXP`
- Weak-on-panel cases: `BRD2_BD2_LIT001_V3EXP, BRD3_BD1_LIT001_V3EXP, BRD3_BD2_LIT001_V3EXP, BRD4_BD1_LIT001_V3EXP, BRDT_BD1_LIT001_V3EXP, PXR_LBD_LIT001_V3EXP`
- Failed shortlist-preservation cases: `BRD2_BD1_LIT002_V3EXP`
- Non-BRD4 enhancement-only cases: `BRD2_BD1_LIT002_V3EXP, BRD2_BD2_LIT001_V3EXP, BRD3_BD1_LIT001_V3EXP, BRD3_BD1_LIT002_V3EXP, BRD3_BD2_LIT001_V3EXP, BRD3_BD2_LIT002_V3EXP, BRDT_BD1_LIT001_V3EXP, PXR_LBD_LIT001_V3EXP`

## Existing Case Inventory

- Enabled literature-backed cases in metadata: `24`
- `BRD4_BD1_LIT001` -> target `BRD4_BD1_4QZS`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v2`
- `BRD4_BD1_LIT001_V3EXP` -> target `BRD4_BD1_4QZS`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v3`
- `BRD4_BD1_LIT002` -> target `BRD4_BD1_4C66`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v2`
- `BRD4_BD1_LIT002_V3EXP` -> target `BRD4_BD1_4C66`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v3`
- `BRD4_BD1_LIT003` -> target `BRD4_BD1_4QZS`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v2`
- `BRD4_BD1_LIT003_V3EXP` -> target `BRD4_BD1_4QZS`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v3`
- `BRD2_BD2_LIT001` -> target `BRD2_BD2_3ONI`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v2`
- `BRD2_BD2_LIT001_V3EXP` -> target `BRD2_BD2_3ONI`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v3`
- `BRDT_BD1_LIT001` -> target `BRDT_BD1_4FLP`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v2`
- `BRDT_BD1_LIT001_V3EXP` -> target `BRDT_BD1_4FLP`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v3`
- `PXR_LBD_LIT001` -> target `PXR_LBD_8F5Y`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v2`
- `PXR_LBD_LIT001_V3EXP` -> target `PXR_LBD_8F5Y`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v3`
- `BRD3_BD1_LIT001` -> target `BRD3_BD1_3S91`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v2`
- `BRD3_BD1_LIT001_V3EXP` -> target `BRD3_BD1_3S91`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v3`
- `BRD3_BD2_LIT001` -> target `BRD3_BD2_3S92`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v2`
- `BRD3_BD2_LIT001_V3EXP` -> target `BRD3_BD2_3S92`, library `BRD4_LIT_FOCUSED_001`, rerank `ai_rerank_v3`
- `BRD2_BD1_LIT002` -> target `BRD2_BD1_2YEK`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v2`
- `BRD2_BD1_LIT002_V3EXP` -> target `BRD2_BD1_2YEK`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v3`
- `BRD3_BD1_LIT002` -> target `BRD3_BD1_24OS`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v2`
- `BRD3_BD1_LIT002_V3EXP` -> target `BRD3_BD1_24OS`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v3`
- `BRDT_BD1_LIT002` -> target `BRDT_BD1_4FLP`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v2`
- `BRDT_BD1_LIT002_V3EXP` -> target `BRDT_BD1_4FLP`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v3`
- `BRD3_BD2_LIT002` -> target `BRD3_BD2_3S92`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v2`
- `BRD3_BD2_LIT002_V3EXP` -> target `BRD3_BD2_3S92`, library `BRD4_LIT_FOCUSED_002`, rerank `ai_rerank_v3`

## Expansion Readiness

- Additional non-frozen literature-backed case already present: `True`
- Expansion readiness: `interim_brd4_brd3_boundary_ready`
- Recommended next action: `formalize_interim_brd4_brd3_boundary_then_validate_non_brd3_surface`

## Constraints

- Do not move enhancement results into frozen manuscript or benchmark claims.
- Do not continue indefinite same-panel tuning when no new validation surface is available.
- Treat current v3 gains as bounded to the enhancement line and explicitly checked frozen cases only.
- If a new surface loses known-active shortlist/rank preservation, treat it as a boundary challenge before any further expansion.
