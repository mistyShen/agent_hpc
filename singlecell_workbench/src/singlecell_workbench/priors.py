from __future__ import annotations

import importlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from singlecell_workbench.config import dump_config
from singlecell_workbench.provenance import sha256_file


def fetch_decoupler_priors(
    output_dir: Path,
    *,
    organism: str = "human",
    license_name: str = "academic",
    pathway_top: int | float = 500,
    pathway_thr_padj: float = 0.05,
    remove_complexes: bool = False,
    config_base_dir: Path = Path("config"),
    verbose: bool = False,
) -> dict[str, Any]:
    display_output_dir = Path(output_dir)
    resolved_output_dir = display_output_dir.resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)

    try:
        decoupler = importlib.import_module("decoupler")
    except Exception as exc:  # pragma: no cover - runtime dependency path
        raise RuntimeError(f"decoupler could not be imported: {exc}") from exc

    progeny = decoupler.op.progeny(
        organism=organism,
        top=pathway_top,
        thr_padj=pathway_thr_padj,
        license=license_name,
        verbose=verbose,
    )
    collectri = decoupler.op.collectri(
        organism=organism,
        remove_complexes=remove_complexes,
        license=license_name,
        verbose=verbose,
    )

    pathway_path = resolved_output_dir / "progeny.tsv"
    tf_path = resolved_output_dir / "collectri.tsv"
    manifest_path = resolved_output_dir / "manifest.json"
    config_snippet_path = resolved_output_dir / "stats_config.yaml"

    progeny.to_csv(pathway_path, sep="\t", index=False)
    collectri.to_csv(tf_path, sep="\t", index=False)

    config_snippet = {
        "stats": {
            "decoupler": {
                "enabled": True,
                "runner": "mlm",
                "min_targets": 3,
                "pathway_network": _path_for_config(pathway_path, config_base_dir),
                "tf_network": _path_for_config(tf_path, config_base_dir),
            }
        }
    }
    dump_config(config_snippet, config_snippet_path)

    manifest = {
        "source": "decoupler_official_wrappers",
        "retrieval_timestamp": datetime.now(timezone.utc).isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decoupler_version": getattr(decoupler, "__version__", "unknown"),
        "organism": organism,
        "license": license_name,
        "gene_identifier_namespace": "gene_symbol",
        "config_base_dir": str(config_base_dir),
        "pathway": {
            "resource": "PROGENy",
            "path": str(pathway_path),
            "rows": int(len(progeny)),
            "row_count": int(len(progeny)),
            "columns": [str(column) for column in progeny.columns],
            "column_schema": [str(column) for column in progeny.columns],
            "gene_identifier_namespace": "gene_symbol",
            "sha256": sha256_file(pathway_path),
            "top": pathway_top,
            "thr_padj": pathway_thr_padj,
        },
        "tf": {
            "resource": "CollecTRI",
            "path": str(tf_path),
            "rows": int(len(collectri)),
            "row_count": int(len(collectri)),
            "columns": [str(column) for column in collectri.columns],
            "column_schema": [str(column) for column in collectri.columns],
            "gene_identifier_namespace": "gene_symbol",
            "sha256": sha256_file(tf_path),
            "remove_complexes": remove_complexes,
        },
        "config_snippet_path": str(config_snippet_path),
    }
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    return manifest


def _path_for_config(path: Path, config_base_dir: Path) -> str:
    resolved_path = path.resolve()
    resolved_config_base = (Path.cwd() / config_base_dir).resolve() if not config_base_dir.is_absolute() else config_base_dir
    try:
        relative = os.path.relpath(resolved_path, start=resolved_config_base)
    except ValueError:
        return str(resolved_path)
    return Path(relative).as_posix()
