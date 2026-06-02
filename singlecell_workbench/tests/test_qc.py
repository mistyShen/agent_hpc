from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from singlecell_workbench.modules.qc import run_qc


class FakeAnnData:
    def __init__(self, obs_index: list[str], var_index: list[str], x: list[list[float]]):
        self.obs = pd.DataFrame(index=pd.Index(obs_index, name="cell_id"))
        self.var = pd.DataFrame(index=pd.Index(var_index, name="gene_id"))
        self.X = np.asarray(x, dtype=float)
        self.uns: dict[str, object] = {}

    @property
    def n_vars(self) -> int:
        return int(self.var.shape[0])

    @property
    def var_names(self) -> pd.Index:
        return self.var.index


class FakeMuData:
    def __init__(self, rna: FakeAnnData):
        self.mod = {"rna": rna}
        self.obs = pd.DataFrame(index=rna.obs.index.copy())


def _fake_calculate_qc_metrics(adata, qc_vars=None, percent_top=None, log1p=True, inplace=True):
    obs_index = adata.obs.index
    counts = pd.Series(adata.X.sum(axis=1), index=obs_index, dtype=float)
    detected = pd.Series((adata.X > 0).sum(axis=1), index=obs_index, dtype=float)

    adata.obs["total_counts"] = counts
    adata.obs["n_genes_by_counts"] = detected
    if log1p:
        adata.obs["log1p_total_counts"] = np.log1p(counts)
        adata.obs["log1p_n_genes_by_counts"] = np.log1p(detected)

    for qc_var in qc_vars or []:
        column = adata.var[qc_var].astype(bool).to_numpy() if qc_var in adata.var.columns else None
        if column is None or not column.any():
            adata.obs[f"pct_counts_{qc_var}"] = 0.0
            continue
        subset_counts = pd.Series(adata.X[:, column].sum(axis=1), index=obs_index, dtype=float)
        adata.obs[f"pct_counts_{qc_var}"] = np.where(counts.to_numpy() > 0, subset_counts / counts * 100.0, 0.0)


def _install_fake_scanpy(monkeypatch):
    calls: list[dict[str, object]] = []

    def wrapped(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        return _fake_calculate_qc_metrics(*args, **kwargs)

    fake_scanpy = SimpleNamespace(pp=SimpleNamespace(calculate_qc_metrics=wrapped))
    monkeypatch.setitem(sys.modules, "scanpy", fake_scanpy)
    return calls


def test_run_qc_ann_data_skips_optional_dependencies(tmp_path, monkeypatch):
    calls = _install_fake_scanpy(monkeypatch)
    monkeypatch.setattr("singlecell_workbench.modules.qc._module_available", lambda module_name: False)

    data = FakeAnnData(
        obs_index=["cell1", "cell2"],
        var_index=["MT-CO1", "GAPDH", "RPL13A"],
        x=[[10, 0, 2], [0, 5, 1]],
    )

    result, manifest = run_qc(
        data,
        tmp_path,
        {
            "solo": {"enabled": True},
            "scar": {"enabled": True},
        },
    )

    assert result is data
    assert data.var["mt"].tolist() == [True, False, False]
    assert calls[0]["kwargs"]["qc_vars"] == ["mt"]
    assert calls[0]["kwargs"]["percent_top"] is None

    qc_dir = tmp_path / "qc"
    assert (qc_dir / "per_cell_qc.csv").exists()
    manifest_path = qc_dir / "manifest.json"
    assert manifest_path.exists()

    loaded_manifest = json.loads(manifest_path.read_text())
    assert loaded_manifest["solo"]["status"] == "skipped"
    assert loaded_manifest["solo"]["reason"] == "dependency_missing: scvi-tools"
    assert loaded_manifest["scar"]["status"] == "skipped"
    assert loaded_manifest["scar"]["reason"] == "dependency_missing: scar"
    assert manifest["per_cell_qc_csv"].endswith("per_cell_qc.csv")

    per_cell = pd.read_csv(qc_dir / "per_cell_qc.csv", index_col=0)
    assert {"total_counts", "n_genes_by_counts", "pct_counts_mt"}.issubset(per_cell.columns)


def test_run_qc_mudata_mirrors_top_level_obs(tmp_path, monkeypatch):
    _install_fake_scanpy(monkeypatch)
    monkeypatch.setattr("singlecell_workbench.modules.qc._module_available", lambda module_name: False)

    rna = FakeAnnData(
        obs_index=["cellA", "cellB"],
        var_index=["MT-CO1", "GAPDH", "RPL13A"],
        x=[[4, 1, 0], [2, 0, 3]],
    )
    data = FakeMuData(rna)

    _, manifest = run_qc(
        data,
        tmp_path,
        {
            "rna_modality": "rna",
            "solo": {"enabled": True},
            "scar": {"enabled": True},
        },
    )

    assert {"total_counts", "n_genes_by_counts", "pct_counts_mt"}.issubset(data.obs.columns)
    assert manifest["data_kind"] == "MuData"
    assert "total_counts" in manifest["mirrored_columns"]
    assert data.obs.loc["cellA", "total_counts"] == 5.0
