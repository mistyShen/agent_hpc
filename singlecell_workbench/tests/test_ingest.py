from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import h5py
import numpy as np
import pandas as pd
import pytest
from scipy import sparse
from scipy.io import mmwrite

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

from singlecell_workbench.modules.ingest import ingest_samples
from singlecell_workbench.schema import validate_and_fix_schema


def _sample_spec(sample_id: str, condition: str, input_path: Path, **obs_metadata: object) -> SimpleNamespace:
    return SimpleNamespace(
        sample_id=sample_id,
        condition=condition,
        input_path=input_path,
        obs_metadata=obs_metadata,
    )


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


def _write_h5_fixture(base_dir: Path) -> Path:
    input_path = base_dir / "synthetic_10x.h5"
    matrix = sparse.csr_matrix(
        np.array(
            [
                [1, 0],
                [0, 2],
                [5, 0],
                [0, 7],
            ],
            dtype=np.int64,
        )
    )
    with h5py.File(input_path, "w") as handle:
        group = handle.create_group("matrix")
        group.create_dataset("data", data=matrix.data)
        group.create_dataset("indices", data=matrix.indices)
        group.create_dataset("indptr", data=matrix.indptr)
        group.create_dataset("shape", data=np.asarray(matrix.shape, dtype=np.int64))
        group.create_dataset("barcodes", data=np.asarray([b"cell1", b"cell2"]))
        features = group.create_group("features")
        features.create_dataset("id", data=np.asarray([b"feat1", b"feat2", b"feat3", b"feat4"]))
        features.create_dataset("name", data=np.asarray([b"GeneA", b"GeneB", b"ADT1", b"ADT2"]))
        features.create_dataset(
            "feature_type",
            data=np.asarray(
                [
                    b"Gene Expression",
                    b"Gene Expression",
                    b"Antibody Capture",
                    b"Antibody Capture",
                ]
            ),
        )
    return input_path


def test_ingest_mtx_single_modality(tmp_path: Path) -> None:
    input_dir = _write_mtx_fixture(tmp_path)
    output_dir = tmp_path / "output"

    data, report, manifest = ingest_samples(
        [_sample_spec("sample_a", "treated", input_dir)],
        output_dir,
    )

    assert manifest["kind"] == "h5ad"
    assert Path(manifest["normalized_path"]).exists()
    assert Path(manifest["schema_report_path"]).exists()
    assert report.to_dict()["issues"] == []
    assert data.obs["sample_id"].tolist() == ["sample_a", "sample_a"]
    assert data.obs["condition"].tolist() == ["treated", "treated"]
    assert Path(manifest["normalized_path"]).suffix == ".h5ad"

    report_json = json.loads(Path(manifest["schema_report_path"]).read_text(encoding="utf-8"))
    assert report_json["applied_fixes"] == []


def test_ingest_synthetic_10x_h5_multimodal(tmp_path: Path) -> None:
    input_path = _write_h5_fixture(tmp_path)
    output_dir = tmp_path / "output"

    data, report, manifest = ingest_samples(
        [_sample_spec("sample_b", "control", input_path, batch="b1")],
        output_dir,
    )

    assert manifest["kind"] == "h5mu"
    assert Path(manifest["normalized_path"]).exists()
    assert set(manifest["modalities"]) == {"Gene Expression", "Antibody Capture"}
    assert set(data.mod) == {"Gene Expression", "Antibody Capture"}
    assert data.obs["sample_id"].tolist() == ["sample_b", "sample_b"]
    assert data.obs["condition"].tolist() == ["control", "control"]
    assert all("batch" in modality.obs.columns for modality in data.mod.values())
    assert isinstance(report.to_dict()["issues"], list)


def test_schema_validation_applies_low_risk_fixes() -> None:
    data = SimpleNamespace(
        X=sparse.csr_matrix(np.eye(2, dtype=np.float32)),
        obs=pd.DataFrame({"value": [1, 2]}, index=["cell", "cell"]),
        var=pd.DataFrame({"value": [3, 4]}, index=["gene", "gene"]),
        layers={"bad": np.zeros((3, 3))},
        obsm={"good": np.array([1.0, 2.0]), "bad": np.zeros((3, 2))},
        uns={"path": Path("/tmp/example"), "nested": {"items": {1, 2}}},
    )

    fixed, report = validate_and_fix_schema(data, {"default_sample_id": "sample_x", "default_condition": "stim"})

    assert fixed.obs["sample_id"].tolist() == ["sample_x", "sample_x"]
    assert fixed.obs["condition"].tolist() == ["stim", "stim"]
    assert fixed.obs.index.is_unique
    assert fixed.var.index.is_unique
    assert "bad" not in fixed.layers
    assert fixed.obsm["good"].shape == (2, 1)
    assert "bad" not in fixed.obsm
    assert fixed.uns["path"] == "/tmp/example"
    assert sorted(fixed.uns["nested"]["items"]) == [1, 2]
    assert any(issue.location in {"obs", "var", "layers.bad", "obsm.bad"} for issue in report.issues) is True
