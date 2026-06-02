# Module Status Table Draft

| Module | Backend class | Runnable | Current role | Publication readiness |
| --- | --- | --- | --- | --- |
| `target_preparation` | hybrid_lightweight | yes | prepares target manifests and docking box metadata | partial |
| `compound_library_preparation` | hybrid_lightweight | yes | prepares standardized SMILES library inputs | partial |
| `classical_docking` | real_backend | yes | produces real CPU-only Vina docking outputs | strongest current module |
| `ai_reranking` | hybrid_lightweight | yes | consumes real docking artifacts for lightweight reranking | partial |
| `filtering` | scaffold | yes | preserves pipeline stage boundary and candidate table shape | low |
| `clustering_and_prioritization` | scaffold | yes | preserves shortlist and cluster output shape | low |
| `report_generation` | scaffold | yes | aggregates module summaries into top-level reports | low |
| `benchmark_evaluation` | scaffold | yes | computes lightweight completion metrics | low |

## Reading Guide

- `real_backend` means a real executable backend or real scientific artifact is already in use
- `hybrid_lightweight` means the module consumes real upstream state but still uses lightweight internal logic
- `scaffold` means the interface is real enough for workflow wiring, but the scientific method is still placeholder-level

## Current Recommendation

The next comparison-focused work should build outward from `classical_docking` and `ai_reranking`, not by adding new modules, but by upgrading benchmark metadata, recovery discipline, filtering policy, clustering policy, and evaluation metrics.
