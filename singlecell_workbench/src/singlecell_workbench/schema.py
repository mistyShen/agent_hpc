from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


@dataclass(slots=True)
class SchemaIssue:
    location: str
    severity: str
    message: str
    suggestion: str


@dataclass(slots=True)
class SchemaReport:
    issues: list[SchemaIssue] = field(default_factory=list)
    applied_fixes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "issues": [asdict(issue) for issue in self.issues],
            "applied_fixes": list(self.applied_fixes),
        }


def make_unique(values: pd.Index | list[str]) -> pd.Index:
    seen: dict[str, int] = {}
    unique: list[str] = []
    for value in list(values):
        value = str(value)
        count = seen.get(value, 0)
        if count == 0 and value not in unique:
            unique.append(value)
        else:
            unique_name = f"{value}-{count}"
            while unique_name in seen:
                count += 1
                unique_name = f"{value}-{count}"
            unique.append(unique_name)
        seen[value] = count + 1
        seen[unique[-1]] = 1
    return pd.Index(unique)


def json_safe(value: Any, *, _seen: set[int] | None = None) -> Any:
    if _seen is None:
        _seen = set()

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, pd.Series):
        return [json_safe(item, _seen=_seen) for item in value.tolist()]
    if isinstance(value, pd.DataFrame):
        return {
            "__type__": "DataFrame",
            "columns": list(value.columns),
            "index": [json_safe(item, _seen=_seen) for item in value.index.tolist()],
            "data": {
                column: [json_safe(item, _seen=_seen) for item in value[column].tolist()]
                for column in value.columns
            },
        }

    object_id = id(value)
    if object_id in _seen:
        return "<cycle>"
    _seen.add(object_id)

    if isinstance(value, dict):
        return {
            str(key): json_safe(item, _seen=_seen)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [json_safe(item, _seen=_seen) for item in value]
    if isinstance(value, set):
        return [json_safe(item, _seen=_seen) for item in sorted(value, key=str)]

    return str(value)


def _ensure_dataframe(frame: Any, *, default_index_prefix: str) -> pd.DataFrame:
    if isinstance(frame, pd.DataFrame):
        result = frame.copy()
    elif frame is None:
        result = pd.DataFrame()
    elif isinstance(frame, dict):
        result = pd.DataFrame(frame)
    else:
        result = pd.DataFrame(frame)

    if result.index.empty or any(item is None for item in result.index):
        result.index = pd.Index(
            [f"{default_index_prefix}_{i}" for i in range(len(result))],
            name=result.index.name,
        )
    return result


def _coerce_column_values(values: Any, length: int) -> list[Any]:
    if values is None:
        return [None] * length
    if isinstance(values, (str, bytes)) or not hasattr(values, "__len__"):
        return [values] * length
    result = list(values)
    if len(result) == length:
        return result
    if len(result) == 1:
        return result * length
    return result[:length] + [None] * max(0, length - len(result))


def _shape_of(value: Any) -> tuple[int, ...] | None:
    shape = getattr(value, "shape", None)
    if shape is None:
        return None
    return tuple(int(item) for item in shape)


def _sanitize_uns(value: Any, report: SchemaReport, location: str) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Path):
        report.applied_fixes.append(f"Converted {location} Path to string")
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, pd.DataFrame):
        report.applied_fixes.append(f"Converted {location} DataFrame to JSON-safe mapping")
        return json_safe(value)
    if isinstance(value, pd.Series):
        report.applied_fixes.append(f"Converted {location} Series to list")
        return value.tolist()
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            cleaned[str(key)] = _sanitize_uns(item, report, f"{location}.{key}")
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_sanitize_uns(item, report, f"{location}[]") for item in value]
    if isinstance(value, set):
        return [_sanitize_uns(item, report, f"{location}[]") for item in sorted(value, key=str)]

    report.applied_fixes.append(f"Replaced unsupported uns value at {location} with string representation")
    return str(value)


def _validate_obs_or_var(
    frame: pd.DataFrame,
    *,
    location: str,
    report: SchemaReport,
    default_sample_id: str | None,
    default_condition: str | None,
) -> pd.DataFrame:
    result = frame.copy()

    if not result.index.is_unique:
        issue = SchemaIssue(
            location=location,
            severity="warning",
            message="Index contains duplicate names.",
            suggestion="Make names unique before downstream serialization.",
        )
        report.issues.append(issue)
        result.index = make_unique(result.index)
        report.applied_fixes.append(f"Made {location} names unique")

    if location == "obs":
        if "sample_id" not in result.columns:
            result["sample_id"] = default_sample_id or "unknown_sample"
            report.applied_fixes.append("Filled missing obs.sample_id values")
        else:
            result["sample_id"] = _coerce_column_values(result["sample_id"], len(result))
            result["sample_id"] = pd.Series(
                [default_sample_id if pd.isna(value) else value for value in result["sample_id"]],
                index=result.index,
            )

        if "condition" not in result.columns:
            result["condition"] = default_condition or "unknown_condition"
            report.applied_fixes.append("Filled missing obs.condition values")
        else:
            result["condition"] = _coerce_column_values(result["condition"], len(result))
            result["condition"] = pd.Series(
                [default_condition if pd.isna(value) else value for value in result["condition"]],
                index=result.index,
            )

    return result


def _validate_layers_or_obsm(
    *,
    container: dict[str, Any],
    expected_rows: int,
    report: SchemaReport,
    location: str,
) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, value in container.items():
        shape = _shape_of(value)
        if shape is None:
            cleaned[key] = value
            continue
        if len(shape) == 1 and shape[0] == expected_rows:
            cleaned[key] = np.asarray(value).reshape(expected_rows, 1)
            report.applied_fixes.append(f"Reshaped {location}.{key} to a column vector")
            continue
        if len(shape) >= 2 and shape[0] == expected_rows:
            cleaned[key] = value
            continue

        issue = SchemaIssue(
            location=f"{location}.{key}",
            severity="warning",
            message=f"Shape {shape} does not match expected row count {expected_rows}.",
            suggestion="Drop or recompute this entry so its first axis matches obs.",
        )
        report.issues.append(issue)
        report.applied_fixes.append(f"Dropped {location}.{key} because of a shape mismatch")
    return cleaned


def _replace_mapping(target: Any, replacement: dict[str, Any]) -> Any:
    if hasattr(target, "clear") and hasattr(target, "update"):
        target.clear()
        target.update(replacement)
        return target
    return replacement


def validate_and_fix_schema(
    data: Any,
    config: dict[str, Any] | None = None,
) -> tuple[Any, SchemaReport]:
    config = config or {}
    report = SchemaReport()
    default_sample_id = config.get("default_sample_id")
    default_condition = config.get("default_condition")

    if hasattr(data, "mod") and isinstance(getattr(data, "mod"), dict):
        for modality_name, modality in list(data.mod.items()):
            fixed_modality, modality_report = validate_and_fix_schema(
                modality,
                {
                    "default_sample_id": default_sample_id or modality_name,
                    "default_condition": default_condition,
                },
            )
            data.mod[modality_name] = fixed_modality
            report.issues.extend(modality_report.issues)
            report.applied_fixes.extend(modality_report.applied_fixes)

        if hasattr(data, "obs"):
            data.obs = _validate_obs_or_var(
                _ensure_dataframe(data.obs, default_index_prefix="cell"),
                location="obs",
                report=report,
                default_sample_id=default_sample_id,
                default_condition=default_condition,
            )
        if hasattr(data, "uns"):
            data.uns = _replace_mapping(data.uns, _sanitize_uns(data.uns or {}, report, "uns"))
        return data, report

    obs = _ensure_dataframe(getattr(data, "obs", None), default_index_prefix="cell")
    var = _ensure_dataframe(getattr(data, "var", None), default_index_prefix="feature")

    obs = _validate_obs_or_var(
        obs,
        location="obs",
        report=report,
        default_sample_id=default_sample_id,
        default_condition=default_condition,
    )
    var = _validate_obs_or_var(
        var,
        location="var",
        report=report,
        default_sample_id=default_sample_id,
        default_condition=default_condition,
    )

    expected_obs = len(obs)
    expected_var = len(var)

    layers = dict(getattr(data, "layers", {}) or {})
    cleaned_layers: dict[str, Any] = {}
    for key, value in layers.items():
        shape = _shape_of(value)
        if shape is not None and shape != (expected_obs, expected_var):
            issue = SchemaIssue(
                location=f"layers.{key}",
                severity="warning",
                message=f"Shape {shape} does not match expected {(expected_obs, expected_var)}.",
                suggestion="Drop or rebuild the layer so it matches obs x var.",
            )
            report.issues.append(issue)
            report.applied_fixes.append(f"Dropped layers.{key} because of a shape mismatch")
            continue
        cleaned_layers[key] = value

    obsm = dict(getattr(data, "obsm", {}) or {})
    cleaned_obsm = _validate_layers_or_obsm(
        container=obsm,
        expected_rows=expected_obs,
        report=report,
        location="obsm",
    )

    uns = _sanitize_uns(getattr(data, "uns", {}) or {}, report, "uns")

    data.obs = obs
    data.var = var
    data.layers = _replace_mapping(getattr(data, "layers", {}), cleaned_layers)
    data.obsm = _replace_mapping(getattr(data, "obsm", {}), cleaned_obsm)
    data.uns = _replace_mapping(getattr(data, "uns", {}), uns)
    return data, report


validate_schema = validate_and_fix_schema


def write_schema_report(report: SchemaReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
