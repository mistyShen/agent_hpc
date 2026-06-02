from __future__ import annotations

from pathlib import Path

from singlecell_workbench.modules.reports import build_reports


class _AxisFrame:
    def __init__(self, columns: list[str]) -> None:
        self.columns = list(columns)


class _FakeAnnData:
    def __init__(
        self,
        *,
        n_obs: int,
        n_vars: int,
        obs_columns: list[str],
        var_columns: list[str],
        layers: list[str] | None = None,
        obsm: list[str] | None = None,
        uns: list[str] | None = None,
    ) -> None:
        self.n_obs = n_obs
        self.n_vars = n_vars
        self.obs = _AxisFrame(obs_columns)
        self.var = _AxisFrame(var_columns)
        self.layers = {name: object() for name in (layers or [])}
        self.obsm = {name: object() for name in (obsm or [])}
        self.uns = {name: object() for name in (uns or [])}


class _FakeMuData:
    def __init__(self, modalities: dict[str, _FakeAnnData]) -> None:
        self.mod = modalities
        self.n_obs = max((modality.n_obs for modality in modalities.values()), default=0)
        self.n_vars = sum(modality.n_vars for modality in modalities.values())
        self.obs = _AxisFrame(["sample_id", "condition"])
        self.var = _AxisFrame(["feature_type"])
        self.layers = {}
        self.obsm = {}
        self.uns = {}


def test_build_reports_writes_html_and_methods_for_anndata(tmp_path: Path) -> None:
    data = _FakeAnnData(
        n_obs=2,
        n_vars=3,
        obs_columns=["sample_id", "condition", "cell_type"],
        var_columns=["gene_id", "feature_type"],
    )
    schema_manifest = {
        "issues": [
            {
                "location": "obs.sample_id",
                "severity": "warning",
                "message": "sample_id was filled from the sample spec",
                "suggestion": "Keep sample_id in obs for downstream joins",
            }
        ],
        "applied_fixes": ["filled obs.sample_id"],
    }
    qc_manifest = {
        "status": "complete",
        "metrics": {"calculate_qc_metrics": "obs"},
        "run_solo": True,
        "run_scar": True,
        "dependency_skips": [{"dependency": "SCAR", "reason": "optional dependency not installed"}],
        "artifact_paths": {"qc_summary": "reports/qc_summary.csv"},
    }
    annotation_manifest = {
        "selected_method": "scarches_scanvi",
        "fallback_method": "celltypist",
        "artifact_paths": {"labels": "reports/labels.csv"},
    }
    stats_manifest = {
        "groupby": ["sample_id", "cell_type", "condition"],
        "run_decoupler": True,
        "artifact_paths": {"summary": "reports/stats_summary.csv"},
    }

    manifest = build_reports(
        data=data,
        output_dir=tmp_path,
        schema_manifest=schema_manifest,
        qc_manifest=qc_manifest,
        annotation_manifest=annotation_manifest,
        stats_manifest=stats_manifest,
        report_config={"title": "QA Report"},
    )

    report_dir = tmp_path / "reports"
    html_path = report_dir / "report.html"
    methods_path = report_dir / "methods.md"
    manifest_path = report_dir / "report_manifest.json"

    assert html_path.exists()
    assert methods_path.exists()
    assert manifest_path.exists()
    assert manifest["html_report"] == str(html_path)
    assert manifest["methods_draft"] == str(methods_path)
    assert manifest["data"]["kind"] == "AnnData"
    assert manifest["data"]["n_obs"] == 2

    html = html_path.read_text(encoding="utf-8")
    methods = methods_path.read_text(encoding="utf-8")
    assert "QA Report" in html
    assert "AnnData" in html
    assert "sample_id was filled" in html
    assert "scarches_scanvi" in html
    assert "sample_id" in methods
    assert "SCAR" in methods
    assert "decoupler" in methods


def test_build_reports_summarizes_mudata_modalities(tmp_path: Path) -> None:
    data = _FakeMuData(
        {
            "rna": _FakeAnnData(
                n_obs=2,
                n_vars=2,
                obs_columns=["sample_id"],
                var_columns=["gene_id"],
            ),
            "atac": _FakeAnnData(
                n_obs=2,
                n_vars=2,
                obs_columns=["sample_id"],
                var_columns=["peak_id"],
            ),
        }
    )
    manifest = build_reports(
        data=data,
        output_dir=tmp_path,
        schema_manifest={"issues": [], "applied_fixes": []},
        qc_manifest={"status": "complete", "run_solo": False, "run_scar": False},
        annotation_manifest={"selected_method": "celltypist"},
        stats_manifest={"run_decoupler": False},
        report_config=None,
    )

    html = (tmp_path / "reports" / "report.html").read_text(encoding="utf-8")
    methods = (tmp_path / "reports" / "methods.md").read_text(encoding="utf-8")

    assert manifest["data"]["kind"] == "MuData"
    assert set(manifest["data"]["modalities"]) == {"rna", "atac"}
    assert "rna: 2 x 2" in html
    assert "atac: 2 x 2" in html
    assert "Processed 2 cells and" in methods


def test_build_reports_handles_empty_top_level_mudata_mappings(tmp_path: Path) -> None:
    data = _FakeMuData(
        {
            "rna": _FakeAnnData(
                n_obs=2,
                n_vars=2,
                obs_columns=["sample_id"],
                var_columns=["gene_id"],
            )
        }
    )
    data.layers = None
    data.obsm = None
    data.uns = None

    manifest = build_reports(
        data=data,
        output_dir=tmp_path,
        schema_manifest={"issues": [], "applied_fixes": []},
        qc_manifest={"status": "complete", "run_solo": False, "run_scar": False},
        annotation_manifest={"selected_method": "celltypist"},
        stats_manifest={"run_decoupler": False},
        report_config=None,
    )

    assert manifest["data"]["layers"] == []
    assert manifest["data"]["obsm"] == []
    assert manifest["data"]["uns"] == []
