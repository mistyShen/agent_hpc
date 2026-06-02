from __future__ import annotations

import json
import subprocess
from pathlib import Path
import sys

def test_minimal_example_pipeline_runs(tmp_path: Path) -> None:
    example_dir = tmp_path / "example"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "singlecell_workbench",
            "make-example",
            "--output-dir",
            str(example_dir),
        ],
        check=True,
        cwd=tmp_path,
    )

    config_path = example_dir / "run_config.yaml"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "singlecell_workbench",
            "run",
            "--config",
            str(config_path),
        ],
        check=True,
        cwd=tmp_path,
    )

    manifest_path = example_dir / "runs" / "minimal_example" / "run_manifest.json"
    with manifest_path.open("r", encoding="utf-8") as handle:
        run_manifest = json.load(handle)

    final_export = Path(run_manifest["final_export"]["path"])
    report_path = Path(run_manifest["reports"]["html_report"])
    methods_path = Path(run_manifest["reports"]["methods_draft"])
    assert final_export.exists()
    assert report_path.exists()
    assert methods_path.exists()
    assert manifest_path.exists()

    with manifest_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["schema"]["applied_fixes"] is not None
    assert Path(payload["config_snapshot_path"]).exists()
    assert Path(payload["samplesheet_snapshot_path"]).exists()
    assert "annotation_mode" in payload
    assert "git" in payload
    assert "stats_network_paths" in payload
