from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import yaml

from singlecell_workbench.sample_contract import ORDERED_SAMPLE_FIELDS, sample_spec_to_record


def sha256_file(path: Path | None) -> str | None:
    if path is None or not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest_document(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    if path.suffix.lower() in {".yaml", ".yml"}:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    else:
        payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def write_samplesheet_snapshot(sample_specs: list[Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(ORDERED_SAMPLE_FIELDS), delimiter="\t")
        writer.writeheader()
        for sample_spec in sample_specs:
            writer.writerow(sample_spec_to_record(sample_spec))
    return path


def detect_git_context(cwd: Path) -> dict[str, Any]:
    def _run(args: list[str]) -> str | None:
        try:
            completed = subprocess.run(
                args,
                cwd=cwd,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception:
            return None
        return completed.stdout.strip() or None

    root = _run(["git", "rev-parse", "--show-toplevel"])
    commit = _run(["git", "rev-parse", "HEAD"])
    dirty_output = _run(["git", "status", "--porcelain"])
    if root is None or commit is None:
        return {
            "available": False,
            "root": None,
            "commit": None,
            "dirty": None,
        }
    return {
        "available": True,
        "root": root,
        "commit": commit,
        "dirty": bool(dirty_output),
    }
