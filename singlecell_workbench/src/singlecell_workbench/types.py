from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from anndata import AnnData
except Exception:  # pragma: no cover - optional scientific stack may be absent in minimal envs
    AnnData = Any  # type: ignore[misc,assignment]

try:
    from mudata import MuData
except Exception:  # pragma: no cover - optional scientific stack may be absent in minimal envs
    MuData = Any  # type: ignore[misc,assignment]

from singlecell_workbench.schema import SchemaIssue, SchemaReport


SingleCellData = Any


@dataclass(slots=True)
class SampleSpec:
    sample_id: str
    condition: str
    input_path: Path
    organism: str | None = None
    donor: str | None = None
    batch: str | None = None
    modality: str | None = None
    library_type: str | None = None
    chemistry: str | None = None
    reference_build: str | None = None
    gene_id_type: str | None = None
    tissue: str | None = None
    obs_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ModuleArtifacts:
    output_dir: Path
    manifest: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PipelineOutputs:
    data: SingleCellData
    schema_report: SchemaReport
    qc_manifest: dict[str, Any]
    annotation_manifest: dict[str, Any]
    stats_manifest: dict[str, Any]
    report_manifest: dict[str, Any]
