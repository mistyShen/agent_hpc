# cpu_ai_drug_design

CPU-only AI-assisted drug design workflow and benchmark scaffold.

This repository contains the lightweight local control plane for HPC work:
scripts, metadata, small benchmark inputs, environment files, Slurm templates,
reports, and recovery documentation.
Server-side formal execution root is configured as:

- `/shared/shen/cpu_ai_drug_design`

Heavy dependencies, large datasets, machine-local environments, scratch files,
and long-running job outputs are not committed. Keep those under `/shared` and
record the paths or manifests needed to recover them.

For a new machine, start with [RESTORE_FROM_GITHUB.md](RESTORE_FROM_GITHUB.md).

## Ultimate v2 Remote Evidence Loop

Ultimate is maintained under `ultimate/` and deployed to
`/shared/shen/2026/ultimate` for remote validation, production-style rehearsal,
storage audit, and delivery evidence checks. Heavy computation, public-data
validation, and real-data validation must run through Slurm; lightweight import,
pytest, manifest, and audit checks may run directly in the configured remote
environment.

Ultimate is not an automatic quoting or biological-claim engine. It is a
Codex-facing bioinformatics workbench: the user provides raw data paths and an
analysis request, then Codex uses Ultimate's module library, tool registry,
configuration templates, Slurm wrappers, reporting contract, and reproducibility
package to choose the appropriate workflow and execute it transparently.

The v2 evidence loop refreshes:

- `/shared/shen/2026/ultimate/reports/validation_index/validation_index.tsv`
- `/shared/shen/2026/ultimate/reports/validation_index/validation_summary.tsv`
- `/shared/shen/2026/ultimate/audits/production_latest/production_audit.tsv`
- `/shared/shen/2026/ultimate/audits/production_latest/module_maturity_table.tsv`
- `/shared/shen/2026/ultimate/audits/storage_latest/storage_audit_summary.json`
- `/shared/shen/2026/ultimate/reports/v2_status_report.md`

`validated_backend` is validation evidence only. It is not customer delivery.
`production_backend` requires a production approval JSON and an explicit
delivery gate. Demo, smoke, stub, and placeholder outputs must not set
`delivery_allowed=true`.

## scRNA MVP Validation

Run the public scRNA MVP validation through Slurm on the remote project root:

```bash
hpc-sbatch /shared/shen/2026/ultimate/slurm/scrna_mvp_validation.sbatch
```

The validation outputs are written under:

```text
/shared/shen/2026/ultimate/validation_runs/scrna_mvp_validation/{10x_mtx,h5ad}/
```

Key artifacts include:

- `objects/scrna_mvp.h5ad`
- `run_manifest.json`
- `raw_qc/raw_qc_manifest.json`
- `results/tables/pseudobulk_*.tsv`
- `results/tables/cell_type_annotation_placeholder.tsv`
- `reports/report.html`
- `reports/methods.md`

Passing this path may create `analysis_level=validated_backend`, which is
acceptable as public validation evidence. It is still not customer delivery.

## Production-Style Rehearsal Jobs

Create rehearsals with the prepared job entrypoint so the job directory owns the
config snapshot, production approval, Slurm wrapper, logs, deliverables, and
reproducible-code package:

```bash
ultimate prepare-job --config projects/demo_all/config/project.yaml --job-id demo_all_001 --root /shared/shen/2026/ultimate --run-mode interactive
hpc-sbatch /shared/shen/2026/ultimate/jobs/demo_all_001/config/run_ultimate.sbatch
```

Do not rely on passing extra
config arguments through the wrapper; use `ultimate prepare-job` first so
`jobs/<job_id>/config/run_ultimate.sbatch`,
`jobs/<job_id>/config/project.yaml`, and
`jobs/<job_id>/config/production_approval.json` stay in sync.
