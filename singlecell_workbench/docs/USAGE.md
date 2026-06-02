# Single-cell Workbench Usage

This guide assumes the project lives at `/shared/shen/2026/singlecell_workbench` on the server.

## 1. Create or refresh the server environment

```bash
cd /shared/shen/2026/singlecell_workbench
bash 01_tools/setup_server_env.sh
```

The default environment prefix is:

```bash
/shared/shen/2026/singlecell_workbench/.conda/envs/scw-py311
```

To install into a different prefix:

```bash
bash 01_tools/setup_server_env.sh /shared/shen/2026/singlecell_workbench/.conda/envs/scw-alt
```

## 2. Activate the environment

```bash
source /share/home/nshen/miniconda3/etc/profile.d/conda.sh
conda activate /shared/shen/2026/singlecell_workbench/.conda/envs/scw-py311
```

## 3. Smoke-test the installation

```bash
python -m singlecell_workbench make-example --output-dir example_data/minimal_example
python -m singlecell_workbench run --config example_data/minimal_example/run_config.yaml
pytest -q tests
```

Expected key outputs from the minimal example:

- `example_data/minimal_example/runs/minimal_example/run_manifest.json`
- `example_data/minimal_example/runs/minimal_example/final/final_dataset.h5mu`
- `example_data/minimal_example/runs/minimal_example/reports/report.html`
- `example_data/minimal_example/runs/minimal_example/reports/methods.md`

## 4. Run schema validation on a new dataset

For a 10x MTX directory:

```bash
python -m singlecell_workbench validate-schema \
  --input-path /path/to/sample/filtered_feature_bc_matrix \
  --sample-id sample_001 \
  --condition baseline \
  --output-dir runs/schema_validation_sample_001
```

For a 10x H5 file:

```bash
python -m singlecell_workbench validate-schema \
  --input-path /path/to/sample/filtered_feature_bc_matrix.h5 \
  --sample-id sample_002 \
  --condition treated \
  --output-dir runs/schema_validation_sample_002
```

## 5. Fetch official pathway / TF priors

```bash
python -m singlecell_workbench fetch-priors \
  --output-dir resources/priors/human_academic \
  --organism human \
  --license academic
```

This writes:

- `resources/priors/human_academic/progeny.tsv`
- `resources/priors/human_academic/collectri.tsv`
- `resources/priors/human_academic/manifest.json`
- `resources/priors/human_academic/stats_config.yaml`

The generated `stats_config.yaml` is intended to be copied into a run config stored under `config/`.

## 6. Run a real analysis

1. Copy `config/default.yaml` to a run-specific file, for example `config/project_run.yaml`.
2. Replace the `samples` block with real 10x inputs.
3. Run `fetch-priors` first if you want real `decoupler` pathway / TF activity outputs.
4. Keep `output_dir` relative to the project root for portability.
5. Launch the workflow:

```bash
python -m singlecell_workbench run --config config/project_run.yaml
```

## 7. Config layout

The main config sections are:

- `samples`: input sample sheet with `sample_id`, `condition`, and `input_path`
- `schema`: schema repair behavior and required columns
- `qc`: QC settings, RNA modality selection, SOLO and SCAR toggles
- `annotation`: preferred annotation backend order and fallback labels
- `stats`: summary grouping columns and decoupler toggles
- `reports`: report title and output metadata

For a config file stored under `config/`, the default decoupler block points to:

- `../resources/priors/human_academic/progeny.tsv`
- `../resources/priors/human_academic/collectri.tsv`

## 8. Output layout

Each run writes under its configured `output_dir`:

- `ingest/`
  - normalized `h5ad` or `h5mu`
  - `schema_report.json`
- `qc/`
  - `per_cell_qc.csv`
  - `manifest.json`
- `annotation/`
  - `annotation_obs.csv`
  - `annotation_manifest.json`
- `stats/`
  - grouped summaries
  - `manifest.json`
- `reports/`
  - `report.html`
  - `methods.md`
  - `report_manifest.json`
- `final/`
  - final exported `h5ad` or `h5mu`
- `run_manifest.json`

## 9. Notes on optional modules

- `scanpy` is the preferred QC backend. If it is missing, the project can still fall back to a compatible QC implementation, but the server environment script is designed to install real `scanpy`.
- `scArches + scANVI` are the preferred annotation path.
- `CellTypist` is installed as the annotation fallback.
- `SOLO` is provided through `scvi-tools`.
- `SCAR` is installed separately via pip.
- `decoupler 2.1.x` is installed via pip in the server environment because the conda channel currently exposes an older `1.5.0` build that is not compatible with the current `numba` stack.
- The stats module accepts both `runner: mlm` and the legacy `runner: run_mlm` style; if no pathway or TF network is provided, the skip reason is recorded in `stats/manifest.json` and `run_manifest.json`.
- `fetch-priors` uses official decoupler wrappers for `PROGENy` and `CollecTRI`, and writes frozen TSV snapshots for rerunnable analyses.

## 10. Recommended handoff checklist

Before handing a run to someone else, confirm:

- `run_manifest.json` exists
- the final `h5ad` or `h5mu` exists
- the HTML report opens correctly
- `methods.md` reflects the actual dependency status
- any skipped optional module is visible in the manifest
