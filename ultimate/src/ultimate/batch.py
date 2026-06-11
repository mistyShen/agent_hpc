from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from ultimate.job import prepare_job


BATCH_NON_DELIVERY_REASON = "batch_scaffold_not_analysis_run"
BATCH_ROW_COLUMNS = (
    "batch_id",
    "job_id",
    "status",
    "scaffold_status",
    "job_dir",
    "config_path",
    "source_config",
    "analysis_request",
    "analysis_request_status",
    "samplesheet",
    "samplesheet_status",
    "run_mode",
    "approval_status",
    "delivery_allowed",
    "non_delivery_reason",
    "blockers",
)


def prepare_batch(
    *,
    batch_path: Path,
    root: Path | None = None,
    output_dir: Path | None = None,
    run_mode: str | None = None,
) -> dict[str, Any]:
    batch_path = batch_path.expanduser().resolve()
    batch = _load_batch(batch_path)
    base_dir = batch_path.parent
    batch_id = _clean_identifier(str(batch.get("batch_id") or batch_path.stem))
    batch_root = (root or _resolve_required_path(base_dir, batch.get("root"), field="root")).expanduser().resolve()
    batch_output_dir = (output_dir or batch_root / "batches" / batch_id).expanduser().resolve()
    batch_output_dir.mkdir(parents=True, exist_ok=True)

    jobs = _job_entries(batch)
    default_run_mode = run_mode or str(batch.get("run_mode") or "production")
    rows: list[dict[str, str]] = []
    job_manifests: list[dict[str, Any]] = []
    for index, job in enumerate(jobs, start=1):
        row, manifest = _prepare_batch_job(
            batch_id=batch_id,
            base_dir=base_dir,
            batch_root=batch_root,
            job=job,
            index=index,
            default_run_mode=default_run_mode,
        )
        rows.append(row)
        if manifest:
            job_manifests.append(manifest)

    summary_path = _write_summary_tsv(batch_output_dir / "batch_summary.tsv", rows)
    report_path = _write_report(batch_output_dir / "batch_report.md", batch_id=batch_id, rows=rows, root=batch_root)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": batch_id,
        "batch_path": str(batch_path),
        "root": str(batch_root),
        "output_dir": str(batch_output_dir),
        "jobs_total": len(rows),
        "jobs_ready": sum(1 for row in rows if row["status"] == "ready"),
        "jobs_blocked": sum(1 for row in rows if row["status"] == "blocked"),
        "delivery_allowed": False,
        "non_delivery_reason": BATCH_NON_DELIVERY_REASON,
        "analysis_level": "smoke_backend",
        "is_demo": False,
        "is_stub": False,
        "validation_evidence_allowed": False,
        "policy": {
            "scope": "batch scaffold only",
            "runs_analysis": False,
            "submits_slurm": False,
            "remote_commands": False,
            "raw_data_policy": "read_only_reference; raw data is not copied, moved, overwritten, or modified",
        },
        "artifacts": {
            "summary_tsv": str(summary_path),
            "report_md": str(report_path),
        },
        "rows": rows,
        "job_manifests": job_manifests,
    }
    manifest_path = batch_output_dir / "batch_manifest.json"
    manifest["manifest_path"] = str(manifest_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def _prepare_batch_job(
    *,
    batch_id: str,
    base_dir: Path,
    batch_root: Path,
    job: dict[str, Any],
    index: int,
    default_run_mode: str,
) -> tuple[dict[str, str], dict[str, Any] | None]:
    row = _base_row(batch_id=batch_id, job_id=str(job.get("job_id") or f"job_{index:03d}"), run_mode=str(job.get("run_mode") or default_run_mode))
    try:
        job_id = _required_text(job, "job_id")
        config_path = _resolve_required_path(base_dir, job.get("config") or job.get("config_path"), field="config")
        samplesheet = _resolve_optional_path(base_dir, job.get("samplesheet"))
        analysis_request = _resolve_optional_path(base_dir, job.get("request") or job.get("analysis_request"))
        job_run_mode = str(job.get("run_mode") or default_run_mode)
        if job_run_mode not in {"production", "interactive"}:
            raise ValueError("run_mode must be one of: production, interactive")
        if not config_path.exists():
            raise FileNotFoundError(f"config does not exist: {config_path}")

        manifest = prepare_job(
            config_path=config_path,
            job_id=job_id,
            root=batch_root,
            samplesheet=samplesheet,
            analysis_request=analysis_request,
            run_mode=job_run_mode,
        )
        _apply_explicit_approval(job, Path(manifest["approval_template"]))
        row.update(
            {
                "job_id": str(manifest["job_id"]),
                "status": "ready",
                "scaffold_status": "scaffolded",
                "job_dir": str(manifest["job_dir"]),
                "config_path": str(manifest["config_path"]),
                "source_config": str(config_path),
                "analysis_request": str(manifest.get("analysis_request") or ""),
                "analysis_request_status": str((manifest.get("analysis_request_status") or {}).get("status", "")),
                "samplesheet": str(manifest.get("samplesheet") or ""),
                "samplesheet_status": str((manifest.get("samplesheet_status") or {}).get("status", "")),
                "run_mode": str(manifest["run_mode"]),
                "approval_status": _approval_status(Path(manifest["approval_template"])),
            }
        )
        return row, manifest
    except Exception as exc:
        row.update(
            {
                "status": "blocked",
                "scaffold_status": "not_scaffolded",
                "blockers": f"{type(exc).__name__}: {exc}",
            }
        )
        return row, None


def _load_batch(batch_path: Path) -> dict[str, Any]:
    if not batch_path.exists():
        raise FileNotFoundError(f"batch file does not exist: {batch_path}")
    if batch_path.suffix.lower() == ".json":
        data = json.loads(batch_path.read_text(encoding="utf-8"))
    else:
        with batch_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise TypeError(f"Batch file must be a mapping: {batch_path}")
    return data


def _job_entries(batch: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = batch.get("jobs") or batch.get("entries")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("batch must contain a non-empty jobs or entries list")
    normalized: list[dict[str, Any]] = []
    for index, job in enumerate(jobs, start=1):
        if not isinstance(job, dict):
            raise TypeError(f"batch job entry {index} must be a mapping")
        merged = dict(job)
        if "config" not in merged and "config_path" not in merged and batch.get("config"):
            merged["config"] = batch["config"]
        normalized.append(merged)
    return normalized


def _base_row(*, batch_id: str, job_id: str, run_mode: str) -> dict[str, str]:
    row = {column: "" for column in BATCH_ROW_COLUMNS}
    row.update(
        {
            "batch_id": batch_id,
            "job_id": _clean_identifier(job_id),
            "status": "blocked",
            "scaffold_status": "not_scaffolded",
            "run_mode": run_mode,
            "delivery_allowed": "false",
            "non_delivery_reason": BATCH_NON_DELIVERY_REASON,
        }
    )
    return row


def _required_text(job: dict[str, Any], field: str) -> str:
    value = job.get(field)
    if value in (None, ""):
        raise ValueError(f"missing required job field: {field}")
    return str(value)


def _resolve_required_path(base_dir: Path, value: Any, *, field: str) -> Path:
    path = _resolve_optional_path(base_dir, value)
    if path is None:
        raise ValueError(f"missing required batch field: {field}")
    return path


def _resolve_optional_path(base_dir: Path, value: Any) -> Path | None:
    if value in (None, ""):
        return None
    candidate = Path(str(value)).expanduser()
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def _apply_explicit_approval(job: dict[str, Any], approval_path: Path) -> None:
    approval = job.get("approval") or job.get("production_approval")
    if not isinstance(approval, dict) or not approval:
        return
    payload = json.loads(approval_path.read_text(encoding="utf-8"))
    payload.update(approval)
    approval_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _approval_status(approval_path: Path) -> str:
    if not approval_path.exists():
        return "missing"
    payload = json.loads(approval_path.read_text(encoding="utf-8"))
    if payload.get("approved") is True and payload.get("delivery_scope") == "customer_delivery":
        return "customer_approved"
    if payload.get("approved") is True:
        return "approved_internal"
    return "template_pending_approval"


def _write_summary_tsv(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=BATCH_ROW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _write_report(path: Path, *, batch_id: str, rows: list[dict[str, str]], root: Path) -> Path:
    ready = sum(1 for row in rows if row["status"] == "ready")
    blocked = sum(1 for row in rows if row["status"] == "blocked")
    lines = [
        "# Ultimate batch scaffold report",
        "",
        f"- batch_id: `{batch_id}`",
        f"- root: `{root}`",
        f"- jobs_total: {len(rows)}",
        f"- jobs_ready: {ready}",
        f"- jobs_blocked: {blocked}",
        "- delivery_allowed: false",
        f"- non_delivery_reason: `{BATCH_NON_DELIVERY_REASON}`",
        "- scope: scaffold only; no analysis, Slurm submission, or remote command is run.",
        "",
        "## Jobs",
        "",
        "| job_id | status | scaffold | approval | blockers |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        blockers = row["blockers"].replace("|", "\\|")
        lines.append(f"| {row['job_id']} | {row['status']} | {row['scaffold_status']} | {row['approval_status']} | {blockers} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _clean_identifier(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in str(value).strip())
    if not cleaned:
        raise ValueError("identifier cannot be empty")
    return cleaned
