from __future__ import annotations

import csv
import importlib
import importlib.util
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

try:  # pragma: no cover - optional scientific deps are not installed in the local test env
    from singlecell_workbench.types import SingleCellData
except Exception:  # pragma: no cover - keep the module importable without AnnData/MuData
    SingleCellData = Any

_DEFAULT_SAMPLE_KEY = "sample_id"
_DEFAULT_CELL_TYPE_KEY = "cell_type"
_DEFAULT_CONDITION_KEY = "condition"


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, set):
        return sorted(_json_safe(item) for item in value)
    return value


def _stringify_group_value(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float) and math.isnan(value):
        return "unknown"
    text = str(value).strip()
    return text if text else "unknown"


def _is_mudata_like(data: Any) -> bool:
    return hasattr(data, "mod") and isinstance(getattr(data, "mod"), dict)


def _resolve_data_view(data: Any, working_modality: str | None) -> tuple[Any, str | None, list[str]]:
    warnings: list[str] = []
    if not _is_mudata_like(data):
        return data, None, warnings

    modalities = list(getattr(data, "mod", {}).keys())
    if working_modality:
        selected = getattr(data, "mod", {}).get(working_modality)
        if selected is None:
            warnings.append(
                f'working modality "{working_modality}" was not found; using MuData-level observations instead'
            )
            return data, None, warnings
        return selected, working_modality, warnings

    if len(modalities) == 1:
        modality = modalities[0]
        return getattr(data, "mod")[modality], modality, warnings

    warnings.append("multiple modalities detected without an explicit working modality; using MuData-level observations")
    return data, None, warnings


def _propagate_parent_obs(parent: Any, child: Any) -> None:
    if not hasattr(parent, "obs") or not hasattr(child, "obs"):
        return
    parent_obs = getattr(parent, "obs")
    child_obs = getattr(child, "obs")
    if not hasattr(parent_obs, "reindex") or not hasattr(child_obs, "index"):
        return
    aligned_parent = pd.DataFrame(parent_obs).reindex(pd.Index(child_obs.index))
    target = pd.DataFrame(child_obs).copy()
    for column in aligned_parent.columns:
        if column not in target.columns:
            target[column] = aligned_parent[column]
    child.obs = target


def _iter_obs_rows(obs: Any) -> list[dict[str, Any]]:
    if obs is None:
        return []
    if isinstance(obs, list):
        rows: list[dict[str, Any]] = []
        for row in obs:
            if isinstance(row, dict):
                rows.append(dict(row))
            else:
                rows.append(dict(row))
        return rows

    to_dict = getattr(obs, "to_dict", None)
    if callable(to_dict):
        try:
            records = to_dict(orient="records")
        except TypeError:
            records = to_dict()
            if isinstance(records, dict):
                keys = list(records.keys())
                length = len(next(iter(records.values()), []))
                return [
                    {key: records[key][index] for key in keys}
                    for index in range(length)
                ]
        if isinstance(records, list):
            return [dict(row) for row in records]

    if hasattr(obs, "columns"):
        columns = list(getattr(obs, "columns"))
        length = len(obs)
        rows = []
        for index in range(length):
            rows.append({column: obs[column][index] for column in columns})
        return rows

    if isinstance(obs, dict):
        keys = list(obs.keys())
        length = len(next(iter(obs.values()), []))
        return [{key: obs[key][index] for key in keys} for index in range(length)]

    return [dict(row) for row in obs]


def _get_obs_source(data: Any) -> Any:
    if hasattr(data, "obs"):
        return getattr(data, "obs")
    return None


def _extract_records(data: Any) -> list[dict[str, Any]]:
    return _iter_obs_rows(_get_obs_source(data))


def _resolve_group_key(records: list[dict[str, Any]], requested: str, aliases: list[str]) -> tuple[str, str | None]:
    if any(requested in record for record in records):
        return requested, None
    for alias in aliases:
        if alias != requested and any(alias in record for record in records):
            return alias, f'grouping key "{requested}" was not found; using "{alias}" instead'
    return requested, None


def _group_records(
    records: list[dict[str, Any]],
    sample_key: str,
    cell_type_key: str,
    condition_key: str,
) -> tuple[
    dict[tuple[str, str, str], list[int]],
    dict[str, int],
    dict[str, int],
    dict[tuple[str, str], int],
    dict[str, int],
]:
    group_index: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    sample_totals: dict[str, int] = defaultdict(int)
    cell_type_totals: dict[str, int] = defaultdict(int)
    sample_condition_totals: dict[tuple[str, str], int] = defaultdict(int)
    repaired_counts: dict[str, int] = defaultdict(int)

    for index, record in enumerate(records):
        sample = _stringify_group_value(record.get(sample_key))
        cell_type = _stringify_group_value(record.get(cell_type_key))
        condition = _stringify_group_value(record.get(condition_key))
        if sample == "unknown":
            repaired_counts[sample_key] += 1
        if cell_type == "unknown":
            repaired_counts[cell_type_key] += 1
        if condition == "unknown":
            repaired_counts[condition_key] += 1
        group_index[(sample, cell_type, condition)].append(index)
        sample_totals[sample] += 1
        cell_type_totals[cell_type] += 1
        sample_condition_totals[(sample, condition)] += 1

    return group_index, sample_totals, cell_type_totals, sample_condition_totals, repaired_counts


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def _extract_numeric_matrix(data: Any, layer: str | None = None) -> list[list[float]] | None:
    source = data
    if layer and hasattr(data, "layers"):
        layers = getattr(data, "layers")
        if isinstance(layers, dict) and layer in layers:
            source = layers[layer]
    matrix = getattr(source, "X", None)
    if matrix is None:
        return None
    if hasattr(matrix, "toarray"):
        matrix = matrix.toarray()
    elif hasattr(matrix, "A"):
        matrix = matrix.A
    if hasattr(matrix, "tolist"):
        matrix = matrix.tolist()
    if not isinstance(matrix, list):
        try:
            matrix = [list(row) for row in matrix]
        except TypeError:
            return None
    return [[float(value) for value in row] for row in matrix]


def _extract_feature_names(data: Any) -> list[str] | None:
    if hasattr(data, "var_names"):
        names = getattr(data, "var_names")
        if isinstance(names, (list, tuple)):
            return [str(name) for name in names]
        if hasattr(names, "tolist"):
            return [str(name) for name in names.tolist()]
        return [str(name) for name in list(names)]

    var = getattr(data, "var", None)
    if var is None:
        return None
    if hasattr(var, "index"):
        return [str(name) for name in list(var.index)]
    if isinstance(var, dict):
        if "index" in var:
            return [str(name) for name in list(var["index"])]
        return [str(name) for name in list(next(iter(var.values()), []))]
    return None


def _build_summary_rows(
    records: list[dict[str, Any]],
    sample_key: str,
    cell_type_key: str,
    condition_key: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[tuple[str, str, str], list[int]]]:
    groups, sample_totals, _, sample_condition_totals, repaired_counts = _group_records(
        records,
        sample_key,
        cell_type_key,
        condition_key,
    )
    total_cells = len(records)
    rows: list[dict[str, Any]] = []
    for sample, cell_type, condition in sorted(groups):
        count = len(groups[(sample, cell_type, condition)])
        sample_total = sample_totals[sample]
        sample_condition_total = sample_condition_totals[(sample, condition)]
        rows.append(
            {
                "sample": sample,
                "cell_type": cell_type,
                "condition": condition,
                "n_cells": count,
                "fraction_of_all_cells": count / total_cells if total_cells else 0.0,
                "fraction_within_sample": count / sample_total if sample_total else 0.0,
                "fraction_within_sample_condition": (
                    count / sample_condition_total if sample_condition_total else 0.0
                ),
            }
        )
    schema_report = {
        "requested_keys": {
            "sample": sample_key,
            "cell_type": cell_type_key,
            "condition": condition_key,
        },
        "missing_or_repaired_values": dict(repaired_counts),
        "total_cells": total_cells,
    }
    return rows, schema_report, groups


def _build_pseudobulk(
    matrix: list[list[float]] | None,
    groups: dict[tuple[str, str, str], list[int]],
) -> tuple[list[list[float]], list[str]]:
    if matrix is None:
        return [], []
    rows: list[list[float]] = []
    labels: list[str] = []
    for sample, cell_type, condition in sorted(groups):
        indices = groups[(sample, cell_type, condition)]
        if not indices:
            continue
        length = len(matrix[0]) if matrix else 0
        aggregated = [0.0] * length
        for index in indices:
            row = matrix[index]
            for position, value in enumerate(row):
                aggregated[position] += float(value)
        divisor = float(len(indices))
        rows.append([value / divisor for value in aggregated])
        labels.append(" | ".join([sample, cell_type, condition]))
    return rows, labels


def _dependency_available(package_name: str) -> bool:
    return importlib.util.find_spec(package_name) is not None


def _load_network_table(source: Any) -> list[dict[str, Any]]:
    if source is None:
        return []
    if isinstance(source, list):
        return [dict(row) for row in source]
    if isinstance(source, dict):
        return [dict(source)]
    path = Path(source)
    if not path.exists():
        return []
    delimiter = "\t" if path.suffix.lower() in {".tsv", ".tab"} else ","
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        return [dict(row) for row in reader]


def _run_optional_decoupler(
    working_data: Any,
    groups: dict[tuple[str, str, str], list[int]],
    stats_dir: Path,
    stats_config: dict[str, Any],
) -> dict[str, Any]:
    dec_cfg = dict(stats_config.get("decoupler") or {})
    network_paths = {
        "pathway": str(dec_cfg.get("pathway_network")) if dec_cfg.get("pathway_network") is not None else None,
        "tf": str(dec_cfg.get("tf_network")) if dec_cfg.get("tf_network") is not None else None,
    }
    if not dec_cfg.get("enabled", True):
        return {"status": "skipped", "reason": "decoupler disabled in stats_config", "network_paths": network_paths}
    if not _dependency_available("decoupler"):
        return {"status": "skipped", "reason": "decoupler is not installed", "network_paths": network_paths}
    if not _dependency_available("pandas"):
        return {"status": "skipped", "reason": "pandas is not installed", "network_paths": network_paths}

    matrix = _extract_numeric_matrix(working_data, layer=stats_config.get("layer"))
    genes = _extract_feature_names(working_data)
    if matrix is None or not genes:
        return {
            "status": "skipped",
            "reason": "expression matrix or feature names are unavailable on the working data",
            "network_paths": network_paths,
        }

    pseudobulk, labels = _build_pseudobulk(matrix, groups)
    if not pseudobulk:
        return {
            "status": "skipped",
            "reason": "no pseudobulk groups were available for decoupler analysis",
            "network_paths": network_paths,
        }

    try:
        import pandas as pd

        decoupler = importlib.import_module("decoupler")
    except Exception as exc:  # pragma: no cover - defensive for runtime environments
        return {"status": "skipped", "reason": f"failed to import decoupler support: {exc}", "network_paths": network_paths}

    analysis_manifest: dict[str, Any] = {
        "status": "completed",
        "analyses": [],
        "network_paths": network_paths,
        "runner_requested": dec_cfg.get("runner", "run_mlm"),
        "min_targets": dec_cfg.get("min_targets", dec_cfg.get("tmin", dec_cfg.get("min_n"))),
        "expression_features": len(genes),
        "pseudobulk_groups": len(labels),
    }
    expr = pd.DataFrame(pseudobulk, index=labels, columns=genes)

    for analysis_name, source_key in (("pathway", "pathway_network"), ("tf", "tf_network")):
        network = _load_network_table(dec_cfg.get(source_key))
        if not network:
            analysis_manifest["analyses"].append(
                {
                    "name": analysis_name,
                    "status": "skipped",
                    "reason": f"no {analysis_name} network was provided",
                }
            )
            continue

        net_df = pd.DataFrame(network)
        if not {"source", "target"}.issubset(net_df.columns):
            analysis_manifest["analyses"].append(
                {
                    "name": analysis_name,
                    "status": "skipped",
                    "reason": f'{analysis_name} network must include "source" and "target" columns',
                }
            )
            continue

        runner_name = dec_cfg.get("runner", "run_mlm")
        runner, resolved_runner_name = _resolve_decoupler_runner(decoupler, runner_name)
        if runner is None:
            analysis_manifest["analyses"].append(
                {
                    "name": analysis_name,
                    "status": "skipped",
                    "reason": f'decoupler does not expose runner "{runner_name}"',
                }
            )
            continue

        try:
            result = runner(expr, net_df, **_build_decoupler_runner_kwargs(dec_cfg, resolved_runner_name))
        except Exception as exc:  # pragma: no cover - runtime safety for varied decoupler versions
            analysis_manifest["analyses"].append(
                {
                    "name": analysis_name,
                    "status": "skipped",
                    "reason": f"decoupler analysis failed: {exc}",
                }
            )
            continue

        if result is None:
            analysis_manifest["analyses"].append(
                {
                    "name": analysis_name,
                    "status": "skipped",
                    "reason": f'decoupler runner "{resolved_runner_name}" returned no tabular result',
                }
            )
            continue

        if isinstance(result, tuple):
            result = result[0]

        output_name = f"{analysis_name}_activity.csv"
        output_path = stats_dir / output_name
        if hasattr(result, "to_csv"):
            result.to_csv(output_path)
        elif hasattr(result, "values") and hasattr(result, "index") and hasattr(result, "columns"):
            pd.DataFrame(result.values, index=result.index, columns=result.columns).to_csv(output_path)
        else:
            pd.DataFrame(result).to_csv(output_path)

        analysis_manifest["analyses"].append(
            {
                "name": analysis_name,
                "status": "completed",
                "output": str(output_path),
                "runner": resolved_runner_name,
            }
        )

    return analysis_manifest


def _resolve_decoupler_runner(decoupler: Any, runner_name: str) -> tuple[Any | None, str]:
    runner_aliases: list[str] = [runner_name]
    if runner_name.startswith("run_"):
        runner_aliases.append(runner_name.removeprefix("run_"))
    else:
        runner_aliases.append(f"run_{runner_name}")

    seen: set[str] = set()
    normalized_aliases: list[str] = []
    for alias in runner_aliases:
        if alias not in seen:
            seen.add(alias)
            normalized_aliases.append(alias)

    for alias in normalized_aliases:
        top_level_runner = getattr(decoupler, alias, None)
        if callable(top_level_runner):
            return top_level_runner, alias

    methods = getattr(decoupler, "mt", None)
    if methods is None:
        return None, runner_name

    for alias in normalized_aliases:
        method_name = alias.removeprefix("run_")
        method_runner = getattr(methods, method_name, None)
        if callable(method_runner):
            return method_runner, f"mt.{method_name}"

    return None, runner_name


def _build_decoupler_runner_kwargs(dec_cfg: dict[str, Any], resolved_runner_name: str) -> dict[str, Any]:
    kwargs = dict(dec_cfg.get("runner_kwargs") or {})
    min_targets = dec_cfg.get("min_targets", dec_cfg.get("tmin", dec_cfg.get("min_n")))
    if min_targets is not None:
        threshold_key = "tmin" if resolved_runner_name.startswith("mt.") else "min_n"
        kwargs.setdefault(threshold_key, min_targets)
    return kwargs


def run_statistics(
    data: SingleCellData,
    output_dir: Path,
    stats_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = dict(stats_config or {})
    stats_dir = Path(output_dir) / "stats"
    stats_dir.mkdir(parents=True, exist_ok=True)

    working_modality = config.get("working_modality") or config.get("modality")
    working_data, resolved_modality, warnings = _resolve_data_view(data, working_modality)
    if _is_mudata_like(data) and working_data is not data:
        _propagate_parent_obs(data, working_data)
    obs_source = working_data if _get_obs_source(working_data) is not None else data
    records = _extract_records(obs_source)

    sample_key = config.get("sample_column", config.get("sample_key", _DEFAULT_SAMPLE_KEY))
    cell_type_key = config.get("cell_type_column", config.get("cell_type_key", _DEFAULT_CELL_TYPE_KEY))
    condition_key = config.get("condition_column", config.get("condition_key", _DEFAULT_CONDITION_KEY))

    sample_key, sample_warning = _resolve_group_key(records, str(sample_key), ["sample_id", "sample"])
    cell_type_key, cell_type_warning = _resolve_group_key(records, str(cell_type_key), ["cell_type"])
    condition_key, condition_warning = _resolve_group_key(records, str(condition_key), ["condition"])
    warnings.extend(
        [warning for warning in [sample_warning, cell_type_warning, condition_warning] if warning]
    )

    summary_rows, schema_report, groups = _build_summary_rows(records, sample_key, cell_type_key, condition_key)

    summary_path = stats_dir / "sample_cell_type_condition_summary.csv"
    sample_totals_path = stats_dir / "sample_totals.csv"
    sample_condition_totals_path = stats_dir / "sample_condition_totals.csv"

    _write_csv(
        summary_path,
        summary_rows,
        [
            "sample",
            "cell_type",
            "condition",
            "n_cells",
            "fraction_of_all_cells",
            "fraction_within_sample",
            "fraction_within_sample_condition",
        ],
    )

    sample_totals: dict[str, int] = defaultdict(int)
    sample_condition_totals: dict[tuple[str, str], int] = defaultdict(int)
    for sample, cell_type, condition in groups:
        count = len(groups[(sample, cell_type, condition)])
        sample_totals[sample] += count
        sample_condition_totals[(sample, condition)] += count

    _write_csv(
        sample_totals_path,
        [
            {
                "sample": sample,
                "n_cells": n_cells,
                "fraction_of_all_cells": n_cells / len(records) if records else 0.0,
            }
            for sample, n_cells in sorted(sample_totals.items())
        ],
        ["sample", "n_cells", "fraction_of_all_cells"],
    )
    _write_csv(
        sample_condition_totals_path,
        [
            {
                "sample": sample,
                "condition": condition,
                "n_cells": n_cells,
                "fraction_of_all_cells": n_cells / len(records) if records else 0.0,
                "fraction_within_sample": n_cells / sample_totals[sample] if sample_totals[sample] else 0.0,
            }
            for (sample, condition), n_cells in sorted(sample_condition_totals.items())
        ],
        ["sample", "condition", "n_cells", "fraction_of_all_cells", "fraction_within_sample"],
    )

    decoupler_manifest = _run_optional_decoupler(working_data, groups, stats_dir, config)

    manifest = {
        "module": "stats",
        "status": "completed",
        "output_dir": str(stats_dir),
        "working_modality": resolved_modality,
        "sample_column": sample_key,
        "cell_type_column": cell_type_key,
        "condition_column": condition_key,
        "warnings": warnings,
        "schema": schema_report,
        "network_paths": {
            "pathway": str((config.get("decoupler") or {}).get("pathway_network"))
            if (config.get("decoupler") or {}).get("pathway_network") is not None
            else None,
            "tf": str((config.get("decoupler") or {}).get("tf_network"))
            if (config.get("decoupler") or {}).get("tf_network") is not None
            else None,
        },
        "tables": {
            "sample_cell_type_condition_summary": {
                "path": str(summary_path),
                "rows": len(summary_rows),
            },
            "sample_totals": {"path": str(sample_totals_path), "rows": len(sample_totals)},
            "sample_condition_totals": {
                "path": str(sample_condition_totals_path),
                "rows": len(sample_condition_totals),
            },
        },
        "decoupler": decoupler_manifest,
    }
    manifest_path = stats_dir / "manifest.json"
    manifest_path.write_text(json.dumps(_json_safe(manifest), indent=2, sort_keys=True), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return _json_safe(manifest)
