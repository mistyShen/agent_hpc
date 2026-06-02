from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from ultimate.config import enabled_modules, load_samples, output_dir
from ultimate.constants import MODULE_SPECS


def run_preflight(config: dict[str, Any], *, write: bool = True) -> dict[str, Any]:
    out_dir = output_dir(config)
    samples = load_samples(config)
    module_reports = []
    for module_name in enabled_modules(config):
        module_reports.append(_check_module(config, samples, module_name))

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": config.get("project", {}),
        "output_dir": str(out_dir),
        "organism": config.get("project", {}).get("organism"),
        "samples": {
            "n_rows": int(samples.shape[0]),
            "columns": list(samples.columns),
            "missing_required_columns": _missing_columns(samples, ("sample_id", "condition")),
        },
        "modules": module_reports,
        "tool_checks": _global_tool_checks(),
        "status": _overall_status(module_reports, samples),
    }
    if write:
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "preflight_manifest.json"
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        manifest["manifest_path"] = str(path)
    return manifest


def _check_module(config: dict[str, Any], samples: pd.DataFrame, module_name: str) -> dict[str, Any]:
    spec = MODULE_SPECS[module_name]
    module_cfg = (config.get("modules") or {}).get(module_name) or {}
    input_matrix = module_cfg.get("input_matrix")
    samplesheet = module_cfg.get("samplesheet") or (config.get("samples") or {}).get("samplesheet")
    checks = {
        "input_matrix": _path_check(input_matrix),
        "samplesheet": _path_check(samplesheet),
        "required_sample_columns": _missing_columns(samples, spec.required_columns),
        "optional_commands": {cmd: bool(shutil.which(cmd)) for cmd in spec.optional_commands},
        "optional_r_packages": _r_package_checks(spec.optional_r_packages),
    }
    warnings = []
    if checks["required_sample_columns"]:
        warnings.append("missing_required_sample_columns")
    if not checks["input_matrix"]["exists"]:
        warnings.append("input_matrix_missing_or_not_configured")
    missing_commands = [cmd for cmd, ok in checks["optional_commands"].items() if not ok]
    if missing_commands:
        warnings.append("optional_commands_missing:" + ",".join(missing_commands))
    return {
        "module": module_name,
        "title_cn": spec.title_cn,
        "input_kind": spec.input_kind,
        "checks": checks,
        "warnings": warnings,
        "status": "ready_with_warnings" if warnings else "ready",
    }


def _path_check(value: Any) -> dict[str, Any]:
    if value is None:
        return {"path": None, "exists": False, "kind": None}
    path = Path(value)
    return {
        "path": str(path),
        "exists": path.exists(),
        "kind": "dir" if path.is_dir() else "file" if path.is_file() else None,
    }


def _missing_columns(frame: pd.DataFrame, required: tuple[str, ...]) -> list[str]:
    if frame.empty:
        return list(required)
    return [column for column in required if column not in frame.columns]


def _global_tool_checks() -> dict[str, Any]:
    python_packages = ["click", "yaml", "pandas", "numpy", "matplotlib", "seaborn", "jinja2"]
    commands = ["snakemake", "Rscript", "conda", "mamba", "sbatch"]
    return {
        "commands": {cmd: bool(shutil.which(cmd)) for cmd in commands},
        "python_packages": {pkg: importlib.util.find_spec(pkg) is not None for pkg in python_packages},
    }


def _r_package_checks(packages: tuple[str, ...]) -> dict[str, str]:
    if not shutil.which("Rscript"):
        return {pkg: "not_checked:Rscript_missing" for pkg in packages}
    script = "cat(paste(installed.packages()[, 'Package'], collapse='\\n'))"
    try:
        completed = subprocess.run(
            ["Rscript", "-e", script],
            check=False,
            text=True,
            capture_output=True,
            timeout=20,
        )
    except Exception as exc:
        return {pkg: f"not_checked:{type(exc).__name__}" for pkg in packages}
    installed = set(completed.stdout.splitlines())
    return {pkg: "available" if pkg in installed else "missing_optional" for pkg in packages}


def _overall_status(module_reports: list[dict[str, Any]], samples: pd.DataFrame) -> str:
    if samples.empty:
        return "blocked:no_samples"
    if any(report["checks"]["required_sample_columns"] for report in module_reports):
        return "blocked:sample_schema"
    if any("input_matrix_missing_or_not_configured" in report["warnings"] for report in module_reports):
        return "ready_with_warnings"
    return "ready"
