from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
import gzip
import json

import h5py
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.io import mmread

from singlecell_workbench.schema import SchemaReport, validate_and_fix_schema, write_schema_report

try:  # pragma: no cover - exercised in environments with the full stack installed
    from anndata import AnnData as _AnnData
except Exception:  # pragma: no cover - local fallback when optional dependency is absent
    _AnnData = None

try:  # pragma: no cover - exercised in environments with the full stack installed
    from mudata import MuData as _MuData
except Exception:  # pragma: no cover - local fallback when optional dependency is absent
    _MuData = None


@dataclass(slots=True)
class _ParsedModality:
    sample_id: str
    condition: str
    feature_type: str
    cell_ids: list[str]
    obs: pd.DataFrame
    var: pd.DataFrame
    matrix: sparse.csr_matrix


@dataclass(slots=True)
class _FallbackAnnData:
    X: sparse.csr_matrix
    obs: pd.DataFrame
    var: pd.DataFrame
    layers: dict[str, Any] = field(default_factory=dict)
    obsm: dict[str, Any] = field(default_factory=dict)
    uns: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> "_FallbackAnnData":
        return _FallbackAnnData(
            X=self.X.copy(),
            obs=self.obs.copy(),
            var=self.var.copy(),
            layers={key: value.copy() if hasattr(value, "copy") else value for key, value in self.layers.items()},
            obsm={key: value.copy() if hasattr(value, "copy") else value for key, value in self.obsm.items()},
            uns=json.loads(json.dumps(self.uns, default=str)),
        )

    @property
    def n_obs(self) -> int:
        return int(self.obs.shape[0])

    @property
    def n_vars(self) -> int:
        return int(self.var.shape[0])

    @property
    def obs_names(self) -> pd.Index:
        return self.obs.index

    @property
    def var_names(self) -> pd.Index:
        return self.var.index

    def write_h5ad(self, path: Path) -> None:
        _write_h5ad_like(path, self)


@dataclass(slots=True)
class _FallbackMuData:
    mod: dict[str, _FallbackAnnData]
    obs: pd.DataFrame
    uns: dict[str, Any] = field(default_factory=dict)

    def copy(self) -> "_FallbackMuData":
        return _FallbackMuData(
            mod={key: value.copy() for key, value in self.mod.items()},
            obs=self.obs.copy(),
            uns=json.loads(json.dumps(self.uns, default=str)),
        )

    @property
    def n_obs(self) -> int:
        return int(self.obs.shape[0])

    @property
    def n_vars(self) -> int:
        return int(sum(modality.n_vars for modality in self.mod.values()))

    @property
    def var(self) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for modality_name, modality in self.mod.items():
            frame = modality.var.copy()
            frame["modality"] = modality_name
            frames.append(frame)
        if not frames:
            return pd.DataFrame()
        return pd.concat(frames, axis=0)

    @property
    def layers(self) -> dict[str, Any]:
        return {}

    @property
    def obsm(self) -> dict[str, Any]:
        return {}

    def write_h5mu(self, path: Path) -> None:
        _write_h5mu_like(path, self)


def _sample_attr(spec: Any, name: str, default: Any = None) -> Any:
    if hasattr(spec, name):
        return getattr(spec, name)
    if isinstance(spec, dict):
        return spec.get(name, default)
    return default


def _as_path(value: Any) -> Path:
    if isinstance(value, Path):
        return value
    return Path(str(value))


def _open_text(path: Path) -> Iterable[str]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            yield from handle
        return
    with path.open("rt", encoding="utf-8") as handle:
        yield from handle


def _read_barcodes(path: Path) -> list[str]:
    return [line.rstrip("\n").split("\t")[0] for line in _open_text(path) if line.strip()]


def _decode_array(values: Any, *, default: str | None = None) -> list[str]:
    if values is None:
        return [] if default is None else [default]
    if hasattr(values, "shape") and getattr(values, "shape", (0,))[0] == 0:
        return []
    result: list[str] = []
    for value in list(values):
        if isinstance(value, (bytes, np.bytes_)):
            result.append(value.decode("utf-8"))
        elif value is None:
            result.append(default or "")
        else:
            result.append(str(value))
    return result


def _read_features(path: Path) -> pd.DataFrame:
    rows = [line.rstrip("\n").split("\t") for line in _open_text(path) if line.strip()]
    if not rows:
        raise ValueError(f"Feature table is empty: {path}")
    width = max(len(row) for row in rows)
    padded = [row + [""] * (width - len(row)) for row in rows]
    columns = ["feature_id", "feature_name", "feature_type", "genome", "extra1", "extra2"][:width]
    frame = pd.DataFrame(padded, columns=columns)
    if "feature_type" not in frame.columns:
        frame["feature_type"] = "Gene Expression"
    frame["feature_type"] = frame["feature_type"].replace("", "Gene Expression")
    if "feature_name" not in frame.columns:
        frame["feature_name"] = frame["feature_id"]
    frame.index = pd.Index(frame["feature_id"].astype(str).fillna(frame["feature_name"].astype(str)))
    return frame


def _feature_key(frame: pd.DataFrame) -> pd.Index:
    if "feature_id" in frame.columns:
        return pd.Index(frame["feature_id"].astype(str))
    return pd.Index(frame.index.astype(str))


def _sample_obs_frame(
    *,
    sample_id: str,
    condition: str,
    cell_ids: list[str],
    barcodes: list[str],
    extra_metadata: dict[str, Any] | None,
    input_path: Path,
) -> pd.DataFrame:
    obs = pd.DataFrame(
        {
            "sample_id": [sample_id] * len(cell_ids),
            "condition": [condition] * len(cell_ids),
            "barcode": barcodes,
            "input_path": [str(input_path)] * len(cell_ids),
        },
        index=pd.Index(cell_ids, name="cell_id"),
    )
    if extra_metadata:
        for key, value in extra_metadata.items():
            values = value if isinstance(value, (list, tuple, np.ndarray, pd.Series)) else [value]
            if len(values) == len(cell_ids):
                obs[key] = list(values)
            else:
                obs[key] = [value] * len(cell_ids)
    return obs


def _empty_modality_matrix(feature_count: int, cell_count: int, dtype: Any) -> sparse.csr_matrix:
    return sparse.csr_matrix((feature_count, cell_count), dtype=dtype)


def _read_10x_h5(path: Path, *, sample_id: str, condition: str, extra_metadata: dict[str, Any] | None) -> list[_ParsedModality]:
    with h5py.File(path, "r") as handle:
        matrix = handle["matrix"]
        data = np.asarray(matrix["data"])
        indices = np.asarray(matrix["indices"])
        indptr = np.asarray(matrix["indptr"])
        shape = tuple(int(item) for item in np.asarray(matrix["shape"]).tolist())
        features_group = matrix["features"] if "features" in matrix else matrix
        barcodes = [barcode.decode("utf-8") if isinstance(barcode, (bytes, np.bytes_)) else str(barcode) for barcode in matrix["barcodes"][:]]
        feature_ids = _decode_array(features_group["id"][:] if "id" in features_group else features_group["feature_ids"][:])
        feature_names = _decode_array(
            features_group["name"][:] if "name" in features_group else features_group["feature_names"][:]
            if "feature_names" in features_group
            else feature_ids,
            default="",
        )
        feature_types = _decode_array(
            features_group["feature_type"][:] if "feature_type" in features_group else features_group["feature_types"][:]
            if "feature_types" in features_group
            else np.array(["Gene Expression"] * shape[0]),
            default="Gene Expression",
        )

    matrix_csr = sparse.csr_matrix((data, indices, indptr), shape=shape)
    cell_ids = [f"{sample_id}:{barcode}" for barcode in barcodes]
    obs = _sample_obs_frame(
        sample_id=sample_id,
        condition=condition,
        cell_ids=cell_ids,
        barcodes=barcodes,
        extra_metadata=extra_metadata,
        input_path=path,
    )
    frame = pd.DataFrame(
        {
            "feature_id": feature_ids,
            "feature_name": feature_names,
            "feature_type": feature_types,
        }
    )
    frame.index = pd.Index(frame["feature_id"].astype(str))

    parsed: list[_ParsedModality] = []
    for feature_type in pd.Index(feature_types).unique():
        selector = np.asarray(frame["feature_type"] == feature_type)
        sub_frame = frame.loc[selector].copy()
        sub_matrix = matrix_csr[selector, :]
        parsed.append(
            _ParsedModality(
                sample_id=sample_id,
                condition=condition,
                feature_type=str(feature_type),
                cell_ids=cell_ids,
                obs=obs.copy(),
                var=sub_frame,
                matrix=sub_matrix.tocsr(),
            )
        )
    return parsed


def _read_10x_mtx_dir(path: Path, *, sample_id: str, condition: str, extra_metadata: dict[str, Any] | None) -> list[_ParsedModality]:
    matrix_path = path / "matrix.mtx"
    if not matrix_path.exists():
        gz_candidate = path / "matrix.mtx.gz"
        if gz_candidate.exists():
            matrix_path = gz_candidate
        else:
            candidates = list(path.rglob("matrix.mtx")) + list(path.rglob("matrix.mtx.gz"))
            if not candidates:
                raise FileNotFoundError(f"Could not locate matrix.mtx under {path}")
            matrix_path = candidates[0]
    if matrix_path.suffix == ".gz":
        with gzip.open(matrix_path, "rb") as handle:
            matrix = mmread(handle).tocsr()
    else:
        matrix = mmread(matrix_path).tocsr()

    features_path = next(
        (candidate for candidate in [path / "features.tsv", path / "features.tsv.gz", path / "genes.tsv", path / "genes.tsv.gz"] if candidate.exists()),
        None,
    )
    barcodes_path = next(
        (candidate for candidate in [path / "barcodes.tsv", path / "barcodes.tsv.gz"] if candidate.exists()),
        None,
    )
    if features_path is None or barcodes_path is None:
        nested_features = list(path.rglob("features.tsv")) + list(path.rglob("features.tsv.gz")) + list(path.rglob("genes.tsv")) + list(path.rglob("genes.tsv.gz"))
        nested_barcodes = list(path.rglob("barcodes.tsv")) + list(path.rglob("barcodes.tsv.gz"))
        if features_path is None and nested_features:
            features_path = nested_features[0]
        if barcodes_path is None and nested_barcodes:
            barcodes_path = nested_barcodes[0]
    if features_path is None or barcodes_path is None:
        raise FileNotFoundError(f"Could not locate 10x feature/barcode tables under {path}")

    features = _read_features(features_path)
    barcodes = _read_barcodes(barcodes_path)
    if matrix.shape[0] != len(features):
        raise ValueError(f"Feature table length {len(features)} does not match matrix rows {matrix.shape[0]}")
    if matrix.shape[1] != len(barcodes):
        raise ValueError(f"Barcode table length {len(barcodes)} does not match matrix columns {matrix.shape[1]}")

    cell_ids = [f"{sample_id}:{barcode}" for barcode in barcodes]
    obs = _sample_obs_frame(
        sample_id=sample_id,
        condition=condition,
        cell_ids=cell_ids,
        barcodes=barcodes,
        extra_metadata=extra_metadata,
        input_path=path,
    )

    parsed: list[_ParsedModality] = []
    for feature_type in features["feature_type"].fillna("Gene Expression").astype(str).unique():
        selector = np.asarray(features["feature_type"].fillna("Gene Expression").astype(str) == feature_type)
        sub_features = features.loc[selector].copy()
        sub_matrix = matrix[selector, :]
        parsed.append(
            _ParsedModality(
                sample_id=sample_id,
                condition=condition,
                feature_type=str(feature_type),
                cell_ids=cell_ids,
                obs=obs.copy(),
                var=sub_features,
                matrix=sub_matrix.tocsr(),
            )
        )
    return parsed


def _read_sample_input(spec: Any) -> tuple[list[_ParsedModality], dict[str, Any]]:
    sample_id = str(_sample_attr(spec, "sample_id"))
    condition = str(_sample_attr(spec, "condition"))
    input_path = _as_path(_sample_attr(spec, "input_path"))
    extra_metadata = dict(_sample_attr(spec, "obs_metadata", {}) or {})

    if input_path.is_dir():
        if (
            (input_path / "matrix.mtx").exists()
            or (input_path / "matrix.mtx.gz").exists()
            or list(input_path.rglob("matrix.mtx"))
            or list(input_path.rglob("matrix.mtx.gz"))
        ):
            parsed = _read_10x_mtx_dir(
                input_path,
                sample_id=sample_id,
                condition=condition,
                extra_metadata=extra_metadata,
            )
            return parsed, {
                "sample_id": sample_id,
                "condition": condition,
                "input_path": str(input_path),
                "input_kind": "10x_mtx",
                "feature_types": sorted({modality.feature_type for modality in parsed}),
                "n_cells": len(parsed[0].cell_ids) if parsed else 0,
            }
        raise FileNotFoundError(f"Unsupported directory input: {input_path}")

    suffix = input_path.suffix.lower()
    if suffix == ".h5" or input_path.name.endswith(".h5"):
        parsed = _read_10x_h5(
            input_path,
            sample_id=sample_id,
            condition=condition,
            extra_metadata=extra_metadata,
        )
        return parsed, {
            "sample_id": sample_id,
            "condition": condition,
            "input_path": str(input_path),
            "input_kind": "10x_h5",
            "feature_types": sorted({modality.feature_type for modality in parsed}),
            "n_cells": len(parsed[0].cell_ids) if parsed else 0,
        }

    raise ValueError(f"Unsupported input path: {input_path}")


def _align_modality_matrix(
    parsed_modalities: list[_ParsedModality],
    *,
    global_cell_ids: list[str],
    feature_type: str,
) -> tuple[sparse.csr_matrix, pd.DataFrame]:
    relevant = [modality for modality in parsed_modalities if modality.feature_type == feature_type]
    if not relevant:
        return sparse.csr_matrix((0, len(global_cell_ids))), pd.DataFrame()

    feature_key_order: list[str] = []
    feature_metadata: dict[str, dict[str, Any]] = {}
    for modality in relevant:
        feature_keys = modality.var.index.astype(str).tolist()
        for key, (_, row) in zip(feature_keys, modality.var.iterrows()):
            if key not in feature_metadata:
                feature_key_order.append(key)
                feature_metadata[key] = row.to_dict()
                feature_metadata[key]["feature_id"] = row.get("feature_id", key)
                feature_metadata[key]["feature_name"] = row.get("feature_name", key)
                feature_metadata[key]["feature_type"] = feature_type

    aligned_matrices: list[sparse.csr_matrix] = []
    global_cell_positions = {cell_id: index for index, cell_id in enumerate(global_cell_ids)}
    global_feature_positions = {feature_id: index for index, feature_id in enumerate(feature_key_order)}

    for modality in relevant:
        local_cols = [global_cell_positions[cell_id] for cell_id in modality.cell_ids]
        local_feature_keys = modality.var.index.astype(str).tolist()
        coo = modality.matrix.tocoo()
        mapped_rows = np.asarray(
            [global_feature_positions[local_feature_keys[row]] for row in coo.row],
            dtype=np.int64,
        )
        aligned = sparse.coo_matrix(
            (coo.data, (mapped_rows, np.asarray(local_cols, dtype=np.int64)[coo.col])),
            shape=(len(feature_key_order), len(global_cell_ids)),
        ).tocsr()
        aligned_matrices.append(aligned)

    if aligned_matrices:
        combined = sum(aligned_matrices[1:], aligned_matrices[0].copy())
    else:
        combined = sparse.csr_matrix((len(feature_key_order), len(global_cell_ids)))

    var = pd.DataFrame.from_dict(feature_metadata, orient="index")
    var.index.name = "feature_id"
    if "feature_name" in var.columns:
        var["feature_name"] = var["feature_name"].astype(str)
    return combined, var


def _build_data_objects(
    parsed_samples: list[list[_ParsedModality]],
    sample_manifests: list[dict[str, Any]],
) -> tuple[Any, dict[str, Any]]:
    flattened = [modality for sample in parsed_samples for modality in sample]
    if not flattened:
        raise ValueError("No sample inputs were provided")

    sample_representatives = [sample[0] for sample in parsed_samples if sample]
    global_cell_ids = [cell_id for sample in sample_representatives for cell_id in sample.cell_ids]
    global_obs = pd.concat([sample.obs for sample in sample_representatives], axis=0)

    feature_types = []
    seen: set[str] = set()
    for modality in flattened:
        if modality.feature_type not in seen:
            seen.add(modality.feature_type)
            feature_types.append(modality.feature_type)

    manifest = {
        "samples": sample_manifests,
        "feature_types": feature_types,
        "n_cells": len(global_cell_ids),
    }

    if len(feature_types) == 1:
        feature_type = feature_types[0]
        combined_matrix, var = _align_modality_matrix(flattened, global_cell_ids=global_cell_ids, feature_type=feature_type)
        data = _make_anndata_like(combined_matrix, global_obs, var, feature_type)
        manifest.update(
            {
                "kind": "h5ad",
                "modalities": [feature_type],
                "n_vars": int(var.shape[0]),
            }
        )
        return data, manifest

    modalities: dict[str, Any] = {}
    modality_summaries: dict[str, dict[str, Any]] = {}
    for feature_type in feature_types:
        combined_matrix, var = _align_modality_matrix(flattened, global_cell_ids=global_cell_ids, feature_type=feature_type)
        modalities[feature_type] = _make_anndata_like(combined_matrix, global_obs.copy(), var, feature_type)
        modality_summaries[feature_type] = {
            "n_vars": int(var.shape[0]),
            "feature_type": feature_type,
        }

    data = _make_mudata_like(modalities, global_obs)
    manifest.update(
        {
            "kind": "h5mu",
            "modalities": feature_types,
            "modality_summaries": modality_summaries,
        }
    )
    return data, manifest


def _make_anndata_like(matrix: sparse.csr_matrix, obs: pd.DataFrame, var: pd.DataFrame, feature_type: str) -> Any:
    obs = obs.copy()
    var = var.copy()
    var.index = var.index.astype(str)
    var.index.name = "feature_id"
    matrix = matrix.tocsr()

    if _AnnData is not None:  # pragma: no cover - dependent on optional stack
        return _AnnData(
            X=matrix.T,
            obs=obs,
            var=var,
            uns={"feature_type": feature_type},
        )

    return _FallbackAnnData(
        X=matrix.T.tocsr(),
        obs=obs,
        var=var,
        uns={"feature_type": feature_type},
    )


def _make_mudata_like(modalities: dict[str, Any], obs: pd.DataFrame) -> Any:
    if _MuData is not None:  # pragma: no cover - dependent on optional stack
        try:
            return _MuData(modalities, obs=obs)
        except Exception:
            try:
                return _MuData(modalities)
            except Exception:
                pass
    fallback_modalities = {key: value if isinstance(value, _FallbackAnnData) else _FallbackAnnData(value.X, value.obs, value.var, value.layers, value.obsm, value.uns) for key, value in modalities.items()}
    return _FallbackMuData(mod=fallback_modalities, obs=obs.copy(), uns={"kind": "multimodal"})


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_dataframe(group: h5py.Group, frame: pd.DataFrame) -> None:
    string_dtype = h5py.string_dtype("utf-8")
    group.create_dataset("_index", data=np.asarray(frame.index.astype(str).tolist(), dtype=object), dtype=string_dtype)
    group.attrs["columns"] = json.dumps(list(map(str, frame.columns)))
    for column in frame.columns:
        values = frame[column]
        if pd.api.types.is_numeric_dtype(values):
            group.create_dataset(str(column), data=np.asarray(values))
        else:
            group.create_dataset(str(column), data=np.asarray(values.astype(str).tolist(), dtype=object), dtype=string_dtype)


def _write_sparse(group: h5py.Group, matrix: sparse.spmatrix) -> None:
    csr = matrix.tocsr()
    group.create_dataset("data", data=csr.data)
    group.create_dataset("indices", data=csr.indices)
    group.create_dataset("indptr", data=csr.indptr)
    group.create_dataset("shape", data=np.asarray(csr.shape, dtype=np.int64))


def _write_matrix(group: h5py.Group, matrix: Any) -> None:
    if sparse.issparse(matrix):
        group.attrs["format"] = "csr"
        _write_sparse(group, matrix)
        return
    array = np.asarray(matrix)
    group.attrs["format"] = "dense"
    group.create_dataset("data", data=array)


def _write_h5ad_like(path: Path, data: _FallbackAnnData) -> None:
    with h5py.File(path, "w") as handle:
        handle.attrs["format"] = "h5ad"
        handle.create_dataset("obs_names", data=np.asarray(data.obs.index.astype(str).tolist(), dtype=object), dtype=h5py.string_dtype("utf-8"))
        handle.create_dataset("var_names", data=np.asarray(data.var.index.astype(str).tolist(), dtype=object), dtype=h5py.string_dtype("utf-8"))
        _write_dataframe(handle.create_group("obs"), data.obs)
        _write_dataframe(handle.create_group("var"), data.var)
        _write_matrix(handle.create_group("X"), data.X)
        layers_group = handle.create_group("layers")
        for key, value in data.layers.items():
            _write_matrix(layers_group.create_group(str(key)), value)
        obsm_group = handle.create_group("obsm")
        for key, value in data.obsm.items():
            _write_matrix(obsm_group.create_group(str(key)), value)
        handle.create_dataset("uns_json", data=np.asarray([json.dumps(data.uns, default=str)], dtype=object), dtype=h5py.string_dtype("utf-8"))


def _write_h5mu_like(path: Path, data: _FallbackMuData) -> None:
    with h5py.File(path, "w") as handle:
        handle.attrs["format"] = "h5mu"
        handle.create_dataset("obs_names", data=np.asarray(data.obs.index.astype(str).tolist(), dtype=object), dtype=h5py.string_dtype("utf-8"))
        _write_dataframe(handle.create_group("obs"), data.obs)
        handle.create_dataset("uns_json", data=np.asarray([json.dumps(data.uns, default=str)], dtype=object), dtype=h5py.string_dtype("utf-8"))
        mod_group = handle.create_group("mod")
        for name, modality in data.mod.items():
            modality_group = mod_group.create_group(str(name))
            modality_group.create_dataset("obs_names", data=np.asarray(modality.obs.index.astype(str).tolist(), dtype=object), dtype=h5py.string_dtype("utf-8"))
            modality_group.create_dataset("var_names", data=np.asarray(modality.var.index.astype(str).tolist(), dtype=object), dtype=h5py.string_dtype("utf-8"))
            _write_dataframe(modality_group.create_group("obs"), modality.obs)
            _write_dataframe(modality_group.create_group("var"), modality.var)
            _write_matrix(modality_group.create_group("X"), modality.X)
            layers_group = modality_group.create_group("layers")
            for key, value in modality.layers.items():
                _write_matrix(layers_group.create_group(str(key)), value)
            obsm_group = modality_group.create_group("obsm")
            for key, value in modality.obsm.items():
                _write_matrix(obsm_group.create_group(str(key)), value)
            modality_group.create_dataset(
                "uns_json",
                data=np.asarray([json.dumps(modality.uns, default=str)], dtype=object),
                dtype=h5py.string_dtype("utf-8"),
            )


def _build_artifact_manifest(
    *,
    output_root: Path,
    data: Any,
    schema_report: SchemaReport,
    ingest_manifest: dict[str, Any],
) -> dict[str, Any]:
    normalized_name = "normalized.h5mu" if ingest_manifest["kind"] == "h5mu" else "normalized.h5ad"
    normalized_path = output_root / normalized_name
    schema_path = output_root / "schema_report.json"
    return {
        **ingest_manifest,
        "output_dir": str(output_root),
        "normalized_path": str(normalized_path),
        "schema_report_path": str(schema_path),
        "schema_issue_count": len(schema_report.issues),
    }


def ingest_samples(
    sample_specs: list[Any],
    output_dir: Path,
    schema_config: dict[str, Any] | None = None,
) -> tuple[Any, SchemaReport, dict[str, Any]]:
    output_root = _ensure_dir(Path(output_dir) / "ingest")
    parsed_samples: list[list[_ParsedModality]] = []
    sample_manifests: list[dict[str, Any]] = []

    for spec in sample_specs:
        parsed, sample_manifest = _read_sample_input(spec)
        parsed_samples.append(parsed)
        sample_manifests.append(sample_manifest)

    data, ingest_manifest = _build_data_objects(parsed_samples, sample_manifests)
    data, schema_report = validate_and_fix_schema(
        data,
        {
            **(schema_config or {}),
            "default_sample_id": sample_manifests[0]["sample_id"] if sample_manifests else None,
            "default_condition": sample_manifests[0]["condition"] if sample_manifests else None,
        },
    )

    normalized_name = "normalized.h5mu" if ingest_manifest["kind"] == "h5mu" else "normalized.h5ad"
    normalized_path = output_root / normalized_name
    if hasattr(data, "write_h5mu") and ingest_manifest["kind"] == "h5mu":
        data.write_h5mu(normalized_path)
    elif hasattr(data, "write_h5ad"):
        data.write_h5ad(normalized_path)
    elif ingest_manifest["kind"] == "h5mu" and _MuData is not None:  # pragma: no cover
        data.write_h5mu(normalized_path)
    elif _AnnData is not None:  # pragma: no cover
        data.write_h5ad(normalized_path)
    else:
        raise TypeError("In-memory object does not support serialization")

    schema_path = output_root / "schema_report.json"
    write_schema_report(schema_report, schema_path)
    manifest = _build_artifact_manifest(
        output_root=output_root,
        data=data,
        schema_report=schema_report,
        ingest_manifest=ingest_manifest,
    )
    return data, schema_report, manifest
