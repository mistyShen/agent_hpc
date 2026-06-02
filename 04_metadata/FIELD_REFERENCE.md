# Metadata Field Reference

## `datasets.tsv`

- `dataset_id`: unique dataset handle
- `description`: short human-readable description
- `source_type`: `synthetic`, `public`, `internal`, or other declared provenance
- `notes`: free-text caveats

## `targets.tsv`

- `target_id`: unique target handle
- `species`: organism label
- `target_type`: protein, complex, nucleic acid, or other target class
- `structure_source`: where the structure comes from
- `structure_path`: relative path to the structure file placeholder or asset
- `center_x` / `center_y` / `center_z`: optional manual docking-box center overrides
- `size_x` / `size_y` / `size_z`: optional manual docking-box size overrides
- `notes`: free-text caveats

## `compound_libraries.tsv`

- `library_id`: unique library handle
- `library_type`: vendor, virtual, focused, fragment, etc.
- `source_path`: relative path to source file placeholder
- `record_format`: expected format such as `smi`, `sdf`, or `csv`
- `notes`: free-text caveats

## `benchmark_cases.tsv`

- `case_id`: unique benchmark run handle
- `case_type`: current benchmark class, one of `toy`, `debug`, `realistic`, or `literature_backed`
- `case_tier`: short operational tier such as `bringup`, `smoke`, `comparison`, or `paper_candidate`
- `run_purpose`: current run intent such as `debug`, `regression`, `comparison`, or `manuscript`
- `primary_metric`: primary comparison metric placeholder such as `none`, `top1_known_active`, `enrichment_factor`, or `pose_rmsd`
- `target_id`: foreign key into `targets.tsv`
- `library_id`: foreign key into `compound_libraries.tsv`
- `docking_protocol`: placeholder docking strategy id
- `rerank_strategy`: placeholder AI reranking strategy id
- `filter_policy`: placeholder filtering policy id
- `clustering_policy`: placeholder diversity or clustering policy id
- `report_template`: reporting template id
- `reference_source`: short citation key or provenance handle for the case
- `reference_doi_or_url`: DOI, PDB URL, or other primary reference link for the case
- `ground_truth_type`: case-level truth type such as `none` or `known_binder`
- `known_active_definition`: short description of how known actives are identified for this case
- `expected_behavior`: short statement of what successful recovery should look like
- `enabled`: `true` or `false`

## `benchmark_case_truth.tsv`

- `case_id`: foreign key into `benchmark_cases.tsv`
- `compound_id`: compound handle expected to match the prepared library and downstream results
- `truth_label`: `known_active` or `background`
- `truth_role`: `anchor_active`, `reported_active`, `background_control`, or another declared role
- `reference_source`: short citation key or provenance handle for the truth row
- `reference_doi_or_url`: primary reference link for the truth row
- `notes`: free-text caveats

## Expansion Rules

- Keep IDs stable once referenced by downstream outputs.
- Prefer relative paths inside metadata.
- Add new columns conservatively and document them here before using them in rules.
