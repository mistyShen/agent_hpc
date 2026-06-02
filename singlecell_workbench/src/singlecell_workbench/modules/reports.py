from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

try:  # pragma: no cover - optional scientific dependency
    from singlecell_workbench.types import SingleCellData
except Exception:  # pragma: no cover - test environments may omit anndata/mudata
    SingleCellData = Any  # type: ignore[assignment]


_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"


def build_reports(
    data: SingleCellData,
    output_dir: Path,
    schema_manifest: dict[str, Any],
    qc_manifest: dict[str, Any],
    annotation_manifest: dict[str, Any],
    stats_manifest: dict[str, Any],
    report_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report_config = dict(report_config or {})
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    summary = _build_summary(
        data=data,
        schema_manifest=schema_manifest,
        qc_manifest=qc_manifest,
        annotation_manifest=annotation_manifest,
        stats_manifest=stats_manifest,
        report_config=report_config,
    )
    context = {
        "title": summary["title"],
        "generated_at": summary["generated_at"],
        "data": summary["data"],
        "schema": summary["schema"],
        "qc": summary["qc"],
        "annotation": summary["annotation"],
        "stats": summary["stats"],
        "dependency_skips": summary["dependency_skips"],
        "artifacts": summary["artifacts"],
        "methods_sections": summary["methods_sections"],
    }

    html_path = reports_dir / "report.html"
    methods_path = reports_dir / "methods.md"
    manifest_path = reports_dir / "report_manifest.json"

    html_path.write_text(_render_template("report.html.j2", context), encoding="utf-8")
    methods_path.write_text(_render_template("methods.md.j2", context), encoding="utf-8")

    manifest = {
        "title": summary["title"],
        "generated_at": summary["generated_at"],
        "report_dir": str(reports_dir),
        "html_report": str(html_path),
        "methods_draft": str(methods_path),
        "manifest_path": str(manifest_path),
        "data": summary["data"],
        "schema": summary["schema"],
        "qc": summary["qc"],
        "annotation": summary["annotation"],
        "stats": summary["stats"],
        "dependency_skips": summary["dependency_skips"],
        "artifacts": summary["artifacts"],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _build_summary(
    *,
    data: SingleCellData,
    schema_manifest: dict[str, Any],
    qc_manifest: dict[str, Any],
    annotation_manifest: dict[str, Any],
    stats_manifest: dict[str, Any],
    report_config: dict[str, Any],
) -> dict[str, Any]:
    title = str(report_config.get("title", "Single-cell Workbench Report"))
    generated_at = datetime.now(timezone.utc).isoformat()
    data_summary = _summarize_data(data)
    schema_summary = _summarize_manifest("schema", schema_manifest)
    qc_summary = _summarize_manifest("qc", qc_manifest)
    annotation_summary = _summarize_manifest("annotation", annotation_manifest)
    stats_summary = _summarize_manifest("stats", stats_manifest)
    dependency_skips = _collect_dependency_skips(
        schema_manifest,
        qc_manifest,
        annotation_manifest,
        stats_manifest,
    )
    artifacts = _collect_artifacts(
        schema_manifest,
        qc_manifest,
        annotation_manifest,
        stats_manifest,
    )
    methods_sections = _build_methods_sections(
        data_summary=data_summary,
        schema_summary=schema_summary,
        qc_summary=qc_summary,
        annotation_summary=annotation_summary,
        stats_summary=stats_summary,
        dependency_skips=dependency_skips,
        artifacts=artifacts,
    )
    return {
        "title": title,
        "generated_at": generated_at,
        "data": data_summary,
        "schema": schema_summary,
        "qc": qc_summary,
        "annotation": annotation_summary,
        "stats": stats_summary,
        "dependency_skips": dependency_skips,
        "artifacts": artifacts,
        "methods_sections": methods_sections,
    }


def _summarize_data(data: SingleCellData) -> dict[str, Any]:
    if _is_mudata_like(data):
        modalities = {}
        for name, modality in data.mod.items():
            modalities[name] = {
                "kind": "AnnData",
                "n_obs": int(modality.n_obs),
                "n_vars": int(modality.n_vars),
                "obs_columns": _sorted_strings(modality.obs.columns),
                "var_columns": _sorted_strings(modality.var.columns),
                "layers": _sorted_strings(getattr(modality, "layers", None)),
                "obsm": _sorted_strings(getattr(modality, "obsm", None)),
                "uns": _sorted_strings(getattr(modality, "uns", None)),
            }
        return {
            "kind": "MuData",
            "n_obs": int(data.n_obs),
            "n_vars": int(data.n_vars),
            "modalities": modalities,
            "obs_columns": _sorted_strings(data.obs.columns),
            "var_columns": _sorted_strings(data.var.columns),
            "layers": _sorted_strings(getattr(data, "layers", None)),
            "obsm": _sorted_strings(getattr(data, "obsm", None)),
            "uns": _sorted_strings(getattr(data, "uns", None)),
        }

    if _is_anndata_like(data):
        return {
            "kind": "AnnData",
            "n_obs": int(data.n_obs),
            "n_vars": int(data.n_vars),
            "obs_columns": _sorted_strings(data.obs.columns),
            "var_columns": _sorted_strings(data.var.columns),
            "layers": _sorted_strings(getattr(data, "layers", None)),
            "obsm": _sorted_strings(getattr(data, "obsm", None)),
            "uns": _sorted_strings(getattr(data, "uns", None)),
        }

    return {
        "kind": type(data).__name__,
        "summary": "Unsupported data object for report rendering.",
    }


def _summarize_manifest(name: str, manifest: dict[str, Any]) -> dict[str, Any]:
    manifest = _to_jsonable(manifest)
    return {
        "name": name,
        "status": manifest.get("status")
        or manifest.get("state")
        or ("skipped" if manifest.get("skipped") else "complete"),
        "decisions": _collect_decisions(manifest),
        "artifacts": _collect_artifacts(manifest),
        "dependency_skips": _collect_dependency_skips(manifest),
        "raw": manifest,
    }


def _build_methods_sections(
    *,
    data_summary: dict[str, Any],
    schema_summary: dict[str, Any],
    qc_summary: dict[str, Any],
    annotation_summary: dict[str, Any],
    stats_summary: dict[str, Any],
    dependency_skips: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "overview": [
            f"Processed {data_summary.get('n_obs', 0)} cells and {data_summary.get('n_vars', 0)} features using {data_summary.get('kind', 'single-cell')}.",
            "The pipeline retained the canonical single-cell object in h5ad or h5mu form depending on detected modalities.",
        ],
        "schema": [
            _format_decision_line(schema_summary),
        ],
        "qc": [
            _format_decision_line(qc_summary),
            "QC uses scanpy.pp.calculate_qc_metrics and records optional SOLO / SCAR steps when they are available.",
        ],
        "annotation": [
            _format_decision_line(annotation_summary),
            "Annotation prefers scArches + scANVI and falls back to CellTypist when the preferred stack is unavailable.",
        ],
        "stats": [
            _format_decision_line(stats_summary),
            "Statistics aggregate sample x cell_type x condition summaries and can attach decoupler pathway / TF activity outputs.",
        ],
        "dependency_skips": [
            _format_dependency_skip(entry) for entry in dependency_skips
        ]
        or ["No dependency skips were recorded."],
        "artifacts": [
            _format_artifact(entry) for entry in artifacts
        ]
        or ["No artifacts were recorded."],
    }


def _render_template(template_name: str, context: dict[str, Any]) -> str:
    environment = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = environment.get_template(template_name)
    return template.render(**_to_jsonable(context))


def _collect_decisions(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(manifest, Mapping):
        return []
    decision_keys = {
        "selected_method",
        "method",
        "method_priority",
        "fallback_method",
        "fallback_label",
        "annotation_mode",
        "selected_backend",
        "selected_reason",
        "run_solo",
        "run_scar",
        "run_decoupler",
        "groupby",
        "sample_column",
        "cell_type_column",
        "condition_column",
        "modality",
        "rna_modality",
        "apply_fixes",
        "required_obs_columns",
        "top_n_genes",
        "mitochondrial_prefixes",
        "enabled",
    }
    decisions: list[dict[str, Any]] = []
    for key in decision_keys:
        if key in manifest:
            decisions.append({"key": key, "value": _to_jsonable(manifest[key])})
    for key in ("decisions", "decision", "analysis_decisions"):
        if key in manifest and isinstance(manifest[key], Sequence) and not isinstance(manifest[key], (str, bytes)):
            for item in manifest[key]:
                decisions.append({"key": key, "value": _to_jsonable(item)})
    return decisions


def _collect_artifacts(*manifests: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for manifest in manifests:
        _collect_artifacts_from_mapping(manifest, artifacts, prefix="")
    unique = []
    seen = set()
    for artifact in artifacts:
        signature = (artifact.get("key"), json.dumps(artifact.get("value"), sort_keys=True))
        if signature not in seen:
            seen.add(signature)
            unique.append(artifact)
    return unique


def _collect_artifacts_from_mapping(
    manifest: Any,
    artifacts: list[dict[str, Any]],
    *,
    prefix: str,
) -> None:
    if not isinstance(manifest, Mapping):
        return
    for key, value in manifest.items():
        path_key = f"{prefix}.{key}" if prefix else str(key)
        if key in {"artifact_paths", "artifacts", "paths"} and isinstance(value, Mapping):
            for artifact_key, artifact_value in value.items():
                artifacts.append({"key": f"{path_key}.{artifact_key}", "value": _to_jsonable(artifact_value)})
        elif key.endswith("_path") or key.endswith("_paths"):
            artifacts.append({"key": path_key, "value": _to_jsonable(value)})
        elif isinstance(value, Mapping):
            _collect_artifacts_from_mapping(value, artifacts, prefix=path_key)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for idx, item in enumerate(value):
                _collect_artifacts_from_mapping(item, artifacts, prefix=f"{path_key}[{idx}]")


def _collect_dependency_skips(*manifests: dict[str, Any]) -> list[dict[str, Any]]:
    skips: list[dict[str, Any]] = []
    for manifest in manifests:
        if not isinstance(manifest, Mapping):
            continue
        for key in ("dependency_skips", "skipped_dependencies", "skipped_steps"):
            if key in manifest:
                value = manifest[key]
                if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                    for item in value:
                        skips.append(_normalize_skip(item, source=key))
                else:
                    skips.append(_normalize_skip(value, source=key))
        if manifest.get("skipped") and "skip_reason" in manifest:
            skips.append(
                {
                    "source": "skip_reason",
                    "dependency": manifest.get("dependency", manifest.get("module", "unknown")),
                    "reason": str(manifest.get("skip_reason")),
                }
            )
        if manifest.get("fallback_method"):
            skips.append(
                {
                    "source": "fallback_method",
                    "dependency": manifest.get("fallback_method"),
                    "reason": "Preferred method was unavailable, so the fallback path was used.",
                }
            )
    unique = []
    seen = set()
    for skip in skips:
        signature = json.dumps(skip, sort_keys=True)
        if signature not in seen:
            seen.add(signature)
            unique.append(skip)
    return unique


def _normalize_skip(value: Any, *, source: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {
            "source": source,
            "dependency": value.get("dependency")
            or value.get("name")
            or value.get("module")
            or value.get("tool")
            or "unknown",
            "reason": value.get("reason")
            or value.get("message")
            or value.get("skip_reason")
            or value.get("detail")
            or "dependency was skipped",
        }
    return {
        "source": source,
        "dependency": "unknown",
        "reason": str(value),
    }


def _format_decision_line(summary: dict[str, Any]) -> str:
    decisions = summary.get("decisions", [])
    if not decisions:
        return f"{summary.get('name', 'module').title()} reported no explicit decisions."
    pieces = [f"{item['key']}={_stringify(item['value'])}" for item in decisions[:6]]
    suffix = "" if len(decisions) <= 6 else f" and {len(decisions) - 6} more"
    return f"{summary.get('name', 'module').title()} decisions: " + "; ".join(pieces) + suffix + "."


def _format_dependency_skip(entry: dict[str, Any]) -> str:
    return f"{entry.get('dependency', 'unknown')}: {entry.get('reason', 'skipped')}"


def _format_artifact(entry: dict[str, Any]) -> str:
    return f"{entry.get('key')}: {_stringify(entry.get('value'))}"


def _sorted_strings(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, Mapping):
        iterable = values.keys()
    else:
        iterable = values
    return sorted(str(value) for value in iterable)


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return str(value)
    return json.dumps(_to_jsonable(value), ensure_ascii=False, sort_keys=True)


def _to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _to_jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [_to_jsonable(item) for item in value]
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except Exception:  # pragma: no cover - extremely defensive
            return str(value)
    return value


def _is_mudata_like(data: Any) -> bool:
    return hasattr(data, "mod") and isinstance(getattr(data, "mod"), Mapping)


def _is_anndata_like(data: Any) -> bool:
    return hasattr(data, "obs") and hasattr(data, "var") and not _is_mudata_like(data)
