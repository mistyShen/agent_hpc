# Enhancement Line Workflow

This note describes the smallest safe workflow for iterating on the enhancement line without touching the frozen manuscript / benchmark result line.

## Scope

Use this workflow when:

- the frozen line must remain unchanged
- a new enhancement-only rerank or prioritization experiment is being tested
- the goal is to improve scientific separation or tool usability on the isolated enhancement workspace

Do not use this workflow to update:

- `BRD4_BD1_LIT001`
- `BRD4_BD1_LIT002`
- frozen manuscript tables or benchmark claims

## Current Isolated Enhancement Case

- baseline frozen comparison case: `BRD4_BD1_LIT002`
- enhancement experiment case: `BRD4_BD1_LIT002_V3EXP`
- isolated remote execution root: `/shared/shen/cpu_ai_drug_design_v3exp`

## Core Safety Rule

Keep the enhancement line isolated.

- default rerank backend stays `cpu_docking_rerank_v2`
- only explicit enhancement cases should use `ai_rerank_v3`
- fetch enhancement outputs into local `09_reports/` only after the isolated remote run succeeds

## Minimal Iteration Loop

### 1. Make a small enhancement-only change

Examples:

- adjust `config.yaml` under `ai_reranking.v3`
- refine enhancement-only reporting tools under `01_tools/`
- improve enhancement-only diagnostics

Avoid changing multiple scientific rules at once.

### 2. Re-run only the enhancement case on the isolated remote workspace

Typical remote chain:

- `ai_reranking`
- `filtering`
- `clustering_and_prioritization`
- `benchmark_evaluation`
- enhancement comparison builders

Do not re-run frozen cases unless there is a deliberate compatibility check.

### 3. Fetch back the enhancement reports

Refresh at least:

- `09_reports/enhancement_line_v2_vs_v3_comparison.json`
- `09_reports/enhancement_line_v2_vs_v3_comparison.md`
- `09_reports/enhancement_line_background_delta.json`
- `09_reports/enhancement_line_background_delta.md`

### 4. Rebuild local derived reports in one command

Run:

```bash
python3 01_tools/rebuild_enhancement_reports.py --project-root . --strict
```

If you want the tool to fetch the current enhancement reports from the isolated remote workspace first, run:

```bash
python3 01_tools/rebuild_enhancement_reports.py --project-root . --fetch-remote-root /shared/shen/cpu_ai_drug_design_v3exp --strict
```

This serially rebuilds:

- comparison-dependent background delta
- iteration tracker
- diagnostic checklist
- flag impact summary
- hard-background watchlist
- enhancement snapshot history + trend summary

Behavior note:

- if local `07_results` contains both enhancement cases, the tool will rebuild comparison and background delta from raw workflow outputs
- if local `07_results` does not contain those rows, the tool will safely reuse the fetched local `09_reports/enhancement_line_v2_vs_v3_comparison.json` and `09_reports/enhancement_line_background_delta.json`, then continue rebuilding downstream reports

and then validates:

- comparison gap matches tracker gap
- shortlist count matches across outputs
- checklist consistency gates are all true

### 5. Decide based on tool outputs, not intuition

Primary decision surfaces:

- `09_reports/enhancement_line_v2_vs_v3_comparison.md`
- `09_reports/enhancement_line_background_delta.md`
- `09_reports/enhancement_line_iteration_tracker.md`
- `09_reports/enhancement_line_diagnostic_checklist.md`
- `09_reports/enhancement_line_flag_impact_summary.md`
- `09_reports/enhancement_line_background_watchlist.md`
- `09_reports/enhancement_line_trend_summary.md`

The trend archive now auto-labels snapshots from the current key `v3` tuning values, so future history is easier to read without manual naming.

The background watchlist and trend summary now also emit a recommended next tuning knob and direction, so the next enhancement step can be chosen from current evidence instead of memory.

### 6. After 1-2 tuning steps, run a bounded rule audit

When the enhancement line has moved forward for a couple of small steps, stop local tuning and run:

```bash
python3 01_tools/run_enhancement_rule_audit.py --project-root . --remote-root /shared/shen/cpu_ai_drug_design_v3exp
```

This fetches the isolated enhancement source files and docking artifacts, then locally recomputes the enhancement case under bounded ablations without overwriting the remote enhancement outputs.

Current bounded audit set:

- `ablate_simple_aromatic_penalty`
- `ablate_polyaryl_hydrophobe_penalty`
- `ablate_single_ring_background_penalty`
- `ablate_all_background_penalties`

Primary audit outputs:

- `09_reports/enhancement_line_rule_audit.md`
- `09_reports/enhancement_line_rule_audit.json`

Use the audit to answer:

- which penalty is currently driving most of the active-background gap
- which penalties are still contributing materially on the current panel
- whether shortlist behavior is robust or only the margin is changing
- whether the next step should still be tuning, or should shift to a new case / cross-case check

### 7. After audit, run a bounded cross-case compatibility check

Before making broader claims about the current `v3` tuning, run a local compatibility check against an existing frozen/root literature-backed case:

```bash
python3 01_tools/run_enhancement_cross_case_check.py --project-root . --remote-root /shared/shen/cpu_ai_drug_design --case-id BRD4_BD1_LIT001
```

This fetches the selected case source files from the frozen/root workspace, locally recomputes the case under the current enhancement `v3` tuning, and compares the simulated result to the reference frozen/root outputs without overwriting the remote case.

Primary compatibility outputs:

- `09_reports/enhancement_cross_case_check_BRD4_BD1_LIT001.md`
- `09_reports/enhancement_cross_case_check_BRD4_BD1_LIT001.json`

Use the compatibility check to answer:

- whether the known active still remains rank 1
- whether the known active still remains shortlisted
- whether shortlist size expands under the current enhancement tuning
- whether the current `v3` tuning already shows obvious panel-specific overfitting

### 8. Before broader rollout, build a dual-case validation readout

Once there are at least two enhancement-only validation surfaces, rebuild:

```bash
python3 01_tools/build_enhancement_dual_case_validation_summary.py --project-root .
python3 01_tools/build_enhancement_panel_profile_summary.py --project-root .
```

Primary outputs:

- `09_reports/enhancement_dual_case_validation_summary.md`
- `09_reports/enhancement_dual_case_validation_summary.json`
- `09_reports/enhancement_panel_profile_summary.md`
- `09_reports/enhancement_panel_profile_summary.json`

Use the dual-case summary to answer:

- whether current `v3` behavior is materially helpful on more than one enhancement-only case
- whether a case is only a compatibility-preserving pass versus a real margin-improving gain
- whether the next step should be case-aware gating, another validation surface, or further bounded tuning

Use the panel-profile summary to answer:

- whether the current panel composition actually exposes the background types the current `v3` penalties target
- whether a weak-on-panel result is explained by panel chemistry rather than by broken logic
- whether a proposed gating rule has a plausible panel-structure basis

## Recommended Reading Order

1. comparison
2. background delta
3. background watchlist
4. tracker
5. diagnostic checklist
6. flag impact summary
7. dual-case validation summary
8. panel profile summary

## What Good Looks Like

Prefer changes that keep all of these true:

- known active remains rank 1
- known active remains shortlisted
- active-best-background gap improves
- shortlist compresses or stays tighter
- diagnostic outputs remain consistent

## Current Practical Heuristic

When tuning `v3`, prioritize:

- one config-only change at a time
- one interpretable scientific hypothesis at a time
- rebuilding reports with the single-entry tool immediately after fetch

That keeps the system acting like a tool instead of a collection of ad hoc scripts.

## 9. When The Boundary Is Stable, Freeze A Handoff Package

Once the current enhancement boundary is stable enough that the next step could reasonably be handoff rather than more tuning, rebuild:

```bash
python3 01_tools/build_enhancement_line_handoff_package.py --project-root .
```

Primary outputs:

- `09_reports/enhancement_line_handoff_package.md`
- `09_reports/enhancement_line_handoff_package.json`

Use the handoff package to answer:

- what the current bounded headline is
- which surfaces are currently material versus weak
- what is safe to say and what remains blocked from frozen promotion
- what the next operator should do without reopening old claim-boundary debates
