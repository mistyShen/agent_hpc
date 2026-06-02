from __future__ import annotations

import json

import numpy as np
import pytest

pytest.importorskip("anndata")
pytest.importorskip("mudata")

from anndata import AnnData
from mudata import MuData

from singlecell_workbench.modules import annotation


def _make_adata() -> AnnData:
    return AnnData(
        X=np.array(
            [
                [1, 0],
                [0, 1],
                [1, 1],
            ],
            dtype=float,
        ),
        obs={"sample_id": ["s1", "s1", "s2"]},
        var={"gene_symbol": ["g1", "g2"]},
    )


def test_annotate_cells_graceful_placeholder_and_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(
        annotation,
        "_detect_optional_dependencies",
        lambda: {"scarches": False, "scvi": False, "celltypist": False},
    )

    data = _make_adata()
    annotated, manifest = annotation.annotate_cells(data, tmp_path, {"placeholder_label": "unassigned"})

    assert annotated.obs["cell_type"].tolist() == ["unassigned", "unassigned", "unassigned"]
    assert annotated.obs["cell_type_pred"].tolist() == ["unassigned", "unassigned", "unassigned"]
    assert annotated.obs["cell_type_confidence"].tolist() == [0.0, 0.0, 0.0]
    assert annotated.obs["cell_type_method"].tolist() == ["placeholder"] * 3
    assert annotated.obs["annotation_source"].tolist() == ["placeholder"] * 3
    assert annotated.obs["cell_type_curated"].isna().all()

    assert manifest["selected_backend"] == "placeholder"
    assert manifest["annotation_mode"] == "fallback"
    assert manifest["fallback_reason"] == "deterministic fallback"
    assert manifest["missing_optional_dependencies"] == ["celltypist", "scarches", "scvi"]

    manifest_path = tmp_path / "annotation" / "annotation_manifest.json"
    assert manifest_path.exists()
    saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved_manifest["selected_backend"] == "placeholder"
    assert saved_manifest["obs_columns_written"] == [
        "cell_type_pred",
        "cell_type_confidence",
        "annotation_source",
        "cell_type_curated",
        "cell_type",
        "cell_type_method",
    ]


def test_annotate_cells_is_deterministic_for_muda_working_modality(tmp_path, monkeypatch):
    monkeypatch.setattr(
        annotation,
        "_detect_optional_dependencies",
        lambda: {"scarches": False, "scvi": False, "celltypist": False},
    )

    first = MuData({"rna": _make_adata()})
    second = MuData({"rna": _make_adata()})

    first_result, first_manifest = annotation.annotate_cells(
        first,
        tmp_path / "first",
        {"working_modality": "rna"},
    )
    second_result, second_manifest = annotation.annotate_cells(
        second,
        tmp_path / "second",
        {"working_modality": "rna"},
    )

    assert first_manifest["working_modality"] == "rna"
    assert second_manifest["working_modality"] == "rna"
    assert first_result.obs["cell_type"].tolist() == second_result.obs["cell_type"].tolist()
    assert first_result.obs["cell_type_confidence"].tolist() == second_result.obs["cell_type_confidence"].tolist()
    assert first_result.obs["cell_type_method"].tolist() == second_result.obs["cell_type_method"].tolist()

    assert (tmp_path / "first" / "annotation" / "annotation_manifest.json").exists()
    assert (tmp_path / "second" / "annotation" / "annotation_manifest.json").exists()


def test_annotate_cells_preserves_existing_curated_labels(tmp_path, monkeypatch):
    monkeypatch.setattr(
        annotation,
        "_detect_optional_dependencies",
        lambda: {"scarches": False, "scvi": False, "celltypist": False},
    )

    data = _make_adata()
    data.obs["cell_type"] = ["T", "T", "B"]

    annotated, _ = annotation.annotate_cells(data, tmp_path, {"placeholder_label": "unassigned"})

    assert annotated.obs["cell_type_curated"].tolist() == ["T", "T", "B"]
    assert annotated.obs["cell_type_pred"].tolist() == ["unassigned", "unassigned", "unassigned"]
    assert annotated.obs["cell_type"].tolist() == ["T", "T", "B"]
