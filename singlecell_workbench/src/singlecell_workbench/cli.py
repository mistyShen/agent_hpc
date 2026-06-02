from __future__ import annotations

import json
from pathlib import Path

import click

from singlecell_workbench.example_data import create_minimal_example
from singlecell_workbench.modules.ingest import ingest_samples
from singlecell_workbench.pipeline import run_pipeline_from_config
from singlecell_workbench.preflight import run_preflight_from_config
from singlecell_workbench.priors import fetch_decoupler_priors
from singlecell_workbench.types import SampleSpec


@click.group()
def main() -> None:
    """Single-cell workbench command line interface."""


@main.command("make-example")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("example_data/minimal_example"),
    show_default=True,
    help="Directory where the runnable minimal example will be generated.",
)
def make_example_command(output_dir: Path) -> None:
    manifest = create_minimal_example(output_dir)
    click.echo(json.dumps(manifest, indent=2))


@main.command("run")
@click.option(
    "--config",
    "config_path",
    required=True,
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help="YAML config describing samples, outputs, and module settings.",
)
def run_command(config_path: Path) -> None:
    manifest = run_pipeline_from_config(config_path)
    click.echo(json.dumps(manifest, indent=2))


@main.command("preflight")
@click.option(
    "--config",
    "config_path",
    required=True,
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help="YAML config to validate before running a real-data smoke test.",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Optional output directory for preflight artifacts. Defaults to <output_dir>/preflight.",
)
def preflight_command(config_path: Path, output_dir: Path | None) -> None:
    manifest = run_preflight_from_config(config_path, output_dir=output_dir)
    click.echo(json.dumps(manifest, indent=2))


@main.command("validate-schema")
@click.option(
    "--input-path",
    required=True,
    type=click.Path(path_type=Path, exists=True),
    help="10x filtered_feature_bc_matrix.h5 or matrix.mtx directory.",
)
@click.option(
    "--sample-id",
    default="adhoc_sample",
    show_default=True,
    help="Sample identifier to attach during validation.",
)
@click.option(
    "--condition",
    default="unknown",
    show_default=True,
    help="Condition label to attach during validation.",
)
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("runs/schema_validation"),
    show_default=True,
    help="Where validation artifacts should be written.",
)
def validate_schema_command(
    input_path: Path,
    sample_id: str,
    condition: str,
    output_dir: Path,
) -> None:
    _, schema_report, manifest = ingest_samples(
        sample_specs=[
            SampleSpec(
                sample_id=sample_id,
                condition=condition,
                input_path=input_path.resolve(),
            )
        ],
        output_dir=output_dir.resolve(),
        schema_config={"apply_fixes": True},
    )
    payload = {
        "schema_report": {
            "issues": [
                {
                    "location": issue.location,
                    "severity": issue.severity,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                }
                for issue in schema_report.issues
            ],
            "applied_fixes": schema_report.applied_fixes,
        },
        "ingest_manifest": manifest,
    }
    click.echo(json.dumps(payload, indent=2))


@main.command("fetch-priors")
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path("resources/priors/human_academic"),
    show_default=True,
    help="Directory where official pathway and TF prior tables will be written.",
)
@click.option(
    "--organism",
    default="human",
    show_default=True,
    help="Organism passed to decoupler official resource wrappers.",
)
@click.option(
    "--license",
    "license_name",
    default="academic",
    show_default=True,
    help="License tier forwarded to official decoupler resource wrappers.",
)
@click.option(
    "--pathway-top",
    default=500,
    show_default=True,
    type=int,
    help="Number of top PROGENy genes retained per pathway.",
)
@click.option(
    "--pathway-thr-padj",
    default=0.05,
    show_default=True,
    type=float,
    help="Adjusted p-value threshold used when exporting PROGENy weights.",
)
@click.option(
    "--remove-complexes/--keep-complexes",
    default=False,
    show_default=True,
    help="Whether to remove TF complexes when exporting CollecTRI.",
)
@click.option(
    "--config-base-dir",
    type=click.Path(path_type=Path),
    default=Path("config"),
    show_default=True,
    help="Config directory used to compute snippet paths relative to project config files.",
)
def fetch_priors_command(
    output_dir: Path,
    organism: str,
    license_name: str,
    pathway_top: int,
    pathway_thr_padj: float,
    remove_complexes: bool,
    config_base_dir: Path,
) -> None:
    manifest = fetch_decoupler_priors(
        output_dir=output_dir,
        organism=organism,
        license_name=license_name,
        pathway_top=pathway_top,
        pathway_thr_padj=pathway_thr_padj,
        remove_complexes=remove_complexes,
        config_base_dir=config_base_dir,
    )
    click.echo(json.dumps(manifest, indent=2))


main.add_command(preflight_command, "validate-inputs")
