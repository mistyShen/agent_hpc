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
