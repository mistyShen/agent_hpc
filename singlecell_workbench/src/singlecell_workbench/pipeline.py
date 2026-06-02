from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from singlecell_workbench.config import (
    build_sample_specs,
    dump_config,
    load_config,
    normalize_config_paths,
    resolve_output_dir,
)
from singlecell_workbench.modules.annotation import annotate_cells
from singlecell_workbench.modules.ingest import ingest_samples
from singlecell_workbench.modules.qc import run_qc
from singlecell_workbench.modules.reports import build_reports
from singlecell_workbench.modules.stats import run_statistics
from singlecell_workbench.provenance import detect_git_context, load_manifest_document, sha256_file, write_samplesheet_snapshot
from singlecell_workbench.types import SingleCellData

try:
    from mudata import MuData as _MuData
except Exception:  # pragma: no cover - optional scientific stack may be absent
    _MuData = None


def run_pipeline(config: dict[str, Any], base_dir: Path, *, config_path: Path | None = None) -> dict[str, Any]:
    output_dir = resolve_output_dir(config, base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    sample_specs = build_sample_specs(config, base_dir)
    config_snapshot_path = dump_config(config, output_dir / "config_snapshot.yaml")
    samplesheet_snapshot_path = write_samplesheet_snapshot(sample_specs, output_dir / "samplesheet_snapshot.tsv")
    git_context = detect_git_context(base_dir)
    priors_manifest = _resolve_priors_manifest(config)
    reference_manifest = _resolve_reference_manifest(config)

    data, schema_report, ingest_manifest = ingest_samples(
        sample_specs=sample_specs,
        output_dir=output_dir,
        schema_config=config.get("schema"),
    )
    data, qc_manifest = run_qc(data=data, output_dir=output_dir, qc_config=config.get("qc"))
    data, annotation_manifest = annotate_cells(
        data=data,
        output_dir=output_dir,
        annotation_config=config.get("annotation"),
    )
    stats_manifest = run_statistics(
        data=data,
        output_dir=output_dir,
        stats_config=config.get("stats"),
    )

    schema_manifest = _schema_report_to_manifest(schema_report)
    report_manifest = build_reports(
        data=data,
        output_dir=output_dir,
        schema_manifest=schema_manifest,
        qc_manifest=qc_manifest,
        annotation_manifest=annotation_manifest,
        stats_manifest=stats_manifest,
        report_config=config.get("reports"),
    )
    final_export = _write_final_data_object(data=data, output_dir=output_dir)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_name": config.get("project_name", "singlecell_workbench"),
        "output_dir": str(output_dir),
        "config_path": str(config_path) if config_path is not None else None,
        "config_snapshot_path": str(config_snapshot_path),
        "samplesheet_snapshot_path": str(samplesheet_snapshot_path),
        "git": git_context,
        "env_path": os.environ.get("CONDA_PREFIX") or os.environ.get("VIRTUAL_ENV") or sys.prefix,
        "python_version": sys.version.split()[0],
        "python_executable": sys.executable,
        "priors_manifest": priors_manifest,
        "reference_manifest": reference_manifest,
        "annotation_mode": annotation_manifest.get("annotation_mode") or annotation_manifest.get("selected_backend"),
        "annotation_fallback_reason": annotation_manifest.get("fallback_reason")
        or annotation_manifest.get("selected_reason"),
        "stats_network_paths": _resolve_stats_network_paths(config),
        "config": config,
        "ingest": ingest_manifest,
        "schema": schema_manifest,
        "qc": qc_manifest,
        "annotation": annotation_manifest,
        "stats": stats_manifest,
        "reports": report_manifest,
        "final_export": final_export,
    }
    manifest_path = output_dir / "run_manifest.json"
    manifest["run_manifest_path"] = str(manifest_path)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest


def run_pipeline_from_config(config_path: Path) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = normalize_config_paths(load_config(config_path), config_path.parent)
    return run_pipeline(config=config, base_dir=config_path.parent, config_path=config_path)


def _schema_report_to_manifest(schema_report: Any) -> dict[str, Any]:
    return {
        "issues": [asdict(issue) for issue in schema_report.issues],
        "applied_fixes": list(schema_report.applied_fixes),
    }


def _write_final_data_object(data: SingleCellData, output_dir: Path) -> dict[str, str]:
    final_dir = output_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    if _is_mudata_like(data):
        final_path = final_dir / "final_dataset.h5mu"
        data.write_h5mu(final_path)
        data_kind = "h5mu"
    else:
        final_path = final_dir / "final_dataset.h5ad"
        data.write_h5ad(final_path)
        data_kind = "h5ad"
    return {"path": str(final_path), "kind": data_kind}


def _is_mudata_like(data: Any) -> bool:
    if _MuData is not None and isinstance(data, _MuData):
        return True
    return hasattr(data, "mod") and hasattr(data, "write_h5mu")


def _resolve_stats_network_paths(config: dict[str, Any]) -> dict[str, str | None]:
    decoupler = (config.get("stats") or {}).get("decoupler") or {}
    return {
        "pathway": str(decoupler.get("pathway_network")) if decoupler.get("pathway_network") is not None else None,
        "tf": str(decoupler.get("tf_network")) if decoupler.get("tf_network") is not None else None,
    }


def _resolve_priors_manifest(config: dict[str, Any]) -> dict[str, Any]:
    network_paths = _resolve_stats_network_paths(config)
    candidates = []
    for path_value in network_paths.values():
        if not path_value:
            continue
        candidate = Path(path_value).parent / "manifest.json"
        if candidate.exists():
            candidates.append(candidate)
    manifest_path = candidates[0] if candidates else None
    payload = load_manifest_document(manifest_path)
    return {
        "path": str(manifest_path) if manifest_path is not None else None,
        "sha256": sha256_file(manifest_path),
        "summary": payload,
    }


def _resolve_reference_manifest(config: dict[str, Any]) -> dict[str, Any]:
    annotation_cfg = dict(config.get("annotation") or {})
    path_value = annotation_cfg.get("reference_manifest")
    manifest_path = Path(path_value) if path_value is not None else None
    payload = load_manifest_document(manifest_path) if manifest_path is not None else None
    return {
        "path": str(manifest_path) if manifest_path is not None else None,
        "sha256": sha256_file(manifest_path),
        "summary": payload,
    }
