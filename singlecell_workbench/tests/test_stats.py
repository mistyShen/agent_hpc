from __future__ import annotations

import csv
import importlib
import sys
from pathlib import Path

import pandas as pd

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from singlecell_workbench.modules import stats


class FakeAnnData:
    def __init__(self, obs: list[dict[str, object]], X: list[list[float]] | None = None, var_names: list[str] | None = None):
        self.obs = obs
        self.X = X
        self.var_names = var_names or []
        self.layers: dict[str, object] = {}


class FakeMuData:
    def __init__(self, mod: dict[str, FakeAnnData], obs: list[dict[str, object]]):
        self.mod = mod
        self.obs = obs


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_run_statistics_writes_grouped_summary(tmp_path: Path) -> None:
    data = FakeAnnData(
        obs=[
            {"sample": "s1", "cell_type": "T", "condition": "ctrl"},
            {"sample": "s1", "cell_type": "T", "condition": "ctrl"},
            {"sample": "s1", "cell_type": "B", "condition": "ctrl"},
            {"sample": "s2", "cell_type": "T", "condition": "treated"},
        ]
    )

    manifest = stats.run_statistics(data, tmp_path, {"decoupler": {"enabled": False}})

    summary_path = tmp_path / "stats" / "sample_cell_type_condition_summary.csv"
    sample_totals_path = tmp_path / "stats" / "sample_totals.csv"
    manifest_path = tmp_path / "stats" / "manifest.json"

    assert summary_path.exists()
    assert sample_totals_path.exists()
    assert manifest_path.exists()
    assert manifest["status"] == "completed"
    assert manifest["tables"]["sample_cell_type_condition_summary"]["rows"] == 3

    rows = _read_csv(summary_path)
    assert rows == [
        {
            "sample": "s1",
            "cell_type": "B",
            "condition": "ctrl",
            "n_cells": "1",
            "fraction_of_all_cells": "0.25",
            "fraction_within_sample": "0.3333333333333333",
            "fraction_within_sample_condition": "0.3333333333333333",
        },
        {
            "sample": "s1",
            "cell_type": "T",
            "condition": "ctrl",
            "n_cells": "2",
            "fraction_of_all_cells": "0.5",
            "fraction_within_sample": "0.6666666666666666",
            "fraction_within_sample_condition": "0.6666666666666666",
        },
        {
            "sample": "s2",
            "cell_type": "T",
            "condition": "treated",
            "n_cells": "1",
            "fraction_of_all_cells": "0.25",
            "fraction_within_sample": "1.0",
            "fraction_within_sample_condition": "1.0",
        },
    ]


def test_run_statistics_gracefully_skips_decoupler(tmp_path: Path, monkeypatch) -> None:
    data = FakeMuData(
        mod={
            "rna": FakeAnnData(
                obs=[
                    {"sample": "s1", "cell_type": "T", "condition": "ctrl"},
                    {"sample": "s1", "cell_type": "B", "condition": "treated"},
                ]
            )
        },
        obs=[
            {"sample": "s1", "cell_type": "T", "condition": "ctrl"},
            {"sample": "s1", "cell_type": "B", "condition": "treated"},
        ],
    )

    monkeypatch.setattr(stats, "_dependency_available", lambda package_name: False if package_name == "decoupler" else True)

    manifest = stats.run_statistics(
        data,
        tmp_path,
        {"working_modality": "rna", "decoupler": {"enabled": True}},
    )

    assert manifest["working_modality"] == "rna"
    assert manifest["decoupler"]["status"] == "skipped"
    assert "not installed" in manifest["decoupler"]["reason"]


def test_run_statistics_supports_decoupler_v2_mt_runner(tmp_path: Path, monkeypatch) -> None:
    data = FakeAnnData(
        obs=[
            {"sample_id": "s1", "cell_type": "T", "condition": "ctrl"},
            {"sample_id": "s1", "cell_type": "T", "condition": "ctrl"},
            {"sample_id": "s2", "cell_type": "B", "condition": "treated"},
            {"sample_id": "s2", "cell_type": "B", "condition": "treated"},
        ],
        X=[
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            [2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
            [3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
            [4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
        ],
        var_names=["g1", "g2", "g3", "g4", "g5", "g6"],
    )

    calls: list[dict[str, object]] = []

    class _FakeDecouplerMT:
        @staticmethod
        def mlm(expr: pd.DataFrame, net: pd.DataFrame, **kwargs: object) -> tuple[pd.DataFrame, pd.DataFrame]:
            calls.append({"expr_shape": expr.shape, "net_shape": net.shape, "kwargs": dict(kwargs)})
            scores = pd.DataFrame({"score": [0.1] * len(expr.index)}, index=expr.index)
            pvals = pd.DataFrame({"score": [0.05] * len(expr.index)}, index=expr.index)
            return scores, pvals

    class _FakeDecoupler:
        __version__ = "2.1.6"
        mt = _FakeDecouplerMT()

    monkeypatch.setattr(stats, "_dependency_available", lambda _package_name: True)
    original_import_module = importlib.import_module
    monkeypatch.setattr(
        stats.importlib,
        "import_module",
        lambda package_name: _FakeDecoupler if package_name == "decoupler" else original_import_module(package_name),
    )

    manifest = stats.run_statistics(
        data,
        tmp_path,
        {
            "sample_column": "sample_id",
            "cell_type_column": "cell_type",
            "condition_column": "condition",
            "decoupler": {
                "enabled": True,
                "runner": "mlm",
                "min_targets": 3,
                "pathway_network": [{"source": "pathway_a", "target": "g1", "weight": 1.0}],
                "tf_network": [{"source": "tf_a", "target": "g2", "weight": 1.0}],
            },
        },
    )

    assert manifest["decoupler"]["status"] == "completed"
    assert [entry["status"] for entry in manifest["decoupler"]["analyses"]] == ["completed", "completed"]
    assert all(entry["runner"] == "mt.mlm" for entry in manifest["decoupler"]["analyses"])
    assert len(calls) == 2
    assert all(call["expr_shape"] == (2, 6) for call in calls)
    assert all(call["kwargs"] == {"tmin": 3} for call in calls)
    assert (tmp_path / "stats" / "pathway_activity.csv").exists()
    assert (tmp_path / "stats" / "tf_activity.csv").exists()
