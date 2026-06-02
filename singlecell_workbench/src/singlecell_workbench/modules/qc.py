from __future__ import annotations

from collections.abc import Mapping
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:  # pragma: no cover - import-time safety in minimal environments.
    from singlecell_workbench.types import SingleCellData


_DEFAULT_QC_PATTERNS: dict[str, tuple[str, ...]] = {
    "mt": ("MT-", "mt-"),
    "ribo": ("RPL", "RPS", "rpl", "rps"),
    "hb": ("HB", "HBA", "HBB", "hb"),
}

_MIRRORED_COLUMNS = (
    "total_counts",
    "n_genes_by_counts",
    "log1p_total_counts",
    "log1p_n_genes_by_counts",
    "pct_counts_mt",
    "pct_counts_ribo",
    "pct_counts_hb",
)


def run_qc(
    data: "SingleCellData",
    output_dir: Path,
    qc_config: dict[str, Any] | None = None,
) -> tuple["SingleCellData", dict[str, Any]]:
    qc_config = dict(qc_config or {})
    qc_dir = Path(output_dir) / "qc"
    qc_dir.mkdir(parents=True, exist_ok=True)

    data_kind = "MuData" if _is_mudata(data) else "AnnData"
    rna_modality_name, rna_data = _resolve_rna_container(data, qc_config)

    qc_vars = _ensure_qc_var_flags(rna_data, qc_config)
    scanpy_module, qc_backend = _import_scanpy_compatible()
    qc_metrics_config = _build_qc_metrics_kwargs(rna_data, qc_config, qc_vars)
    scanpy_module.pp.calculate_qc_metrics(rna_data, **qc_metrics_config)

    if data_kind == "MuData":
        _mirror_metrics_to_mudata(data, rna_data)

    per_cell_qc = pd.DataFrame(rna_data.obs).copy()
    per_cell_qc.index.name = per_cell_qc.index.name or "cell_id"
    per_cell_qc_csv = qc_dir / "per_cell_qc.csv"
    per_cell_qc.to_csv(per_cell_qc_csv)

    solo_manifest = _run_optional_solo(rna_data, qc_config)
    scar_manifest = _run_optional_scar(rna_data, qc_config)

    manifest: dict[str, Any] = {
        "module": "qc",
        "data_kind": data_kind,
        "rna_modality": rna_modality_name,
        "output_dir": str(qc_dir),
        "per_cell_qc_csv": str(per_cell_qc_csv),
        "qc_backend": qc_backend,
        "qc_metrics": {
            "qc_vars": list(qc_vars),
            "percent_top": qc_metrics_config.get("percent_top"),
            "log1p": qc_metrics_config.get("log1p", True),
        },
        "mirrored_columns": [
            column for column in _MIRRORED_COLUMNS if column in getattr(data, "obs", pd.DataFrame()).columns
        ]
        if data_kind == "MuData"
        else [],
        "solo": solo_manifest,
        "scar": scar_manifest,
        "schema_notes": _schema_notes(rna_data, qc_vars),
    }

    manifest_path = qc_dir / "manifest.json"
    manifest_path.write_text(json.dumps(_jsonable(manifest), indent=2, sort_keys=True), encoding="utf-8")
    manifest["manifest_json"] = str(manifest_path)

    return data, manifest


def _import_scanpy_compatible() -> tuple[Any, str]:
    try:
        return importlib.import_module("scanpy"), "scanpy"
    except ModuleNotFoundError:
        return SimpleNamespace(pp=SimpleNamespace(calculate_qc_metrics=_calculate_qc_metrics_fallback)), "fallback"


def _import_scanpy() -> Any:
    return _import_scanpy_compatible()[0]


def _calculate_qc_metrics_fallback(
    adata: Any,
    *,
    qc_vars: list[str] | None = None,
    percent_top: list[int] | None = None,
    log1p: bool = True,
    inplace: bool = True,
) -> Any:
    del percent_top, inplace
    matrix = getattr(adata, "X", None)
    if matrix is None:
        raise RuntimeError("QC fallback requires an X matrix on the AnnData-like object")
    if hasattr(matrix, "tocsr"):
        import numpy as np

        matrix = matrix.tocsr()
        total_counts = np.asarray(matrix.sum(axis=1)).astype(float).reshape(-1)
        n_genes_by_counts = np.asarray((matrix > 0).sum(axis=1)).astype(float).reshape(-1)
    else:
        import numpy as np

        dense = np.asarray(matrix)
        total_counts = dense.sum(axis=1).astype(float)
        n_genes_by_counts = (dense > 0).sum(axis=1).astype(float)
    adata.obs["total_counts"] = total_counts
    adata.obs["n_genes_by_counts"] = n_genes_by_counts
    if log1p:
        adata.obs["log1p_total_counts"] = pd.Series(total_counts).map(_safe_log1p).to_numpy()
        adata.obs["log1p_n_genes_by_counts"] = pd.Series(n_genes_by_counts).map(_safe_log1p).to_numpy()

    for qc_var in qc_vars or []:
        if not hasattr(adata, "var") or qc_var not in adata.var.columns:
            continue
        selector = pd.Series(adata.var[qc_var]).astype(bool).to_numpy()
        if hasattr(matrix, "tocsr"):
            import numpy as np

            subset_counts = np.asarray(matrix[:, selector].sum(axis=1)).astype(float).reshape(-1)
        else:
            subset_counts = dense[:, selector].sum(axis=1).astype(float)
        adata.obs[f"pct_counts_{qc_var}"] = _safe_pct(subset_counts, total_counts)
    return adata


def _safe_log1p(value: float) -> float:
    import math

    return math.log1p(float(value))


def _safe_pct(numerator: Any, denominator: Any) -> list[float]:
    values: list[float] = []
    for num, den in zip(list(numerator), list(denominator)):
        if float(den) == 0.0:
            values.append(0.0)
        else:
            values.append(float(num) / float(den) * 100.0)
    return values


def _is_mudata(data: Any) -> bool:
    return hasattr(data, "mod") and isinstance(getattr(data, "mod"), Mapping)


def _resolve_rna_container(data: Any, qc_config: Mapping[str, Any]) -> tuple[str, Any]:
    if not _is_mudata(data):
        return "adata", data

    modality_name = str(qc_config.get("rna_modality", "rna"))
    candidates = [modality_name, modality_name.lower(), modality_name.upper()]
    for candidate in candidates:
        if candidate in data.mod:
            return candidate, data.mod[candidate]

    if len(data.mod) == 1:
        only_name = next(iter(data.mod))
        return only_name, data.mod[only_name]

    raise KeyError(
        f"RNA modality {modality_name!r} was not found in MuData modalities: {sorted(data.mod)}"
    )


def _ensure_qc_var_flags(adata: Any, qc_config: Mapping[str, Any]) -> list[str]:
    requested = qc_config.get("qc_vars")
    if requested is None:
        requested = ["mt"] if _auto_detect_qc_flag(adata, "mt") else []
    requested = list(dict.fromkeys(str(flag) for flag in requested))

    if not hasattr(adata, "var"):
        return requested

    var_frame = adata.var
    var_names = _get_var_names(adata)
    for qc_var in requested:
        if qc_var in var_frame.columns:
            continue
        inferred = _infer_qc_flag(qc_var, var_names, qc_config)
        var_frame[qc_var] = inferred

    return requested


def _auto_detect_qc_flag(adata: Any, qc_var: str) -> bool:
    return _infer_qc_flag(qc_var, _get_var_names(adata), {}).any()


def _infer_qc_flag(qc_var: str, var_names: pd.Index, qc_config: Mapping[str, Any]) -> pd.Series:
    prefixes = qc_config.get("qc_var_prefixes", {}).get(qc_var)
    if prefixes is None:
        prefixes = _DEFAULT_QC_PATTERNS.get(qc_var, ())
    elif isinstance(prefixes, str):
        prefixes = (prefixes,)
    else:
        prefixes = tuple(prefixes)

    if not prefixes:
        return pd.Series(False, index=var_names)

    mask = pd.Series(False, index=var_names)
    var_text = pd.Series(var_names.astype(str), index=var_names)
    for prefix in prefixes:
        mask |= var_text.str.startswith(prefix)
    return mask.astype(bool)


def _get_var_names(adata: Any) -> pd.Index:
    if hasattr(adata, "var_names"):
        return pd.Index(getattr(adata, "var_names"))
    if hasattr(adata, "var") and hasattr(adata.var, "index"):
        return pd.Index(adata.var.index)
    return pd.Index([])


def _build_qc_metrics_kwargs(adata: Any, qc_config: Mapping[str, Any], qc_vars: list[str]) -> dict[str, Any]:
    percent_top = qc_config.get("percent_top", (50, 100, 200, 500))
    percent_top = _sanitize_percent_top(percent_top, getattr(adata, "n_vars", len(_get_var_names(adata))))
    kwargs: dict[str, Any] = {
        "qc_vars": qc_vars,
        "percent_top": percent_top,
        "log1p": bool(qc_config.get("log1p", True)),
        "inplace": True,
    }
    return kwargs


def _sanitize_percent_top(percent_top: Any, n_vars: int) -> list[int] | None:
    if percent_top is None:
        return None
    values = []
    for value in percent_top:
        try:
            int_value = int(value)
        except (TypeError, ValueError):
            continue
        if 0 < int_value <= n_vars:
            values.append(int_value)
    if not values:
        return None
    return sorted(dict.fromkeys(values))


def _mirror_metrics_to_mudata(mudata: Any, rna_data: Any) -> None:
    if not hasattr(mudata, "obs"):
        return
    rna_obs = pd.DataFrame(rna_data.obs).copy()
    if getattr(mudata.obs, "index", None) is None or len(mudata.obs.index) == 0:
        mudata.obs = pd.DataFrame(index=rna_obs.index)
    else:
        mudata.obs = mudata.obs.reindex(rna_obs.index).copy()

    for column in _MIRRORED_COLUMNS:
        if column in rna_obs.columns:
            mudata.obs[column] = rna_obs[column].values


def _run_optional_solo(adata: Any, qc_config: Mapping[str, Any]) -> dict[str, Any]:
    solo_config = dict(qc_config.get("solo", {}))
    if not solo_config.get("enabled", False):
        return _skipped_manifest("solo", "disabled", available=None)

    available = _module_available("scvi")
    if not available:
        return _skipped_manifest("solo", "dependency_missing: scvi-tools", available=False)

    runner = solo_config.get("runner")
    if callable(runner):
        result = runner(adata, solo_config)
        return _completed_manifest("solo", result, available=True)

    model = solo_config.get("model") or getattr(getattr(adata, "uns", {}), "get", lambda *_: None)("scvi_model")
    if model is None:
        return _skipped_manifest("solo", "missing_scvi_model", available=True)

    try:
        scvi_external = importlib.import_module("scvi.external")
        solo_cls = getattr(scvi_external, "SOLO")
        solo = solo_cls.from_scvi_model(model)
        solo.train(**solo_config.get("train_kwargs", {}))
        prediction = solo.predict(**solo_config.get("predict_kwargs", {}))
        _attach_optional_result(adata, "solo", prediction, solo_config)
        return _completed_manifest("solo", {"rows": len(prediction)}, available=True)
    except Exception as exc:  # pragma: no cover - depends on optional dependency behavior.
        return _failed_manifest("solo", exc, available=True)


def _run_optional_scar(adata: Any, qc_config: Mapping[str, Any]) -> dict[str, Any]:
    scar_config = dict(qc_config.get("scar", {}))
    if not scar_config.get("enabled", False):
        return _skipped_manifest("scar", "disabled", available=None)

    available = _module_available("scar")
    if not available:
        return _skipped_manifest("scar", "dependency_missing: scar", available=False)

    runner = scar_config.get("runner")
    if callable(runner):
        result = runner(adata, scar_config)
        return _completed_manifest("scar", result, available=True)

    return _skipped_manifest("scar", "no_builtin_adapter", available=True)


def _attach_optional_result(adata: Any, prefix: str, result: Any, config: Mapping[str, Any]) -> None:
    target = config.get("result_key")
    if not target:
        target = f"{prefix}_result"
    if hasattr(adata, "obs") and isinstance(result, pd.DataFrame):
        for column in result.columns:
            adata.obs[f"{target}_{column}"] = result[column].values
    elif hasattr(adata, "uns"):
        adata.uns[target] = result


def _module_available(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
    except Exception:  # pragma: no cover - optional dependency detection.
        return False
    return True


def _completed_manifest(name: str, result: Any, available: bool) -> dict[str, Any]:
    return {
        "name": name,
        "status": "completed",
        "available": available,
        "reason": None,
        "result": _jsonable(result),
    }


def _skipped_manifest(name: str, reason: str, available: bool | None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "skipped",
        "available": available,
        "reason": reason,
    }


def _failed_manifest(name: str, error: Exception, available: bool) -> dict[str, Any]:
    return {
        "name": name,
        "status": "failed",
        "available": available,
        "reason": f"{type(error).__name__}: {error}",
    }


def _schema_notes(adata: Any, qc_vars: list[str]) -> list[str]:
    notes: list[str] = []
    if not qc_vars:
        notes.append("No qc_vars were requested or inferred; calculate_qc_metrics ran without subset QC flags.")
    if hasattr(adata, "var"):
        missing = [qc_var for qc_var in qc_vars if qc_var not in adata.var.columns]
        if missing:
            notes.append(f"QC flags missing before execution and were inferred when possible: {missing}")
    return notes


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.DataFrame):
        return value.to_dict(orient="list")
    if isinstance(value, pd.Series):
        return value.to_list()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(_jsonable(item) for item in value)
    if isinstance(value, SimpleNamespace):
        return _jsonable(vars(value))
    if callable(value):
        return getattr(value, "__name__", repr(value))
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            return value.item()
        except Exception:  # pragma: no cover - defensive.
            return repr(value)
    return value
