from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from ultimate.batch import BATCH_NON_DELIVERY_REASON, prepare_batch
from ultimate.cli import main
from ultimate.config import dump_yaml


def test_prepare_batch_scaffolds_two_jobs_without_copying_raw_data(tmp_path: Path) -> None:
    raw_dir = tmp_path / "customer_raw"
    raw_dir.mkdir()
    raw_counts = raw_dir / "raw_counts.tsv"
    raw_counts.write_text("gene\tS1\tS2\nG1\t10\t20\n", encoding="utf-8")
    samplesheet = tmp_path / "samples.tsv"
    samplesheet.write_text("sample_id\tcondition\tinput_path\nS1\tcontrol\t/shared/raw/S1.fastq.gz\n", encoding="utf-8")
    request = tmp_path / "request.yaml"
    request.write_text("analysis_presets:\n  - basic\n", encoding="utf-8")

    config_a = _write_project_config(tmp_path / "config_a.yaml", raw_counts)
    config_b = _write_project_config(tmp_path / "config_b.yaml", raw_counts)
    root = tmp_path / "shared" / "shen" / "2026" / "ultimate"
    batch_path = tmp_path / "batch.yaml"
    batch_path.write_text(
        yaml.safe_dump(
            {
                "batch_id": "pytest_batch",
                "root": str(root),
                "jobs": [
                    {"job_id": "ORDER_A", "config": str(config_a), "request": str(request), "samplesheet": str(samplesheet)},
                    {"job_id": "ORDER_B", "config": str(config_b), "request": str(request), "samplesheet": str(samplesheet)},
                    {"job_id": "ORDER_BLOCKED", "config": str(tmp_path / "missing.yaml")},
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    manifest = prepare_batch(batch_path=batch_path)

    assert manifest["jobs_total"] == 3
    assert manifest["jobs_ready"] == 2
    assert manifest["jobs_blocked"] == 1
    assert manifest["delivery_allowed"] is False
    assert manifest["non_delivery_reason"] == BATCH_NON_DELIVERY_REASON
    assert manifest["policy"]["runs_analysis"] is False
    assert manifest["policy"]["submits_slurm"] is False
    assert manifest["policy"]["remote_commands"] is False

    for job_id in ("ORDER_A", "ORDER_B"):
        job_dir = root / "jobs" / job_id
        assert job_dir.is_dir()
        assert (job_dir / "config" / "project.yaml").exists()
        assert not list(job_dir.rglob(raw_counts.name))
        approval = json.loads((job_dir / "config" / "production_approval.json").read_text(encoding="utf-8"))
        assert approval["approved"] is False
        assert approval["delivery_scope"] == "internal_rehearsal"

    blocked_dir = root / "jobs" / "ORDER_BLOCKED"
    assert not blocked_dir.exists()
    rows = _read_summary(Path(manifest["artifacts"]["summary_tsv"]))
    assert [row["status"] for row in rows] == ["ready", "ready", "blocked"]
    assert {row["scaffold_status"] for row in rows} == {"scaffolded", "not_scaffolded"}
    assert all(row["delivery_allowed"] == "false" for row in rows)
    assert all(row["non_delivery_reason"] == BATCH_NON_DELIVERY_REASON for row in rows)
    assert rows[0]["approval_status"] == "template_pending_approval"
    assert "config does not exist" in rows[2]["blockers"]
    report = Path(manifest["artifacts"]["report_md"]).read_text(encoding="utf-8")
    assert "delivery_allowed: false" in report
    assert "no analysis, Slurm submission, or remote command is run" in report


def test_prepare_batch_cli_scaffolds_jobs(tmp_path: Path) -> None:
    from click.testing import CliRunner

    raw_counts = tmp_path / "raw_counts.tsv"
    raw_counts.write_text("gene\tS1\nG1\t5\n", encoding="utf-8")
    config_path = _write_project_config(tmp_path / "config.yaml", raw_counts)
    root = tmp_path / "shared" / "shen" / "2026" / "ultimate"
    batch_path = tmp_path / "batch.yaml"
    batch_path.write_text(
        yaml.safe_dump({"batch_id": "cli_batch", "root": str(root), "jobs": [{"job_id": "CLI001", "config": str(config_path)}]}),
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, ["prepare-batch", "--batch", str(batch_path)])

    assert result.exit_code == 0, result.output
    manifest = json.loads(result.output)
    assert manifest["analysis_level"] == "smoke_backend"
    assert manifest["delivery_allowed"] is False
    assert (root / "jobs" / "CLI001" / "config" / "project.yaml").exists()


def test_prepare_batch_supports_json_and_explicit_customer_approval_without_delivery(tmp_path: Path) -> None:
    raw_counts = tmp_path / "raw_counts.tsv"
    raw_counts.write_text("gene\tS1\nG1\t5\n", encoding="utf-8")
    config_path = _write_project_config(tmp_path / "config.yaml", raw_counts)
    root = tmp_path / "shared" / "shen" / "2026" / "ultimate"
    batch_path = tmp_path / "batch.json"
    batch_path.write_text(
        json.dumps(
            {
                "batch_id": "json_batch",
                "root": str(root),
                "jobs": [
                    {
                        "job_id": "JSON001",
                        "config": str(config_path),
                        "approval": {
                            "approved": True,
                            "approved_by": "pytest",
                            "approved_at": "2026-06-11T00:00:00Z",
                            "delivery_scope": "customer_delivery",
                            "reason": "pytest explicit approval metadata only",
                        },
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest = prepare_batch(batch_path=batch_path)

    assert manifest["jobs_ready"] == 1
    assert manifest["delivery_allowed"] is False
    assert manifest["non_delivery_reason"] == BATCH_NON_DELIVERY_REASON
    rows = _read_summary(Path(manifest["artifacts"]["summary_tsv"]))
    assert rows[0]["status"] == "ready"
    assert rows[0]["approval_status"] == "customer_approved"
    assert rows[0]["delivery_allowed"] == "false"
    approval = json.loads((root / "jobs" / "JSON001" / "config" / "production_approval.json").read_text(encoding="utf-8"))
    assert approval["approved"] is True
    assert approval["delivery_scope"] == "customer_delivery"


def _write_project_config(path: Path, raw_counts: Path) -> Path:
    return dump_yaml(
        {
            "project": {
                "name": path.stem,
                "organism": "human",
                "output_dir": "../runs/placeholder",
                "server_root": "/shared/shen/2026/ultimate",
            },
            "modules": {
                "rnaseq": {
                    "enabled": True,
                    "raw": {"input_path": str(raw_counts)},
                }
            },
        },
        path,
    )


def _read_summary(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))
