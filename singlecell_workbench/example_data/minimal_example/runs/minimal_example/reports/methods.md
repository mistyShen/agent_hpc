# Single-cell Workbench Minimal Example

Generated at 2026-04-16T16:33:35.109534+00:00.

## Overview
- Processed 12 cells and 6 features using MuData.
- The pipeline retained the canonical single-cell object in h5ad or h5mu form depending on detected modalities.

## Schema
- Schema reported no explicit decisions.

## QC
- Qc decisions: rna_modality=Gene Expression.
- QC uses scanpy.pp.calculate_qc_metrics and records optional SOLO / SCAR steps when they are available.

## Annotation
- Annotation reported no explicit decisions.
- Annotation prefers scArches + scANVI and falls back to CellTypist when the preferred stack is unavailable.

## Statistics
- Stats reported no explicit decisions.
- Statistics aggregate sample x cell_type x condition summaries and can attach decoupler pathway / TF activity outputs.

## Dependency Skips
- No dependency skips were recorded.

## Artifacts
- manifest_path: /Users/a1234/Documents/coding/projects/agent_hpc/singlecell_workbench/example_data/minimal_example/runs/minimal_example/stats/manifest.json
