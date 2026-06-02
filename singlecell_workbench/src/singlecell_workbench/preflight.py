from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from singlecell_workbench.config import build_sample_specs, load_config, normalize_config_paths, resolve_output_dir
from singlecell_workbench.modules.ingest import _read_sample_input
from singlecell_workbench.modules.stats import _load_network_table
from singlecell_workbench.provenance import load_manifest_document, sha256_file
from singlecell_workbench.sample_contract import REQUIRED_SAMPLE_FIELDS, gate1_missing_fields


def run_preflight_from_config(config_path: Path, output_dir: Path | None = None) -> dict[str, Any]:
    config_path = config_path.resolve()
    config = normalize_config_paths(load_config(config_path), config_path.parent)
    return run_preflight(config, base_dir=config_path.parent, config_path=config_path, output_dir=output_dir)


def run_preflight(
    config: dict[str, Any],
    *,
    base_dir: Path,
    config_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    sample_specs = build_sample_specs(config, base_dir)
    preflight_dir = (output_dir.resolve() if output_dir is not None else resolve_output_dir(config, base_dir) / "preflight")
    preflight_dir.mkdir(parents=True, exist_ok=True)

    decoupler_cfg = dict(config.get("stats", {}).get("decoupler") or {})
    pathway_network = _as_existing_path(decoupler_cfg.get("pathway_network"))
    tf_network = _as_existing_path(decoupler_cfg.get("tf_network"))
    priors_manifest_path = _infer_priors_manifest_path(pathway_network, tf_network)
    priors_manifest = load_manifest_document(priors_manifest_path)

    annotation_cfg = dict(config.get("annotation") or {})
    reference_manifest_path = _as_existing_path(annotation_cfg.get("reference_manifest"))
    reference_manifest = load_manifest_document(reference_manifest_path)

    sample_ids = [sample.sample_id for sample in sample_specs]
    duplicate_sample_ids = sorted({sample_id for sample_id in sample_ids if sample_ids.count(sample_id) > 1})
    project_conflicts = {
        field: values
        for field in ("organism", "reference_build", "gene_id_type")
        if len(values := sorted({str(value) for value in [getattr(sample, field) for sample in sample_specs] if value})) > 1
    }

    pathway_overlap_reference = _load_network_targets(pathway_network)
    tf_overlap_reference = _load_network_targets(tf_network)
    pathway_namespace = _resolve_prior_namespace(priors_manifest, pathway_overlap_reference)
    tf_namespace = _resolve_prior_namespace(priors_manifest, tf_overlap_reference, analysis_name="tf")

    sample_reports: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    blocking_issue_count = 0
    warning_count = 0

    for sample in sample_specs:
        report = _evaluate_sample(
            sample,
            pathway_targets=pathway_overlap_reference,
            pathway_namespace=pathway_namespace,
            tf_targets=tf_overlap_reference,
            tf_namespace=tf_namespace,
            reference_manifest=reference_manifest,
            annotation_cfg=annotation_cfg,
        )
        sample_reports.append(report)
        if report["status"] == "fail":
            blocking_issue_count += 1
        warning_count += len(report["warnings"])
        summary_rows.append(
            {
                "sample_id": sample.sample_id,
                "status": report["status"],
                "gate1_ready": report["gate1_ready"],
                "input_kind": report["input"].get("kind", ""),
                "declared_modality": sample.modality or "",
                "feature_types": ",".join(report["input"].get("feature_types", [])),
                "organism": sample.organism or "",
                "reference_build": sample.reference_build or "",
                "gene_id_type": sample.gene_id_type or "",
                "pathway_overlap": report["priors"]["pathway"].get("overlap_count", ""),
                "tf_overlap": report["priors"]["tf"].get("overlap_count", ""),
                "missing_required_fields": ",".join(report["missing_required_fields"]),
            }
        )

    project_issues: list[dict[str, Any]] = []
    if duplicate_sample_ids:
        project_issues.append(
            {
                "severity": "error",
                "message": "sample_id values must be unique across the run.",
                "details": duplicate_sample_ids,
            }
        )
        blocking_issue_count += 1
    for field, values in project_conflicts.items():
        project_issues.append(
            {
                "severity": "warning",
                "message": f'Conflicting "{field}" values were detected across samples.',
                "details": values,
            }
        )
        warning_count += 1

    overall_status = "pass"
    if blocking_issue_count:
        overall_status = "fail"
    elif warning_count:
        overall_status = "warn"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": overall_status,
        "gate": "gate1_smoke",
        "project_name": config.get("project_name", "singlecell_workbench"),
        "config_path": str(config_path) if config_path is not None else None,
        "required_gate1_fields": list(REQUIRED_SAMPLE_FIELDS),
        "project_issues": project_issues,
        "project_conflicts": project_conflicts,
        "samples_evaluated": len(sample_specs),
        "samples": sample_reports,
        "priors": {
            "manifest_path": str(priors_manifest_path) if priors_manifest_path is not None else None,
            "manifest_sha256": sha256_file(priors_manifest_path),
            "pathway_network_path": str(pathway_network) if pathway_network is not None else None,
            "tf_network_path": str(tf_network) if tf_network is not None else None,
            "pathway_gene_namespace": pathway_namespace,
            "tf_gene_namespace": tf_namespace,
        },
        "reference": {
            "manifest_path": str(reference_manifest_path) if reference_manifest_path is not None else None,
            "manifest_sha256": sha256_file(reference_manifest_path),
            "summary": _reference_summary(reference_manifest),
        },
    }

    report_path = preflight_dir / "preflight_report.json"
    summary_path = preflight_dir / "preflight_summary.tsv"
    markdown_path = preflight_dir / "preflight.md"
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_summary_table(summary_path, summary_rows)
    markdown_path.write_text(_render_preflight_markdown(payload), encoding="utf-8")

    return {
        "status": overall_status,
        "output_dir": str(preflight_dir),
        "preflight_report": str(report_path),
        "preflight_summary": str(summary_path),
        "preflight_markdown": str(markdown_path),
        "samples_evaluated": len(sample_specs),
        "blocking_issue_count": blocking_issue_count,
        "warning_count": warning_count,
    }


def _evaluate_sample(
    sample: Any,
    *,
    pathway_targets: set[str],
    pathway_namespace: str | None,
    tf_targets: set[str],
    tf_namespace: str | None,
    reference_manifest: dict[str, Any] | None,
    annotation_cfg: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    missing_required = gate1_missing_fields(sample)
    if missing_required:
        warnings.append(f"Missing required Gate 1 fields: {', '.join(missing_required)}")

    input_info: dict[str, Any] = {
        "path": str(sample.input_path),
        "exists": sample.input_path.exists(),
        "readable": os.access(sample.input_path, os.R_OK) if sample.input_path.exists() else False,
        "kind": None,
        "feature_types": [],
        "feature_type_distribution": {},
        "n_cells": None,
    }
    parsed_modalities: list[Any] = []
    if not input_info["exists"]:
        issues.append(f"Input path does not exist: {sample.input_path}")
    elif not input_info["readable"]:
        issues.append(f"Input path is not readable: {sample.input_path}")
    else:
        try:
            parsed_modalities, inferred = _read_sample_input(sample)
        except Exception as exc:
            issues.append(f"Failed to inspect input: {exc}")
        else:
            input_info["kind"] = inferred.get("input_kind")
            input_info["feature_types"] = list(inferred.get("feature_types", []))
            input_info["n_cells"] = inferred.get("n_cells")
            input_info["feature_type_distribution"] = {
                modality.feature_type: int(modality.var.shape[0])
                for modality in parsed_modalities
            }
            modality_consistency = _check_modality_consistency(sample, input_info["feature_types"])
            if modality_consistency is not None:
                if modality_consistency["severity"] == "error":
                    issues.append(modality_consistency["message"])
                else:
                    warnings.append(modality_consistency["message"])
            build_warning = _check_reference_build_consistency(sample, parsed_modalities)
            if build_warning:
                warnings.append(build_warning)

    inferred_gene_namespace = _infer_sample_gene_namespace(parsed_modalities) if parsed_modalities else None
    available_gene_namespaces = _available_sample_gene_namespaces(parsed_modalities) if parsed_modalities else set()
    if (
        sample.gene_id_type
        and available_gene_namespaces
        and _normalize_gene_namespace(sample.gene_id_type) not in available_gene_namespaces
    ):
        warnings.append(
            f'Declared gene_id_type "{sample.gene_id_type}" does not match available feature namespaces "{sorted(available_gene_namespaces)}".'
        )

    pathway_overlap = _compute_overlap(parsed_modalities, sample.gene_id_type, pathway_targets, pathway_namespace)
    tf_overlap = _compute_overlap(parsed_modalities, sample.gene_id_type, tf_targets, tf_namespace)
    if pathway_overlap.get("status") == "completed" and pathway_overlap.get("overlap_count", 0) == 0:
        warnings.append("Pathway prior overlap is zero; check organism and gene namespace alignment.")
    if tf_overlap.get("status") == "completed" and tf_overlap.get("overlap_count", 0) == 0:
        warnings.append("TF prior overlap is zero; check organism and gene namespace alignment.")

    reference_check = _check_reference_consistency(
        sample,
        parsed_modalities=parsed_modalities,
        reference_manifest=reference_manifest,
        annotation_cfg=annotation_cfg,
    )
    warnings.extend(reference_check["warnings"])
    issues.extend(reference_check["issues"])

    status = "pass"
    if issues:
        status = "fail"
    elif warnings:
        status = "warn"

    gate1_ready = not issues and not missing_required
    return {
        "sample_id": sample.sample_id,
        "status": status,
        "gate1_ready": gate1_ready,
        "missing_required_fields": missing_required,
        "declared_fields": {
            "organism": sample.organism,
            "condition": sample.condition,
            "donor": sample.donor,
            "batch": sample.batch,
            "modality": sample.modality,
            "library_type": sample.library_type,
            "chemistry": sample.chemistry,
            "reference_build": sample.reference_build,
            "gene_id_type": sample.gene_id_type,
            "tissue": sample.tissue,
        },
        "input": input_info,
        "inferred_gene_namespace": inferred_gene_namespace,
        "available_gene_namespaces": sorted(available_gene_namespaces),
        "priors": {
            "pathway": pathway_overlap,
            "tf": tf_overlap,
        },
        "annotation_reference": reference_check["summary"],
        "warnings": warnings,
        "issues": issues,
    }


def _check_modality_consistency(sample: Any, feature_types: list[str]) -> dict[str, str] | None:
    declared = _normalize_modality(getattr(sample, "modality", None))
    if declared is None:
        return None
    inferred = _infer_modality_from_feature_types(feature_types)
    if inferred == declared:
        return None
    return {
        "severity": "error",
        "message": f'Declared modality "{sample.modality}" conflicts with inferred input modality "{inferred}".',
    }


def _check_reference_build_consistency(sample: Any, parsed_modalities: list[Any]) -> str | None:
    declared = getattr(sample, "reference_build", None)
    if not declared:
        return None
    observed: set[str] = set()
    for modality in parsed_modalities:
        if "genome" not in modality.var.columns:
            continue
        observed.update(str(value).strip() for value in modality.var["genome"].tolist() if str(value).strip())
    if not observed:
        return None
    if declared not in observed:
        return f'Declared reference_build "{declared}" does not match feature genome values: {sorted(observed)}.'
    return None


def _check_reference_consistency(
    sample: Any,
    *,
    parsed_modalities: list[Any],
    reference_manifest: dict[str, Any] | None,
    annotation_cfg: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    warnings: list[str] = []
    summary = _reference_summary(reference_manifest)
    if reference_manifest is None:
        warnings.append("No annotation reference manifest was provided; reference compatibility could not be validated.")
        return {"summary": summary, "warnings": warnings, "issues": issues}

    reference_species = _normalize_scalar(reference_manifest.get("species") or reference_manifest.get("organism"))
    sample_species = _normalize_scalar(getattr(sample, "organism", None))
    if reference_species and sample_species and reference_species != sample_species:
        issues.append(f'Annotation reference species "{reference_species}" conflicts with sample organism "{sample_species}".')

    reference_tissue = _normalize_scalar(reference_manifest.get("tissue"))
    sample_tissue = _normalize_scalar(getattr(sample, "tissue", None))
    if reference_tissue and sample_tissue and reference_tissue != sample_tissue:
        warnings.append(f'Annotation reference tissue "{reference_tissue}" differs from sample tissue "{sample_tissue}".')
    elif reference_tissue and not sample_tissue:
        warnings.append("Annotation reference declares a tissue, but the sample metadata does not.")

    reference_modality = _normalize_modality(reference_manifest.get("modality"))
    declared_modality = _normalize_modality(getattr(sample, "modality", None) or annotation_cfg.get("modality"))
    inferred_modality = _infer_modality_from_feature_types([modality.feature_type for modality in parsed_modalities])
    effective_modality = declared_modality or inferred_modality
    if reference_modality and effective_modality and reference_modality != effective_modality:
        warnings.append(
            f'Annotation reference modality "{reference_manifest.get("modality")}" differs from sample/annotation modality "{effective_modality}".'
        )

    reference_namespace = _normalize_gene_namespace(
        reference_manifest.get("gene_namespace") or reference_manifest.get("gene_identifier_namespace")
    )
    sample_namespace = _normalize_gene_namespace(getattr(sample, "gene_id_type", None))
    if reference_namespace and sample_namespace and reference_namespace != sample_namespace:
        warnings.append(
            f'Annotation reference gene namespace "{reference_namespace}" differs from sample gene_id_type "{sample_namespace}".'
        )

    return {"summary": summary, "warnings": warnings, "issues": issues}


def _compute_overlap(
    parsed_modalities: list[Any],
    gene_id_type: str | None,
    targets: set[str],
    prior_namespace: str | None,
) -> dict[str, Any]:
    if not parsed_modalities:
        return {"status": "skipped", "reason": "input inspection failed"}
    if not targets:
        return {"status": "skipped", "reason": "network targets unavailable"}
    genes = _extract_sample_genes(parsed_modalities, gene_id_type)
    if not genes:
        return {"status": "skipped", "reason": "gene features unavailable for overlap"}
    normalized_genes = {_normalize_gene_value(gene, prior_namespace) for gene in genes}
    normalized_targets = {_normalize_gene_value(target, prior_namespace) for target in targets}
    normalized_genes.discard("")
    normalized_targets.discard("")
    overlap = normalized_genes & normalized_targets
    return {
        "status": "completed",
        "gene_namespace": prior_namespace,
        "sample_gene_count": len(normalized_genes),
        "network_target_count": len(normalized_targets),
        "overlap_count": len(overlap),
        "overlap_fraction_of_sample": (len(overlap) / len(normalized_genes)) if normalized_genes else 0.0,
        "overlap_fraction_of_network": (len(overlap) / len(normalized_targets)) if normalized_targets else 0.0,
    }


def _extract_sample_genes(parsed_modalities: list[Any], gene_id_type: str | None) -> set[str]:
    working_modality = next((modality for modality in parsed_modalities if modality.feature_type == "Gene Expression"), None)
    if working_modality is None and parsed_modalities:
        working_modality = parsed_modalities[0]
    if working_modality is None:
        return set()

    namespace = _normalize_gene_namespace(gene_id_type) or _infer_sample_gene_namespace(parsed_modalities)
    if namespace == "ensembl_gene_id":
        values = working_modality.var.get("feature_id", working_modality.var.index)
    else:
        values = working_modality.var.get("feature_name", working_modality.var.index)
    return {str(value).strip() for value in list(values) if str(value).strip()}


def _infer_sample_gene_namespace(parsed_modalities: list[Any]) -> str | None:
    available = _available_sample_gene_namespaces(parsed_modalities)
    if "gene_symbol" in available:
        return "gene_symbol"
    if "ensembl_gene_id" in available:
        return "ensembl_gene_id"
    return None


def _available_sample_gene_namespaces(parsed_modalities: list[Any]) -> set[str]:
    working_modality = next((modality for modality in parsed_modalities if modality.feature_type == "Gene Expression"), None)
    if working_modality is None and parsed_modalities:
        working_modality = parsed_modalities[0]
    if working_modality is None:
        return set()

    namespaces: set[str] = set()
    feature_ids = [str(value) for value in list(working_modality.var.get("feature_id", working_modality.var.index))]
    if feature_ids:
        ensembl_hits = sum(1 for value in feature_ids if value.upper().startswith(("ENSG", "ENSMUSG", "ENSGALG", "ENSRNOG")))
        if ensembl_hits / len(feature_ids) >= 0.6:
            namespaces.add("ensembl_gene_id")

    feature_names = [str(value) for value in list(working_modality.var.get("feature_name", []))]
    if feature_names:
        symbol_like = sum(
            1
            for value in feature_names
            if value and not value.upper().startswith(("ENSG", "ENSMUSG", "ENSGALG", "ENSRNOG"))
        )
        if symbol_like / len(feature_names) >= 0.6:
            namespaces.add("gene_symbol")

    if not namespaces:
        namespaces.add("gene_symbol")
    return namespaces


def _load_network_targets(path: Path | None) -> set[str]:
    if path is None:
        return set()
    return {str(row.get("target", "")).strip() for row in _load_network_table(path) if str(row.get("target", "")).strip()}


def _infer_priors_manifest_path(pathway_network: Path | None, tf_network: Path | None) -> Path | None:
    candidates = []
    for path in (pathway_network, tf_network):
        if path is None:
            continue
        candidate = path.parent / "manifest.json"
        if candidate.exists():
            candidates.append(candidate)
    if not candidates:
        return None
    return candidates[0]


def _resolve_prior_namespace(
    priors_manifest: dict[str, Any] | None,
    targets: set[str],
    *,
    analysis_name: str = "pathway",
) -> str | None:
    if priors_manifest is not None:
        direct = priors_manifest.get("gene_identifier_namespace")
        if direct:
            return _normalize_gene_namespace(direct)
        analysis_block = priors_manifest.get(analysis_name) or priors_manifest.get("resources", {}).get(analysis_name)
        if isinstance(analysis_block, dict):
            namespace = analysis_block.get("gene_identifier_namespace")
            if namespace:
                return _normalize_gene_namespace(namespace)
    if not targets:
        return None
    ensembl_hits = sum(1 for value in targets if value.upper().startswith(("ENSG", "ENSMUSG", "ENSGALG", "ENSRNOG")))
    return "ensembl_gene_id" if ensembl_hits / len(targets) >= 0.6 else "gene_symbol"


def _normalize_gene_namespace(value: Any) -> str | None:
    text = _normalize_scalar(value)
    if text is None:
        return None
    aliases = {
        "symbol": "gene_symbol",
        "gene_symbol": "gene_symbol",
        "genesymbol": "gene_symbol",
        "hgnc_symbol": "gene_symbol",
        "ensembl": "ensembl_gene_id",
        "ensembl_gene_id": "ensembl_gene_id",
        "ensembl_id": "ensembl_gene_id",
    }
    return aliases.get(text, text)


def _normalize_gene_value(value: str, namespace: str | None) -> str:
    text = str(value).strip()
    if namespace == "ensembl_gene_id":
        return text.split(".")[0].upper()
    return text.upper()


def _normalize_modality(value: Any) -> str | None:
    text = _normalize_scalar(value)
    if text is None:
        return None
    aliases = {
        "rna": "rna",
        "gex": "rna",
        "gene expression": "rna",
        "gene_expression": "rna",
        "antibody": "antibody",
        "adt": "antibody",
        "antibody capture": "antibody",
        "antibody_capture": "antibody",
        "multimodal": "multimodal",
        "multiome": "multimodal",
        "cite_seq": "multimodal",
        "cite-seq": "multimodal",
    }
    return aliases.get(text, text)


def _infer_modality_from_feature_types(feature_types: list[str]) -> str | None:
    if not feature_types:
        return None
    normalized = {_normalize_modality(feature_type) or str(feature_type) for feature_type in feature_types}
    if len(normalized) > 1:
        return "multimodal"
    return next(iter(normalized))


def _reference_summary(reference_manifest: dict[str, Any] | None) -> dict[str, Any] | None:
    if reference_manifest is None:
        return None
    return {
        "reference_name": reference_manifest.get("reference_name") or reference_manifest.get("name"),
        "species": reference_manifest.get("species") or reference_manifest.get("organism"),
        "tissue": reference_manifest.get("tissue"),
        "modality": reference_manifest.get("modality"),
        "training_source": reference_manifest.get("training_source"),
        "training_version": reference_manifest.get("training_version"),
        "gene_namespace": reference_manifest.get("gene_namespace") or reference_manifest.get("gene_identifier_namespace"),
        "label_fields": reference_manifest.get("label_fields"),
        "model_path": reference_manifest.get("model_path"),
        "ontology_vocabulary": reference_manifest.get("ontology_vocabulary") or reference_manifest.get("label_vocabulary"),
    }


def _write_summary_table(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sample_id",
        "status",
        "gate1_ready",
        "input_kind",
        "declared_modality",
        "feature_types",
        "organism",
        "reference_build",
        "gene_id_type",
        "pathway_overlap",
        "tf_overlap",
        "missing_required_fields",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def _render_preflight_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Preflight Summary",
        "",
        f"- Status: `{payload['status']}`",
        f"- Project: `{payload['project_name']}`",
        f"- Samples evaluated: `{payload['samples_evaluated']}`",
        "",
        "## Project-level findings",
    ]
    if payload["project_issues"]:
        for issue in payload["project_issues"]:
            lines.append(f"- {issue['severity']}: {issue['message']} ({', '.join(issue.get('details', []))})")
    else:
        lines.append("- No blocking project-level issues detected.")
    lines.extend(
        [
            "",
            "## Sample-level findings",
        ]
    )
    for sample in payload["samples"]:
        lines.append(f"- `{sample['sample_id']}`: status=`{sample['status']}`, gate1_ready=`{sample['gate1_ready']}`")
        if sample["issues"]:
            for issue in sample["issues"]:
                lines.append(f"  - issue: {issue}")
        if sample["warnings"]:
            for warning in sample["warnings"]:
                lines.append(f"  - warning: {warning}")
    return "\n".join(lines) + "\n"


def _as_existing_path(value: Any) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.exists() else None


def _normalize_scalar(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None
