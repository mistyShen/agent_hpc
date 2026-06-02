# Benchmark Evaluation

- Project: `cpu_ai_drug_design`
- Enabled benchmark cases: `5`
- Completed cases: `2`
- Valid artifact cases: `0`
- Candidate count: `0`
- Avg candidates per enabled case: `0.0`
- Report available: `True`
- Filtering available: `True`
- Evaluation status: `typed_lightweight_complete`

## Enabled Case Types

- `toy`: `1`
- `debug`: `2`
- `realistic`: `0`
- `literature_backed`: `2`

## Enabled Run Purposes

- `comparison`: `2`
- `debug`: `3`

## Enabled Primary Metrics

- `none`: `3`
- `shortlist_contains_known_active`: `2`

## Case Catalog

- `DEMO_CASE_001`: type `toy`, tier `bringup`, purpose `debug`, metric `none`, band `bringup_debug`, enabled `True`
- `DEMO_CASE_002`: type `debug`, tier `smoke`, purpose `debug`, metric `none`, band `bringup_debug`, enabled `True`
- `DEMO_CASE_003`: type `debug`, tier `smoke`, purpose `debug`, metric `none`, band `bringup_debug`, enabled `True`
- `BRD4_BD1_LIT001`: type `literature_backed`, tier `comparison`, purpose `comparison`, metric `shortlist_contains_known_active`, band `comparison_oriented`, enabled `True`
- `BRD4_BD1_LIT002`: type `literature_backed`, tier `comparison`, purpose `comparison`, metric `shortlist_contains_known_active`, band `comparison_oriented`, enabled `True`

## Grouped Comparisons By Case Type

- `debug`: cases `2`, enabled `2`, completed `0`, valid artifacts `0`
- `literature_backed`: cases `2`, enabled `2`, completed `1`, valid artifacts `0`
- `toy`: cases `1`, enabled `1`, completed `1`, valid artifacts `0`

## Grouped Comparisons By Run Purpose

- `comparison`: cases `2`, enabled `2`, completed `1`, valid artifacts `0`
- `debug`: cases `3`, enabled `3`, completed `1`, valid artifacts `0`

## Grouped Comparisons By Primary Metric

- `none`: cases `3`, enabled `3`, completed `1`, valid artifacts `0`
- `shortlist_contains_known_active`: cases `2`, enabled `2`, completed `1`, valid artifacts `0`

## Bringup And Comparison Bands

- `bringup_debug`: cases `3`, enabled `3`, completed `1`, valid artifacts `0`
- `comparison_oriented`: cases `2`, enabled `2`, completed `1`, valid artifacts `0`

## Ground Truth Recovery Summary

| Case | Known Active Count | In Filter Keep | In Shortlist | Shortlist Contains Known Active | Best Known Active Rank |
| --- | --- | --- | --- | --- | --- |
| BRD4_BD1_LIT001 | 1 | 0 | 0 | False |  |
| BRD4_BD1_LIT002 | 1 | 0 | 0 | False |  |

