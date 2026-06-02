# Samplesheet Contract

`singlecell_workbench` currently treats `config.samples` as the runtime source of truth. The TSV template in `templates/samplesheet.template.tsv` is the contract format used for manual planning, preflight review, and pipeline snapshots.

## Required

| Field | Meaning |
| --- | --- |
| `sample_id` | Stable unique sample identifier. Must be unique within one run. |
| `input_path` | Path to a 10x `filtered_feature_bc_matrix.h5` file or a matrix directory containing `matrix.mtx` plus feature/barcode tables. |
| `condition` | Experimental condition used by downstream grouping and contrast logic. |
| `organism` | Organism for the sample, for example `human` or `mouse`. |
| `reference_build` | Reference build associated with the feature space, for example `GRCh38` or `GRCm39`. |
| `gene_id_type` | Gene identifier namespace intended for alignment with references and priors, for example `gene_symbol` or `ensembl_gene_id`. |

## Recommended

| Field | Meaning |
| --- | --- |
| `donor` | Donor or subject identifier used to preserve repeated-measure structure. |
| `batch` | Technical batch label for sequencing run, lane, library prep, or other processing batch. |
| `modality` | Declared modality such as `rna`, `antibody`, or `multimodal`. Used as a preflight sanity check against observed feature types. |
| `library_type` | Assay family or library strategy, for example `10x_3prime_v3` or `cite_seq`. |
| `chemistry` | Chemistry string used for troubleshooting and reference compatibility checks. |

## Optional

| Field | Meaning |
| --- | --- |
| `tissue` | Tissue or compartment label used to sanity-check annotation references when available. |

## Current preflight checks

The `preflight` / `validate-inputs` command validates:

- `sample_id` uniqueness
- input path existence and readability
- 10x input kind inference
- declared `modality` versus observed feature types
- missing or conflicting `organism`, `reference_build`, and `gene_id_type`
- per-sample feature type distribution
- sample gene overlap with pathway / TF priors
- annotation reference consistency for species, tissue, modality, and gene namespace
- Gate 1 required field completeness

## Notes

- The pipeline writes a resolved `samplesheet_snapshot.tsv` into each run directory using this exact column order.
- If a curated label already exists in `obs.cell_type`, annotation now preserves it in `obs.cell_type_curated` and writes model output to `obs.cell_type_pred`.
