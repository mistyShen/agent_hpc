# singlecell_workbench

`singlecell_workbench` is a reproducible, testable scaffold for 10x single-cell data processing under `/shared/shen/2026/singlecell_workbench`.

It is built around a CLI-first workflow rather than notebooks or UI:

- ingest 10x `filtered_feature_bc_matrix.h5` and `matrix.mtx` directories
- normalize outputs to `h5ad` or `h5mu` depending on detected modalities
- validate `obs` / `var` / `layers` / `obsm` / `uns` schema and emit auto-fix suggestions
- run QC with `scanpy.pp.calculate_qc_metrics` plus optional SOLO and SCAR integration
- annotate with preferred `scArches + scANVI`, falling back to `CellTypist` when available
- summarize `sample x cell_type x condition` results and optionally attach `decoupler` activities
- generate an HTML report and methods draft for handoff

## Quickstart

Create a local environment:

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
```

Generate a runnable minimal example:

```bash
.venv/bin/scw make-example --output-dir example_data/minimal_example
```

Run the full workflow on the generated example:

```bash
.venv/bin/scw run --config example_data/minimal_example/run_config.yaml
```

Fetch official pathway / TF priors for real-data stats runs:

```bash
.venv/bin/scw fetch-priors --output-dir resources/priors/human_academic --organism human --license academic
```

For server-side setup and handoff instructions, see `docs/USAGE.md`.

## Project layout

- `src/singlecell_workbench/`: package source
- `config/default.yaml`: editable baseline config template
- `tests/`: unit and integration coverage
- `notebooks/`: example notebook for onboarding and validation
- `example_data/`: generated minimal example inputs and outputs

## Real-data expansion path

1. Start from the minimal example and confirm the base pipeline completes.
2. Replace the `samples` block in a config YAML with real 10x H5 or MTX inputs.
3. Install optional extras required by your analysis plan:
   - `annotation`: `scArches`, `scvi-tools`, `CellTypist`
   - `qc`: `scvi-tools`, `SCAR`
   - `stats`: `decoupler`
4. Re-run through the CLI and archive the generated `run_manifest.json`, report, and exported `h5ad` / `h5mu`.

## Notes

- The minimal example is designed to complete even when optional deep-learning dependencies are not installed.
- Optional modules record explicit skip reasons in their manifests so handoff remains transparent.
- The server environment installs `decoupler 2.1.x` via pip because the currently available conda build is too old for the active `numba` stack; the stats module supports both `mlm` and legacy `run_mlm` runner names.
- Official pathway / TF priors can be frozen locally with `scw fetch-priors`, which exports PROGENy and CollecTRI snapshots plus a config snippet for `config/`-based runs.
- A reproducible server environment definition is provided in `envs/environment.server.yml`, with installation scripted in `01_tools/setup_server_env.sh` and usage documented in `docs/USAGE.md`.
