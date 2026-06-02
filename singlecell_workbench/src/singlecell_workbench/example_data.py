from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

import h5py
import numpy as np
import pandas as pd
from scipy import io as spio
from scipy import sparse

from singlecell_workbench.config import dump_config


def create_minimal_example(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    data_dir = output_dir / "data"
    runs_dir = output_dir / "runs"
    data_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    features = pd.DataFrame(
        [
            ("ENSG00000198888", "MT-CO1", "Gene Expression", "GRCh38"),
            ("ENSG00000251562", "MALAT1", "Gene Expression", "GRCh38"),
            ("ENSG00000167286", "CD3D", "Gene Expression", "GRCh38"),
            ("ENSG00000163220", "LYZ", "Gene Expression", "GRCh38"),
            ("ADT0001", "CD3", "Antibody Capture", "GRCh38"),
            ("ADT0002", "CD14", "Antibody Capture", "GRCh38"),
        ],
        columns=["id", "name", "feature_type", "genome"],
    )

    sample_matrices = {
        "ctrl_a": np.array(
            [
                [6, 3, 0, 1, 4, 0],
                [5, 2, 0, 1, 4, 0],
                [1, 3, 6, 0, 5, 1],
                [1, 2, 7, 0, 6, 1],
                [0, 5, 1, 7, 0, 5],
                [0, 4, 1, 8, 0, 6],
            ],
            dtype=np.int32,
        ),
        "stim_b": np.array(
            [
                [7, 2, 0, 1, 5, 0],
                [6, 2, 1, 1, 5, 0],
                [2, 2, 7, 0, 6, 1],
                [1, 2, 8, 0, 6, 1],
                [0, 4, 1, 8, 0, 6],
                [0, 5, 1, 7, 0, 6],
            ],
            dtype=np.int32,
        ),
    }

    sample_configs: list[dict[str, Any]] = []
    for sample_id, cell_feature_counts in sample_matrices.items():
        barcodes = [f"{sample_id}_cell{i + 1}" for i in range(cell_feature_counts.shape[0])]
        feature_cell_matrix = sparse.csr_matrix(cell_feature_counts.T)
        sample_dir = data_dir / sample_id / "filtered_feature_bc_matrix"
        sample_dir.mkdir(parents=True, exist_ok=True)
        _write_10x_mtx_dir(feature_cell_matrix, barcodes, features, sample_dir)
        if sample_id == "ctrl_a":
            input_path = sample_dir
        else:
            h5_path = data_dir / sample_id / "filtered_feature_bc_matrix.h5"
            _write_10x_h5(feature_cell_matrix, barcodes, features, h5_path)
            input_path = h5_path
        sample_configs.append(
            {
                "sample_id": sample_id,
                "condition": "control" if sample_id.startswith("ctrl") else "treated",
                "input_path": str(input_path.relative_to(output_dir)),
            }
        )

    config = {
        "project_name": "singlecell_workbench_minimal_example",
        "output_dir": "runs/minimal_example",
        "samples": sample_configs,
        "schema": {
            "apply_fixes": True,
            "required_obs_columns": ["sample_id", "condition"],
        },
        "qc": {
            "rna_modality": "Gene Expression",
            "qc_vars": ["mt"],
            "solo": {"enabled": True},
            "scar": {"enabled": True},
        },
        "annotation": {
            "modality": "Gene Expression",
            "method_priority": ["scarches_scanvi", "celltypist", "unassigned"],
            "placeholder_label": "unassigned",
            "fallback_label": "unassigned",
        },
        "stats": {
            "modality": "Gene Expression",
            "cell_type_column": "cell_type",
            "sample_column": "sample_id",
            "condition_column": "condition",
            "run_decoupler": True,
        },
        "reports": {
            "title": "Single-cell Workbench Minimal Example",
        },
    }
    config_path = dump_config(config, output_dir / "run_config.yaml")

    manifest = {
        "output_dir": str(output_dir),
        "config_path": str(config_path),
        "samples": sample_configs,
    }
    with (output_dir / "example_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    return manifest


def _write_10x_mtx_dir(
    matrix: sparse.csr_matrix,
    barcodes: list[str],
    features: pd.DataFrame,
    output_dir: Path,
) -> None:
    with gzip.open(output_dir / "matrix.mtx.gz", "wb") as handle:
        spio.mmwrite(handle, matrix)
    with gzip.open(output_dir / "barcodes.tsv.gz", "wt", encoding="utf-8") as handle:
        handle.write("\n".join(barcodes) + "\n")
    with gzip.open(output_dir / "features.tsv.gz", "wt", encoding="utf-8") as handle:
        features.to_csv(handle, sep="\t", header=False, index=False)


def _write_10x_h5(
    matrix: sparse.csr_matrix,
    barcodes: list[str],
    features: pd.DataFrame,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(output_path, "w") as handle:
        group = handle.create_group("matrix")
        group.create_dataset("barcodes", data=np.asarray(barcodes, dtype="S"))
        group.create_dataset("data", data=matrix.data.astype(np.int32))
        group.create_dataset("indices", data=matrix.indices.astype(np.int64))
        group.create_dataset("indptr", data=matrix.indptr.astype(np.int64))
        group.create_dataset("shape", data=np.asarray(matrix.shape, dtype=np.int64))
        feature_group = group.create_group("features")
        for column in features.columns:
            feature_group.create_dataset(column, data=np.asarray(features[column].tolist(), dtype="S"))
