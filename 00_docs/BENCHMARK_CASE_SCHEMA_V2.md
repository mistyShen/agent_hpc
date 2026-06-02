# Benchmark Case Schema v2

## Goal

`benchmark_cases.tsv` should evolve from a minimal workflow switchboard into a benchmark definition table that supports:

- reproducible case typing
- fair comparison across methods
- explicit train/debug/evaluation separation
- later paper-ready aggregation

This document defines the next schema without forcing an immediate code migration.

## Current v1 Fields

Current file:

- `04_metadata/benchmark_cases.tsv`

Current fields:

- `case_id`
- `target_id`
- `library_id`
- `docking_protocol`
- `rerank_strategy`
- `filter_policy`
- `clustering_policy`
- `report_template`
- `enabled`

Current limitation:

- enough to run the DAG
- not enough to explain what a case means scientifically

## Proposed v2 Fields

Recommended required fields:

- `case_id`
- `case_type`
- `case_tier`
- `case_group`
- `target_id`
- `library_id`
- `docking_protocol`
- `rerank_strategy`
- `filter_policy`
- `clustering_policy`
- `report_template`
- `enabled`

Recommended provenance fields:

- `case_description`
- `target_origin`
- `library_origin`
- `reference_source`
- `reference_doi_or_url`
- `expected_behavior`

Recommended evaluation fields:

- `ground_truth_type`
- `known_active_definition`
- `decoy_definition`
- `primary_metric`
- `secondary_metrics`

Recommended operations fields:

- `run_purpose`
- `notes`
- `created_by`
- `created_at_utc`

## Field Semantics

- `case_type`
  - one of `toy`, `debug`, `realistic`, `literature_backed`
- `case_tier`
  - a short operational priority such as `bringup`, `smoke`, `comparison`, `paper_candidate`
- `case_group`
  - a stable grouping label for later benchmark families
- `target_origin`
  - where the target setup came from, such as `placeholder`, `experimental_structure`, `literature_protocol`
- `library_origin`
  - where the ligand set came from, such as `toy_smiles`, `focused_library`, `literature_actives_decoys`
- `reference_source`
  - a short human-readable citation key
- `expected_behavior`
  - what the workflow should recover or rank well in this case
- `ground_truth_type`
  - such as `none`, `known_binder`, `actives_vs_decoys`, `pose_recovery`
- `primary_metric`
  - such as `none`, `top1_known_active`, `enrichment_factor`, `auroc`, `pose_rmsd`
- `run_purpose`
  - such as `debug`, `regression`, `comparison`, `manuscript`

## Current Case Typing

Current active case mapped into v2 language:

| case_id | case_type | case_tier | case_group | run_purpose | interpretation |
| --- | --- | --- | --- | --- | --- |
| `DEMO_CASE_001` | `toy` | `bringup` | `demo_debug` | `debug` | validates the module chain and artifact flow, not scientific performance |

## Example v2 Row

```tsv
case_id	case_type	case_tier	case_group	target_id	library_id	docking_protocol	rerank_strategy	filter_policy	clustering_policy	report_template	enabled	case_description	target_origin	library_origin	reference_source	reference_doi_or_url	expected_behavior	ground_truth_type	known_active_definition	decoy_definition	primary_metric	secondary_metrics	run_purpose	notes
DEMO_CASE_001	toy	bringup	demo_debug	DEMO_TARGET_001	DEMO_LIB_001	cpu_placeholder	ai_placeholder	basic_placeholder	diversity_placeholder	summary_v1	true	Minimal smoke-test benchmark for workflow recovery	placeholder	toy_smiles	none	none	Module chain completes and writes expected artifacts	none	none	none	none	none	debug	Keep tiny and stable
```

## Expansion Strategy

Add benchmark coverage in this order:

1. keep the current toy debug case untouched as a permanent smoke test
2. add one `realistic` case with a larger but still local-manageable focused library
3. add one `literature_backed` case with explicit provenance and a recoverable known active
4. separate debug cases from comparison cases in reports and evaluation summaries

## Migration Policy

Short term:

- do not break the current v1 file
- treat this document as the contract for the next metadata upgrade

When migration starts:

- add v2 columns in a backward-compatible way
- update validation scripts before updating module logic
- keep `case_id`, `target_id`, and `library_id` stable
