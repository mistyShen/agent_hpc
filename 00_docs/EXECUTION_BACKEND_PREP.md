# Execution Backend Preparation

## Purpose

This document is a lightweight productization-preparation note. It does not change the current workflow behavior. Its purpose is to clarify where the current local-plus-server execution model is tightly coupled, and to define the smallest future abstraction boundary for an execution backend layer.

Current priority remains:

1. strengthen scientific and benchmark-facing capability
2. keep the current frozen manuscript and benchmark result line stable
3. prepare, but do not yet implement, a cleaner execution backend layer

## Current Coupling Points

The workflow currently works, but local and server execution concerns are still mixed together in several places.

### 1. Config-level path coupling

Current examples:

- `config.yaml`
  - `project.local_root`
  - `project.server_root`
  - `modules.classical_docking.backend_env_prefix`

Why this is coupled:

- one config file currently carries both local and remote concerns
- remote paths are still embedded as concrete deployment details
- execution environment selection is not yet separate from scientific module settings

### 2. Script-level project-root coupling

Current examples:

- modules accept `--project-root`
- HPC wrappers default to `/shared/shen/cpu_ai_drug_design`
- multiple tools assume the server root layout directly

Why this is coupled:

- project identity and execution location are still intertwined
- the same module interface is used for both local and server runs, but backend selection is mostly external and implicit

### 3. Wrapper-level HPC coupling

Current examples:

- `01_tools/preflight_hpc.sh`
- `01_tools/sync_to_hpc.sh`
- `01_tools/submit_hpc_dry_run.sh`
- `01_tools/submit_hpc_scaffold_run.sh`
- approved `hpc-run`, `hpc-put`, `hpc-get`, `hpc-sbatch`

Why this is coupled:

- HPC orchestration currently lives in helper scripts rather than behind a formal execution backend contract
- remote submission style, sync behavior, and path conventions are encoded operationally instead of declaratively

### 4. Documentation-level mixed execution semantics

Current examples:

- `RUN_RECOVERY.md` describes partial rerun semantics in a backend-agnostic way
- actual operational entrypoints still differ across local shell, direct Python module execution, wrapper scripts, and HPC helper commands

Why this is coupled:

- the recovery model is already cleaner than the execution surface
- the execution surface still lacks a single user-facing contract

## What Should Eventually Be Abstracted

The future execution backend layer should be narrow. It should not try to redesign scientific modules.

Target abstraction boundary:

- keep module interfaces stable
- keep artifact schemas stable
- keep rerun and partial-rerun semantics stable
- move environment and location choice behind a small execution backend contract

The execution backend layer should answer only:

1. where the project runs
2. how commands are launched
3. how files are synchronized when needed
4. how logs and run status are surfaced

It should not decide:

- scientific scoring logic
- benchmark schema
- case metadata structure
- module payload formats

## Proposed Future Execution Backend Layer

Minimal conceptual object:

- `execution_backend`
  - `local`
  - `remote_sync_shell`
  - later, if needed:
    - `remote_slurm`
    - `remote_service`

Minimal responsibilities:

### `local`

- runs commands in the current working tree
- uses current `config.yaml`
- writes results locally

### `remote_sync_shell`

- syncs selected files to a remote project root
- runs workflow commands remotely
- pulls back selected reports or artifacts when requested

### later backends, not yet needed

- `remote_slurm`
  - submits jobs via scheduler-aware wrappers
- `remote_service`
  - product/API-facing execution, if the project later becomes service-backed

## Minimal Remote Profile Schema

This schema is intentionally small. It should describe execution location, not scientific behavior.

Suggested future shape:

```yaml
execution_profiles:
  local_default:
    backend: local
    project_root: .

  hpc_default:
    backend: remote_sync_shell
    remote_host_alias: shen_hpc
    remote_project_root: /shared/shen/cpu_ai_drug_design
    sync_strategy: selective
    command_prefix: []
    scheduler_mode: direct_shell
```

Required fields:

- `backend`
- `project_root` or `remote_project_root`
- `remote_host_alias` for remote backends

Optional fields:

- `sync_strategy`
- `command_prefix`
- `scheduler_mode`

Deliberately excluded for now:

- scientific module settings
- benchmark case selection
- threshold values
- backend-specific scientific options

## Minimal CLI Command Set

The future CLI should stay small. It should map to current operations rather than invent new concepts.

Suggested minimum:

### 1. `workflow run`

Purpose:

- run the workflow or a selected module chain under a named execution profile

Example shape:

```bash
workflow run --profile local_default
workflow run --profile hpc_default --case BRD4_BD1_LIT002
workflow run --profile hpc_default --module ai_reranking --case BRD4_BD1_LIT002_V3EXP
```

### 2. `workflow sync`

Purpose:

- push the current project or selected files to a remote profile

Example shape:

```bash
workflow sync --profile hpc_default
```

### 3. `workflow status`

Purpose:

- summarize run-manifest state, module done state, and key outputs

Example shape:

```bash
workflow status --profile local_default
workflow status --profile hpc_default --case BRD4_BD1_LIT001
```

### 4. `workflow fetch`

Purpose:

- retrieve selected reports or result artifacts from remote execution profiles

Example shape:

```bash
workflow fetch --profile hpc_default --report benchmark_summary
```

These four commands are enough for an initial productization layer. Anything larger should be justified later.

## Recommended Phasing

### Phase A: capability first

Continue current mainline work on:

- `ai_reranking v3`
- `clustering_and_prioritization v2`
- benchmark comparison quality

Do not restructure execution yet.

### Phase B: thin execution contract

After the scientific capability is stronger:

- define profile loading
- wrap current local and HPC wrappers behind one small CLI
- keep existing scripts working during transition

### Phase C: backend cleanup

Only after Phase B proves useful:

- reduce duplicated path assumptions
- move more `/shared/shen/...` details out of general-purpose docs and wrappers
- unify status and fetch behavior

## What Not To Do Yet

Do not do these now:

- a large execution-backend refactor
- replacing all current HPC helper scripts
- changing module interfaces
- changing artifact schemas
- bundling scientific policy with execution-profile settings
- turning execution abstraction into the main project priority before capability matures

## Immediate Recommendation

Keep the current execution surface operational and explicit. Use this document only as a preparation layer while the mainline continues to strengthen:

- reranking quality
- shortlist quality
- benchmark comparison quality

That order is still the right one.
