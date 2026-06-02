from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pandas as pd

from singlecell_workbench.types import SingleCellData


DEFAULT_LABEL = "unassigned"
DEFAULT_LABEL_KEY = "cell_type"
DEFAULT_CONFIDENCE_KEY = "cell_type_confidence"
DEFAULT_METHOD_KEY = "cell_type_method"
DEFAULT_PREDICTION_KEY = "cell_type_pred"
DEFAULT_SOURCE_KEY = "annotation_source"
DEFAULT_CURATED_KEY = "cell_type_curated"


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _detect_optional_dependencies() -> dict[str, bool]:
    return {
        "scarches": _module_available("scarches"),
        "scvi": _module_available("scvi"),
        "celltypist": _module_available("celltypist"),
    }


def _get_obs_frame(data: SingleCellData) -> pd.DataFrame:
    return data.obs


def _n_obs(data: SingleCellData) -> int:
    return int(data.n_obs)


def _resolve_working_modality(data: SingleCellData, annotation_config: dict[str, Any]) -> str | None:
    if not hasattr(data, "mod"):
        return None

    available_modalities = list(getattr(data, "mod", {}).keys())
    if not available_modalities:
        return None

    requested = annotation_config.get("working_modality") or annotation_config.get("modality")
    if requested and requested in available_modalities:
        return str(requested)

    if requested and requested not in available_modalities:
        return available_modalities[0]

    return available_modalities[0]


def _write_annotation_outputs(
    output_dir: Path,
    obs: pd.DataFrame,
    manifest: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    obs.to_csv(output_dir / "annotation_obs.csv")
    (output_dir / "annotation_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def annotate_cells(
    data: SingleCellData,
    output_dir: Path,
    annotation_config: dict[str, Any] | None = None,
) -> tuple[SingleCellData, dict[str, Any]]:
    annotation_config = dict(annotation_config or {})
    output_dir = Path(output_dir) / "annotation"

    label_key = str(annotation_config.get("label_key", DEFAULT_LABEL_KEY))
    confidence_key = str(annotation_config.get("confidence_key", DEFAULT_CONFIDENCE_KEY))
    method_key = str(annotation_config.get("method_key", DEFAULT_METHOD_KEY))
    prediction_key = str(annotation_config.get("prediction_key", DEFAULT_PREDICTION_KEY))
    source_key = str(annotation_config.get("source_key", DEFAULT_SOURCE_KEY))
    curated_key = str(annotation_config.get("curated_key", DEFAULT_CURATED_KEY))
    placeholder_label = str(annotation_config.get("placeholder_label", DEFAULT_LABEL))
    working_modality = _resolve_working_modality(data, annotation_config)

    available_deps = _detect_optional_dependencies()
    backend_priority = ["scarches_scanvi", "celltypist", "placeholder"]
    selected_backend = "placeholder"
    selected_reason = "deterministic fallback"
    selected_details: dict[str, Any] = {}

    attempts: list[dict[str, Any]] = []
    if available_deps["scarches"] and available_deps["scvi"]:
        attempts.append(
            {
                "backend": "scarches_scanvi",
                "status": "unavailable",
                "reason": "scArches + scVI dependencies detected, but no reference model or labels were provided",
            }
        )
    else:
        missing = [name for name, present in available_deps.items() if not present and name in {"scarches", "scvi"}]
        attempts.append(
            {
                "backend": "scarches_scanvi",
                "status": "unavailable",
                "reason": "missing optional dependencies",
                "missing_dependencies": missing or ["scarches", "scvi"],
            }
        )

    if available_deps["celltypist"]:
        attempts.append(
            {
                "backend": "celltypist",
                "status": "unavailable",
                "reason": "CellTypist detected, but no model configuration was provided",
            }
        )
    else:
        attempts.append(
            {
                "backend": "celltypist",
                "status": "unavailable",
                "reason": "missing optional dependency",
                "missing_dependencies": ["celltypist"],
            }
        )

    n_cells = _n_obs(data)
    labels = [placeholder_label] * n_cells
    confidences = [0.0] * n_cells
    methods = ["placeholder"] * n_cells

    obs = _get_obs_frame(data)
    if curated_key not in obs.columns:
        if label_key in obs.columns and obs[label_key].notna().any():
            obs[curated_key] = obs[label_key].copy()
        else:
            obs[curated_key] = pd.Series([pd.NA] * n_cells, index=obs.index, dtype="object")
    obs[prediction_key] = labels
    obs[confidence_key] = confidences
    obs[source_key] = methods
    obs[method_key] = methods
    resolved_labels = []
    for curated, predicted in zip(obs[curated_key].tolist(), labels):
        if pd.notna(curated) and str(curated).strip():
            resolved_labels.append(curated)
        else:
            resolved_labels.append(predicted)
    obs[label_key] = resolved_labels

    reference_manifest_path = annotation_config.get("reference_manifest")
    annotation_mode = "fallback" if selected_backend == "placeholder" else "reference"
    fallback_reason = selected_reason if annotation_mode == "fallback" else None

    manifest = {
        "backend_priority": backend_priority,
        "available_optional_dependencies": available_deps,
        "selected_backend": selected_backend,
        "selected_reason": selected_reason,
        "annotation_mode": annotation_mode,
        "fallback_reason": fallback_reason,
        "selected_details": selected_details,
        "working_modality": working_modality,
        "label_key": label_key,
        "confidence_key": confidence_key,
        "method_key": method_key,
        "prediction_key": prediction_key,
        "source_key": source_key,
        "curated_key": curated_key,
        "reference_manifest_path": str(reference_manifest_path) if reference_manifest_path else None,
        "placeholder_label": placeholder_label,
        "n_cells": n_cells,
        "obs_columns_written": [
            prediction_key,
            confidence_key,
            source_key,
            curated_key,
            label_key,
            method_key,
        ],
        "attempts": attempts,
        "missing_optional_dependencies": sorted(
            {
                dep
                for attempt in attempts
                for dep in attempt.get("missing_dependencies", [])
            }
        ),
        "output_files": {
            "obs_csv": str(output_dir / "annotation_obs.csv"),
            "manifest_json": str(output_dir / "annotation_manifest.json"),
        },
    }

    _write_annotation_outputs(output_dir, obs, manifest)
    return data, manifest
