from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from singlecell_workbench.priors import fetch_decoupler_priors


class _FakeDecoupler:
    __version__ = "2.1.6"

    class op:
        @staticmethod
        def progeny(**_: object) -> pd.DataFrame:
            return pd.DataFrame(
                [
                    {"source": "PathwayA", "target": "GENE1", "weight": 1.0, "padj": 0.001},
                    {"source": "PathwayA", "target": "GENE2", "weight": -1.0, "padj": 0.002},
                ]
            )

        @staticmethod
        def collectri(**_: object) -> pd.DataFrame:
            return pd.DataFrame(
                [
                    {"source": "TF1", "target": "GENE3", "weight": 1.0, "resources": "CollecTRI"},
                    {"source": "TF1", "target": "GENE4", "weight": -1.0, "resources": "CollecTRI"},
                ]
            )


def test_fetch_decoupler_priors_writes_tables_and_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "singlecell_workbench.priors.importlib.import_module",
        lambda package_name: _FakeDecoupler if package_name == "decoupler" else __import__(package_name),
    )

    project_root = tmp_path / "project"
    (project_root / "config").mkdir(parents=True)
    monkeypatch.chdir(project_root)

    manifest = fetch_decoupler_priors(
        output_dir=Path("resources/priors/human_academic"),
        organism="human",
        license_name="academic",
        pathway_top=500,
        pathway_thr_padj=0.05,
    )

    output_dir = project_root / "resources" / "priors" / "human_academic"
    pathway_path = output_dir / "progeny.tsv"
    tf_path = output_dir / "collectri.tsv"
    snippet_path = output_dir / "stats_config.yaml"
    manifest_path = output_dir / "manifest.json"

    assert pathway_path.exists()
    assert tf_path.exists()
    assert snippet_path.exists()
    assert manifest_path.exists()
    assert manifest["pathway"]["rows"] == 2
    assert manifest["tf"]["rows"] == 2

    snippet = snippet_path.read_text(encoding="utf-8")
    assert "../resources/priors/human_academic/progeny.tsv" in snippet
    assert "../resources/priors/human_academic/collectri.tsv" in snippet

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["source"] == "decoupler_official_wrappers"
    assert payload["decoupler_version"] == "2.1.6"
    assert payload["gene_identifier_namespace"] == "gene_symbol"
    assert payload["pathway"]["resource"] == "PROGENy"
    assert payload["pathway"]["sha256"]
    assert payload["tf"]["resource"] == "CollecTRI"
    assert payload["tf"]["sha256"]
