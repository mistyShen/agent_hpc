from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from singlecell_workbench.config import normalize_config_paths


def test_normalize_config_paths_resolves_decoupler_networks_relative_to_config_dir(tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    config = {
        "annotation": {
            "reference_manifest": "../references/human_blood/reference_manifest.json",
        },
        "stats": {
            "decoupler": {
                "pathway_network": "../resources/priors/human_academic/progeny.tsv",
                "tf_network": "../resources/priors/human_academic/collectri.tsv",
            }
        }
    }

    normalized = normalize_config_paths(config, config_dir)

    assert normalized["stats"]["decoupler"]["pathway_network"] == str(
        (tmp_path / "resources" / "priors" / "human_academic" / "progeny.tsv").resolve()
    )
    assert normalized["stats"]["decoupler"]["tf_network"] == str(
        (tmp_path / "resources" / "priors" / "human_academic" / "collectri.tsv").resolve()
    )
    assert normalized["annotation"]["reference_manifest"] == str(
        (tmp_path / "references" / "human_blood" / "reference_manifest.json").resolve()
    )
