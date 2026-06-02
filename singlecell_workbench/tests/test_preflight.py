from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.io import mmwrite

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from singlecell_workbench.config import dump_config
from singlecell_workbench.preflight import run_preflight_from_config


def _write_mtx_fixture(base_dir: Path) -> Path:
    input_dir = base_dir / "sample_mtx"
    input_dir.mkdir(parents=True, exist_ok=True)

    matrix = sparse.csr_matrix(
        np.array(
            [
                [1, 0],
                [0, 2],
                [3, 0],
            ],
            dtype=np.int64,
        )
    )
    mmwrite(input_dir / "matrix.mtx", matrix)
    (input_dir / "features.tsv").write_text(
        "\n".join(
            [
                "ENSG0001\tGeneA\tGene Expression",
                "ENSG0002\tGeneB\tGene Expression",
                "ENSG0003\tGeneC\tGene Expression",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (input_dir / "barcodes.tsv").write_text("cell1\ncell2\n", encoding="utf-8")
    return input_dir


def test_preflight_writes_gate1_reports(tmp_path: Path) -> None:
    input_dir = _write_mtx_fixture(tmp_path)
    priors_dir = tmp_path / "resources" / "priors" / "human_academic"
    priors_dir.mkdir(parents=True)
    (priors_dir / "progeny.tsv").write_text(
        "source\ttarget\tweight\nPathwayA\tGeneA\t1.0\nPathwayA\tGeneB\t-1.0\n",
        encoding="utf-8",
    )
    (priors_dir / "collectri.tsv").write_text(
        "source\ttarget\tweight\nTF1\tGeneB\t1.0\nTF1\tGeneC\t-1.0\n",
        encoding="utf-8",
    )
    (priors_dir / "manifest.json").write_text(
        json.dumps(
            {
                "organism": "human",
                "gene_identifier_namespace": "gene_symbol",
                "pathway": {"gene_identifier_namespace": "gene_symbol"},
                "tf": {"gene_identifier_namespace": "gene_symbol"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    reference_dir = tmp_path / "references"
    reference_dir.mkdir()
    reference_manifest_path = reference_dir / "reference_manifest.json"
    reference_manifest_path.write_text(
        json.dumps(
            {
                "reference_name": "blood_ref_v1",
                "species": "human",
                "tissue": "blood",
                "modality": "rna",
                "training_source": "atlas",
                "training_version": "2026-04-01",
                "gene_namespace": "gene_symbol",
                "label_fields": ["cell_type"],
                "model_path": "models/blood_ref",
                "ontology_vocabulary": "CL",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    config = {
        "project_name": "preflight_smoke",
        "output_dir": "runs/preflight_smoke",
        "samples": [
            {
                "sample_id": "s1",
                "condition": "control",
                "input_path": str(input_dir),
                "organism": "human",
                "reference_build": "GRCh38",
                "gene_id_type": "gene_symbol",
                "modality": "rna",
                "tissue": "blood",
            }
        ],
        "annotation": {
            "modality": "Gene Expression",
            "reference_manifest": str(reference_manifest_path),
        },
        "stats": {
            "decoupler": {
                "enabled": True,
                "pathway_network": str(priors_dir / "progeny.tsv"),
                "tf_network": str(priors_dir / "collectri.tsv"),
            }
        },
    }
    config_path = dump_config(config, tmp_path / "config" / "run.yaml")

    manifest = run_preflight_from_config(config_path)

    report_path = Path(manifest["preflight_report"])
    summary_path = Path(manifest["preflight_summary"])
    markdown_path = Path(manifest["preflight_markdown"])
    assert manifest["status"] == "pass"
    assert report_path.exists()
    assert summary_path.exists()
    assert markdown_path.exists()

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["samples"][0]["gate1_ready"] is True
    assert payload["samples"][0]["priors"]["pathway"]["overlap_count"] == 2
    assert payload["reference"]["summary"]["reference_name"] == "blood_ref_v1"


def test_preflight_fails_duplicate_sample_ids(tmp_path: Path) -> None:
    input_dir = _write_mtx_fixture(tmp_path)
    config = {
        "project_name": "preflight_duplicates",
        "output_dir": "runs/preflight_duplicates",
        "samples": [
            {
                "sample_id": "dup",
                "condition": "control",
                "input_path": str(input_dir),
                "organism": "human",
                "reference_build": "GRCh38",
                "gene_id_type": "gene_symbol",
            },
            {
                "sample_id": "dup",
                "condition": "treated",
                "input_path": str(input_dir),
            },
        ],
    }
    config_path = dump_config(config, tmp_path / "config" / "run.yaml")

    manifest = run_preflight_from_config(config_path)
    payload = json.loads(Path(manifest["preflight_report"]).read_text(encoding="utf-8"))

    assert manifest["status"] == "fail"
    assert payload["project_issues"][0]["message"] == "sample_id values must be unique across the run."
