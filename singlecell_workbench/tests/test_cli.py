from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from singlecell_workbench import cli
from singlecell_workbench.schema import SchemaIssue, SchemaReport


def test_make_example_command_creates_config(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli.main, ["make-example", "--output-dir", str(tmp_path / "example")])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert Path(payload["config_path"]).exists()
    assert len(payload["samples"]) == 2


def test_run_and_validate_schema_commands_emit_json(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "run.yaml"
    config_path.write_text("project_name: smoke\nsamples:\n  - sample_id: s1\n    condition: c1\n    input_path: fake\n", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "run_pipeline_from_config",
        lambda path: {"output_dir": str(path.parent / "runs" / "smoke"), "config_path": str(path)},
    )
    monkeypatch.setattr(
        cli,
        "ingest_samples",
        lambda **_: (
            object(),
            SchemaReport(issues=[SchemaIssue("obs", "warning", "duplicate", "make unique")], applied_fixes=["fixed"]),
            {"normalized_path": str(tmp_path / "normalized.h5ad")},
        ),
    )

    runner = CliRunner()
    run_result = runner.invoke(cli.main, ["run", "--config", str(config_path)])
    validate_result = runner.invoke(
        cli.main,
        [
            "validate-schema",
            "--input-path",
            str(config_path),
            "--output-dir",
            str(tmp_path / "schema"),
        ],
    )

    assert run_result.exit_code == 0
    assert json.loads(run_result.output)["output_dir"].endswith("runs/smoke")

    assert validate_result.exit_code == 0
    payload = json.loads(validate_result.output)
    assert payload["schema_report"]["applied_fixes"] == ["fixed"]


def test_fetch_priors_command_emits_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        cli,
        "fetch_decoupler_priors",
        lambda **kwargs: {
            "output_dir": str(kwargs["output_dir"]),
            "pathway": {"rows": 123},
            "tf": {"rows": 456},
        },
    )

    runner = CliRunner()
    result = runner.invoke(
        cli.main,
        [
            "fetch-priors",
            "--output-dir",
            str(tmp_path / "priors"),
            "--organism",
            "mouse",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["pathway"]["rows"] == 123
    assert payload["tf"]["rows"] == 456


def test_preflight_command_emits_json(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "run.yaml"
    config_path.write_text("project_name: smoke\nsamples:\n  - sample_id: s1\n    condition: c1\n    input_path: fake\n", encoding="utf-8")

    monkeypatch.setattr(
        cli,
        "run_preflight_from_config",
        lambda config_path, output_dir=None: {
            "status": "warn",
            "output_dir": str((output_dir or config_path.parent / 'runs' / 'smoke').resolve()),
            "preflight_report": str((config_path.parent / "preflight" / "preflight_report.json").resolve()),
        },
    )

    runner = CliRunner()
    result = runner.invoke(cli.main, ["validate-inputs", "--config", str(config_path)])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "warn"
    assert payload["preflight_report"].endswith("preflight_report.json")
