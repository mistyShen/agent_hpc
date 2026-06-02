# Project Structure

## Root Layout

- `00_docs`: design notes, benchmark definition, operating conventions
- `01_tools`: helper utilities and reusable wrappers
- `02_postprocess`: result cleanup and consolidation utilities
- `03_data_raw`: raw input manifests and small local placeholders
- `04_metadata`: schemas, sample sheets, benchmark metadata
- `05_data_processed`: normalized intermediate data products
- `06_scripts`: workflow entrypoints and module implementations
- `07_results`: logs, temporary files, and module outputs
- `08_envs`: environment specs and future lock files
- `09_reports`: exported reports and summaries
- `99_legacy`: deprecated or migrated content

## Execution-Conscious Conventions

- Keep paths relative inside the repository whenever possible.
- Treat `config.yaml` as the single source of truth for project-level paths.
- Keep server project root explicit in config as `/shared/shen/cpu_ai_drug_design`.
- Reserve heavy inputs and formal runs for the HPC side later; local scaffold remains lightweight.

## Result Layout

- `07_results/logs/<module>.log`: per-module execution log
- `07_results/modules/<module>/done.json`: placeholder module artifact
- `07_results/tmp`: transient local runtime outputs
