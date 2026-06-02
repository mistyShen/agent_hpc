from __future__ import annotations

import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ultimate.config import dump_yaml, enabled_modules, load_config, load_samples, output_dir
from ultimate.modules import run_module
from ultimate.preflight import run_preflight
from ultimate.report import build_report


def run_pipeline_from_config(config_path: Path) -> dict[str, Any]:
    loaded = load_config(config_path)
    loaded.raw["_config_path"] = str(loaded.path)
    return run_pipeline(loaded.raw)


def run_pipeline(config: dict[str, Any]) -> dict[str, Any]:
    out_dir = output_dir(config)
    for directory in ("results/figures", "results/tables", "objects", "reports", "logs"):
        (out_dir / directory).mkdir(parents=True, exist_ok=True)
    dump_yaml(config, out_dir / "config_snapshot.yaml")
    preflight = run_preflight(config, write=True)
    samples = load_samples(config)
    module_manifests = []
    for module_name in enabled_modules(config):
        module_manifests.append(
            run_module(
                module_name=module_name,
                config=config,
                output_dir=out_dir,
                samples=samples,
            )
        )
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": config.get("project", {}),
        "output_dir": str(out_dir),
        "python": {
            "version": sys.version.split()[0],
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "preflight": preflight,
        "modules": module_manifests,
        "artifacts_root": {
            "figures": str(out_dir / "results" / "figures"),
            "tables": str(out_dir / "results" / "tables"),
            "objects": str(out_dir / "objects"),
            "reports": str(out_dir / "reports"),
            "logs": str(out_dir / "logs"),
        },
    }
    manifest_path = out_dir / "run_manifest.json"
    manifest["run_manifest_path"] = str(manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    report_manifest = build_report(out_dir)
    manifest["report"] = report_manifest
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
