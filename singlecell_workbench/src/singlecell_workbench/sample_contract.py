from __future__ import annotations

from pathlib import Path
from typing import Any

REQUIRED_SAMPLE_FIELDS: tuple[str, ...] = (
    "sample_id",
    "input_path",
    "condition",
    "organism",
    "reference_build",
    "gene_id_type",
)
RECOMMENDED_SAMPLE_FIELDS: tuple[str, ...] = (
    "donor",
    "batch",
    "modality",
    "library_type",
    "chemistry",
)
OPTIONAL_SAMPLE_FIELDS: tuple[str, ...] = ("tissue",)

ORDERED_SAMPLE_FIELDS: tuple[str, ...] = (
    *REQUIRED_SAMPLE_FIELDS,
    *RECOMMENDED_SAMPLE_FIELDS,
    *OPTIONAL_SAMPLE_FIELDS,
)

FIELD_DESCRIPTIONS: dict[str, str] = {
    "sample_id": "Stable unique sample identifier used across ingest, stats, and reports.",
    "input_path": "Path to a 10x filtered_feature_bc_matrix.h5 or matrix.mtx directory.",
    "condition": "Biological or experimental condition used for grouping and contrast.",
    "organism": "Organism for the sample, for example human or mouse.",
    "reference_build": "Reference genome / annotation build associated with the feature space, for example GRCh38.",
    "gene_id_type": "Primary gene identifier namespace intended for downstream alignment, for example gene_symbol or ensembl_gene_id.",
    "donor": "Donor or subject identifier used to track repeated measures and pseudoreplication risk.",
    "batch": "Technical batch label for library prep, sequencing run, or other processing batch.",
    "modality": "Declared biological modality for the sample, for example rna, antibody, or multimodal.",
    "library_type": "Library strategy or assay family, for example 10x_3prime_v3 or cite_seq.",
    "chemistry": "10x or assay chemistry string used for troubleshooting and reference compatibility.",
    "tissue": "Optional tissue or compartment label used to sanity-check annotation references.",
}


def normalize_scalar_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def sample_spec_to_record(sample_spec: Any) -> dict[str, str]:
    record: dict[str, str] = {}
    for field in ORDERED_SAMPLE_FIELDS:
        value = getattr(sample_spec, field, None)
        if field == "input_path" and isinstance(value, Path):
            record[field] = str(value)
            continue
        record[field] = normalize_scalar_text(value) or ""
    return record


def gate1_missing_fields(sample_spec: Any) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_SAMPLE_FIELDS:
        value = getattr(sample_spec, field, None)
        if field == "input_path":
            if value is None or not str(value).strip():
                missing.append(field)
            continue
        if normalize_scalar_text(value) is None:
            missing.append(field)
    return missing
