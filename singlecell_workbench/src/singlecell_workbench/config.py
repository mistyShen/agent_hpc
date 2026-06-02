from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from singlecell_workbench.sample_contract import ORDERED_SAMPLE_FIELDS, normalize_scalar_text
from singlecell_workbench.types import SampleSpec


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}
    if not isinstance(config, dict):
        raise TypeError(f"Config at {config_path} must deserialize to a mapping.")
    return config


def dump_config(config: dict[str, Any], config_path: Path) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, sort_keys=False)
    return config_path


def resolve_path(base_dir: Path, value: str | Path) -> Path:
    candidate = Path(value)
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def resolve_output_dir(config: dict[str, Any], base_dir: Path) -> Path:
    output_value = config.get("output_dir", "outputs/run")
    return resolve_path(base_dir, output_value)


def normalize_config_paths(config: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    normalized = deepcopy(config)
    for keys in (
        ("stats", "decoupler", "pathway_network"),
        ("stats", "decoupler", "tf_network"),
        ("annotation", "reference_manifest"),
    ):
        section: Any = normalized
        for key in keys[:-1]:
            if not isinstance(section, dict):
                section = None
                break
            section = section.get(key)
        if not isinstance(section, dict):
            continue
        value = section.get(keys[-1])
        if value is None:
            continue
        section[keys[-1]] = str(resolve_path(base_dir, value))
    return normalized


def build_sample_specs(config: dict[str, Any], base_dir: Path) -> list[SampleSpec]:
    samples = config.get("samples", [])
    if not samples:
        raise ValueError("Config must include a non-empty 'samples' list.")
    sample_specs: list[SampleSpec] = []
    for sample in samples:
        if not isinstance(sample, dict):
            raise TypeError("Each sample entry must be a mapping.")
        sample_id = str(sample["sample_id"])
        condition = str(sample.get("condition", "unknown"))
        input_path = resolve_path(base_dir, str(sample["input_path"]))
        contract_fields = {
            field: normalize_scalar_text(sample.get(field))
            for field in ORDERED_SAMPLE_FIELDS
            if field not in {"sample_id", "condition", "input_path"}
        }
        obs_metadata = {
            key: value
            for key, value in sample.items()
            if key not in {"sample_id", "condition", "input_path"}
        }
        sample_specs.append(
            SampleSpec(
                sample_id=sample_id,
                condition=condition,
                input_path=input_path,
                organism=contract_fields.get("organism"),
                donor=contract_fields.get("donor"),
                batch=contract_fields.get("batch"),
                modality=contract_fields.get("modality"),
                library_type=contract_fields.get("library_type"),
                chemistry=contract_fields.get("chemistry"),
                reference_build=contract_fields.get("reference_build"),
                gene_id_type=contract_fields.get("gene_id_type"),
                tissue=contract_fields.get("tissue"),
                obs_metadata=obs_metadata,
            )
        )
    return sample_specs
