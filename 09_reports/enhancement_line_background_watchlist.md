# Enhancement Line Background Watchlist

- Generated at: `2026-04-16T06:31:46.862354+00:00`
- Known active: `I-BET762`
- Current best background: `BG_BIPHENYL`
- Active-best-background gap: `6.146`

## Recommended Next Tuning Move

- Recommended knob: `simple_aromatic_penalty`
- Recommended direction: `increase_slightly`
- Target compound: `BG_BIPHENYL`
- Target flags: `simple_aromatic_background, polyaryl_hydrophobe_background`
- Strongest aggregate flag: `polyaryl_hydrophobe_background`
- Rationale: Current best background `BG_BIPHENYL` is still closest to the known active. It is currently explained most directly by `simple_aromatic_background`. Aggregate suppression remains strongest for `polyaryl_hydrophobe_background`, so keep that signal stable while nudging the current bottleneck.

## Watchlist

| Compound | Baseline rank | Enhancement rank | Rank delta | Enhancement score | Baseline shortlist | Enhancement shortlist | Flags | Labels |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `BG_BIPHENYL` | `2` | `2` | `0` | `-2.754` | `True` | `False` | `simple_aromatic_background, polyaryl_hydrophobe_background` | `current_best_background, removed_from_shortlist, explained_by_physchem_flags` |
| `BG_BENZAMIDE` | `3` | `3` | `0` | `-2.741` | `False` | `False` | `single_ring_background` | `explained_by_physchem_flags` |
| `BG_QUINOLINE` | `5` | `4` | `1` | `-2.284` | `False` | `False` | `simple_aromatic_background, polyaryl_hydrophobe_background` | `moved_up, explained_by_physchem_flags` |
| `BG_INDOLE` | `6` | `5` | `1` | `-1.863` | `False` | `False` | `simple_aromatic_background, polyaryl_hydrophobe_background` | `moved_up, explained_by_physchem_flags` |
