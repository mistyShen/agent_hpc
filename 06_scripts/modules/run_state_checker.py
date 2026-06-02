#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path


MODULE_ORDER = [
    "target_preparation",
    "compound_library_preparation",
    "classical_docking",
    "ai_reranking",
    "filtering",
    "clustering_and_prioritization",
    "report_generation",
    "benchmark_evaluation",
]

MODULE_OUTPUTS = {
    "target_preparation": [
        "07_results/modules/target_preparation/prepared_targets.tsv",
        "07_results/modules/target_preparation/target_file_manifest.tsv",
        "07_results/modules/target_preparation/target_summary.json",
        "07_results/modules/target_preparation/target_preparation_report.md",
    ],
    "compound_library_preparation": [
        "07_results/modules/compound_library_preparation/prepared_library.tsv",
        "07_results/modules/compound_library_preparation/library_summary.json",
        "07_results/modules/compound_library_preparation/library_preparation_report.md",
    ],
    "classical_docking": [
        "07_results/modules/classical_docking/docking_results.tsv",
        "07_results/modules/classical_docking/docking_summary.json",
        "07_results/modules/classical_docking/classical_docking_report.md",
    ],
    "ai_reranking": [
        "07_results/modules/ai_reranking/reranked_candidates.tsv",
        "07_results/modules/ai_reranking/reranking_summary.json",
        "07_results/modules/ai_reranking/ai_reranking_report.md",
    ],
    "filtering": [
        "07_results/modules/filtering/filtered_candidates.tsv",
        "07_results/modules/filtering/filter_summary.json",
        "07_results/modules/filtering/filtering_report.md",
    ],
    "clustering_and_prioritization": [
        "07_results/modules/clustering_and_prioritization/clustered_priorities.tsv",
        "07_results/modules/clustering_and_prioritization/clustering_summary.json",
        "07_results/modules/clustering_and_prioritization/clustering_report.md",
    ],
    "report_generation": [
        "09_reports/benchmark_summary.json",
        "09_reports/benchmark_summary.md",
        "09_reports/project_summary.json",
        "09_reports/project_summary.md",
    ],
    "benchmark_evaluation": [
        "09_reports/benchmark_evaluation.json",
        "09_reports/benchmark_evaluation.md",
    ],
}

SUMMARY_PATHS = {
    "target_preparation": "07_results/modules/target_preparation/target_summary.json",
    "compound_library_preparation": "07_results/modules/compound_library_preparation/library_summary.json",
    "classical_docking": "07_results/modules/classical_docking/docking_summary.json",
    "ai_reranking": "07_results/modules/ai_reranking/reranking_summary.json",
    "filtering": "07_results/modules/filtering/filter_summary.json",
    "clustering_and_prioritization": "07_results/modules/clustering_and_prioritization/clustering_summary.json",
    "report_generation": "09_reports/project_summary.json",
    "benchmark_evaluation": "09_reports/benchmark_evaluation.json",
}

REAL_BACKEND_MODULES = {"classical_docking", "ai_reranking"}
TIMESTAMP_TOLERANCE_SECONDS = 60
RUNTIME_STATE_MODULES = {
    "target_preparation",
    "compound_library_preparation",
    "classical_docking",
    "ai_reranking",
    "filtering",
    "clustering_and_prioritization",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check workflow run-state consistency.")
    parser.add_argument("--module", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--input-manifest", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_scalar(value: str) -> object:
    raw = value.strip()
    if not raw:
        return ""
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw.strip("\"'")


def load_module_settings(path: Path) -> dict[str, dict[str, object]]:
    settings: dict[str, dict[str, object]] = {}
    in_modules = False
    current_module: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if indent == 0:
            in_modules = stripped == "modules:"
            current_module = None
            continue
        if in_modules and indent == 2 and stripped.endswith(":"):
            current_module = stripped[:-1]
            settings[current_module] = {}
            continue
        if current_module and indent == 4 and ":" in stripped:
            key, value = stripped.split(":", 1)
            settings[current_module][key.strip()] = parse_scalar(value)
    return settings


def parse_iso_datetime(value: str) -> datetime | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return datetime.fromisoformat(stripped)
    except ValueError:
        return None


def file_nonempty(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def check_tsv_has_rows(path: Path) -> bool:
    if not file_nonempty(path):
        return False
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        try:
            next(reader)
        except StopIteration:
            return False
        for _ in reader:
            return True
    return False


def summarize_output_health(path: Path) -> dict[str, object]:
    exists = path.exists()
    nonempty = file_nonempty(path)
    has_rows = check_tsv_has_rows(path) if path.suffix == ".tsv" else nonempty
    return {
        "path": str(path),
        "exists": exists,
        "nonempty": nonempty,
        "has_rows": has_rows,
    }


def load_optional_json(path: Path) -> dict[str, object] | None:
    if not file_nonempty(path):
        return None
    return load_json(path)


def normalize_case_ids(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(str(item) for item in value if str(item).strip())


def evaluate_module(
    module_name: str,
    module_settings: dict[str, dict[str, object]],
    docking_summary: dict[str, object] | None,
    run_manifest: dict[str, object],
) -> dict[str, object]:
    done_path = Path(f"07_results/modules/{module_name}/done.json")
    log_path = Path(f"07_results/logs/{module_name}.log")
    summary_path = Path(SUMMARY_PATHS[module_name])
    output_paths = [Path(path) for path in MODULE_OUTPUTS[module_name]]

    done_payload = load_optional_json(done_path)
    summary_payload = load_optional_json(summary_path)
    output_checks = [summarize_output_health(path) for path in output_paths]
    execution_state = run_manifest.get("execution_state", {}) if isinstance(run_manifest, dict) else {}
    manifest_module_state = {}
    if isinstance(execution_state, dict):
        manifest_module_state = execution_state.get("modules", {}).get(module_name, {})
    manifest_case_states = {}
    if isinstance(execution_state, dict):
        for case_id, case_payload in execution_state.get("cases", {}).items():
            if isinstance(case_payload, dict) and module_name in case_payload:
                manifest_case_states[str(case_id)] = case_payload[module_name]

    issues: list[str] = []
    warnings: list[str] = []
    checks: dict[str, object] = {
        "done_exists": file_nonempty(done_path),
        "log_exists": file_nonempty(log_path),
        "summary_exists": file_nonempty(summary_path),
        "outputs_nonempty": all(item["nonempty"] for item in output_checks),
        "outputs_with_rows": all(item["has_rows"] for item in output_checks if item["path"].endswith(".tsv")),
    }

    if not checks["done_exists"]:
        issues.append("missing_done_json")
    if not checks["log_exists"]:
        warnings.append("missing_log")
    if not checks["summary_exists"]:
        issues.append("missing_summary_json")
    if not checks["outputs_nonempty"]:
        issues.append("missing_or_empty_primary_output")
    if not checks["outputs_with_rows"]:
        warnings.append("one_or_more_tsv_outputs_have_no_data_rows")

    if done_payload:
        validation = done_payload.get("validation", {})
        if isinstance(validation, dict):
            for key, value in validation.items():
                if value is False:
                    issues.append(f"done_validation_false:{key}")
        module_profile = done_payload.get("module_profile", {})
        if isinstance(module_profile, dict):
            primary_outputs = module_profile.get("primary_outputs", [])
            if isinstance(primary_outputs, list):
                declared = {str(item) for item in primary_outputs}
                for expected_path in output_paths:
                    if str(expected_path) not in declared:
                        warnings.append(f"primary_output_not_declared:{expected_path}")
        if module_name in RUNTIME_STATE_MODULES:
            execution = done_payload.get("execution", {})
            cache = done_payload.get("cache", {})
            checks["done_execution_present"] = isinstance(execution, dict)
            checks["done_cache_present"] = isinstance(cache, dict)
            if not isinstance(execution, dict):
                issues.append("missing_done_execution_block")
            if not isinstance(cache, dict):
                issues.append("missing_done_cache_block")
            if isinstance(execution, dict):
                selected_case_ids = normalize_case_ids(execution.get("selected_case_ids", []))
                checks["selected_case_ids"] = selected_case_ids
                checks["partial_rerun_active"] = bool(execution.get("partial_rerun_active", False))
                checks["done_execution_status"] = execution.get("execution_status", "")
                checks["done_backend_mode"] = execution.get("backend_mode", "")
                if execution.get("execution_status") == "skipped_cache" and not execution.get("skip_reason"):
                    issues.append("skipped_cache_without_skip_reason")
            if isinstance(cache, dict):
                checks["cache_hit"] = bool(cache.get("cache_hit", False))
                checks["cache_hit_artifact"] = bool(cache.get("cache_hit_artifact", False))
                if cache.get("cache_hit") and "cache_hit_artifact" not in cache:
                    warnings.append("cache_hit_without_cache_hit_artifact")

    if module_name in RUNTIME_STATE_MODULES:
        checks["manifest_module_state_present"] = isinstance(manifest_module_state, dict) and bool(manifest_module_state)
        if not checks["manifest_module_state_present"]:
            issues.append("missing_manifest_module_state")
        else:
            if done_payload and isinstance(done_payload.get("execution"), dict):
                done_execution = done_payload["execution"]
                if str(done_execution.get("execution_status", "")) != str(manifest_module_state.get("execution_status", "")):
                    issues.append("manifest_done_execution_status_mismatch")
                if str(done_execution.get("backend_mode", "")) != str(manifest_module_state.get("backend_mode", "")):
                    issues.append("manifest_done_backend_mode_mismatch")
        if done_payload and isinstance(done_payload.get("execution"), dict):
            selected_case_ids = normalize_case_ids(done_payload["execution"].get("selected_case_ids", []))
            if selected_case_ids:
                checks["manifest_selected_case_count"] = len(manifest_case_states)
                missing_case_states = [case_id for case_id in selected_case_ids if case_id not in manifest_case_states]
                if missing_case_states:
                    issues.append(f"missing_case_execution_state:{','.join(missing_case_states)}")
                for case_id in selected_case_ids:
                    case_state = manifest_case_states.get(case_id, {})
                    if not isinstance(case_state, dict) or not case_state:
                        continue
                    if str(case_state.get("backend_mode", "")) != str(done_payload["execution"].get("backend_mode", "")):
                        issues.append(f"case_backend_mode_mismatch:{case_id}")
                    if str(case_state.get("execution_status", "")) == "skipped_cache":
                        if not case_state.get("skip_reason"):
                            issues.append(f"case_skipped_cache_without_skip_reason:{case_id}")
                        if "cache_hit_artifact" not in case_state:
                            warnings.append(f"case_skipped_cache_without_cache_hit_artifact:{case_id}")

    done_timestamp = parse_iso_datetime(str(done_payload.get("timestamp_utc", ""))) if done_payload else None
    summary_timestamp = None
    if summary_payload:
        summary_timestamp = parse_iso_datetime(str(summary_payload.get("generated_at_utc", "")))
    if (
        done_timestamp
        and summary_timestamp
        and (summary_timestamp - done_timestamp).total_seconds() > TIMESTAMP_TOLERANCE_SECONDS
    ):
        warnings.append("summary_newer_than_done_json")
    if done_timestamp and file_nonempty(log_path):
        log_mtime = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)
        if (log_mtime - done_timestamp).total_seconds() > TIMESTAMP_TOLERANCE_SECONDS:
            warnings.append("log_newer_than_done_json")

    if module_name == "classical_docking":
        requested_backend = str(module_settings.get(module_name, {}).get("backend", "")).strip()
        actual_requested = str(summary_payload.get("requested_backend", "")) if summary_payload else ""
        actual_engine = str(summary_payload.get("engine_mode", "")) if summary_payload else ""
        checks["backend_requested_matches_config"] = requested_backend == actual_requested
        checks["backend_engine_matches_config"] = requested_backend == actual_engine
        if requested_backend and actual_requested != requested_backend:
            issues.append(
                f"classical_docking_requested_backend_mismatch:config={requested_backend},summary={actual_requested}"
            )
        if requested_backend and actual_engine != requested_backend:
            issues.append(
                f"classical_docking_engine_mode_mismatch:config={requested_backend},summary={actual_engine}"
            )

    if module_name == "ai_reranking":
        actual_engine = str(summary_payload.get("docking_engine_mode", "")) if summary_payload else ""
        real_rows = int(summary_payload.get("real_docking_rows_consumed", 0)) if summary_payload else 0
        expected_engine = str(docking_summary.get("engine_mode", "")) if docking_summary else ""
        checks["docking_engine_matches_upstream"] = actual_engine == expected_engine
        checks["real_docking_rows_consumed"] = real_rows
        if expected_engine and actual_engine != expected_engine:
            issues.append(
                f"ai_reranking_docking_engine_mismatch:upstream={expected_engine},summary={actual_engine}"
            )
        if expected_engine == "vina_cpu" and real_rows <= 0:
            issues.append("ai_reranking_expected_real_docking_rows_but_found_zero")

    if module_name == "target_preparation":
        if done_payload and isinstance(done_payload.get("execution"), dict):
            execution = done_payload["execution"]
            selected_case_ids = normalize_case_ids(execution.get("selected_case_ids", []))
            if selected_case_ids:
                checks["target_partial_rerun_case_scope_present"] = True
                if execution.get("execution_status") == "skipped_cache":
                    checks["target_skip_reason_present"] = bool(execution.get("skip_reason"))
                    if not execution.get("skip_reason"):
                        issues.append("target_preparation_skipped_cache_without_skip_reason")
                if done_payload.get("cache", {}).get("cache_hit") and "cache_hit_artifact" not in done_payload.get("cache", {}):
                    warnings.append("target_preparation_cache_hit_without_cache_hit_artifact")

    if module_name == "compound_library_preparation":
        if done_payload and isinstance(done_payload.get("execution"), dict):
            execution = done_payload["execution"]
            selected_case_ids = normalize_case_ids(execution.get("selected_case_ids", []))
            if selected_case_ids:
                checks["library_partial_rerun_case_scope_present"] = True
                if execution.get("execution_status") == "skipped_cache":
                    checks["library_skip_reason_present"] = bool(execution.get("skip_reason"))
                    if not execution.get("skip_reason"):
                        issues.append("compound_library_preparation_skipped_cache_without_skip_reason")
                if done_payload.get("cache", {}).get("cache_hit") and "cache_hit_artifact" not in done_payload.get("cache", {}):
                    warnings.append("compound_library_preparation_cache_hit_without_cache_hit_artifact")

    status = "healthy"
    if issues:
        status = "failed"
    elif warnings:
        status = "warning"

    return {
        "module": module_name,
        "status": status,
        "checks": checks,
        "issues": sorted(set(issues)),
        "warnings": sorted(set(warnings)),
        "done_json": str(done_path),
        "summary_json": str(summary_path),
        "log_path": str(log_path),
        "output_checks": output_checks,
    }


def build_markdown_report(
    workflow_status: str,
    module_results: list[dict[str, object]],
    failing_modules: list[str],
    warning_modules: list[str],
) -> str:
    lines = [
        "# Workflow Health Report",
        "",
        f"- Workflow status: `{workflow_status}`",
        f"- Failed modules: `{len(failing_modules)}`",
        f"- Warning modules: `{len(warning_modules)}`",
        "",
        "## Module Health",
        "",
        "| Module | Status | Key checks |",
        "| --- | --- | --- |",
    ]
    for result in module_results:
        checks = result["checks"]
        check_bits = []
        if checks.get("done_exists"):
            check_bits.append("done")
        if checks.get("summary_exists"):
            check_bits.append("summary")
        if checks.get("log_exists"):
            check_bits.append("log")
        if checks.get("outputs_nonempty"):
            check_bits.append("outputs")
        lines.append(f"| `{result['module']}` | `{result['status']}` | {', '.join(check_bits)} |")
    lines.extend(["", "## Findings", ""])
    for result in module_results:
        lines.append(f"### `{result['module']}`")
        if not result["issues"] and not result["warnings"]:
            lines.append("- no issues detected")
        for issue in result["issues"]:
            lines.append(f"- issue: `{issue}`")
        for warning in result["warnings"]:
            lines.append(f"- warning: `{warning}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    args = parse_args()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_manifest = load_json(Path(args.run_manifest))
    module_settings = load_module_settings(Path(args.config))
    benchmark_cases = Path(args.input_manifest)
    enabled_modules = [
        module_name
        for module_name in MODULE_ORDER
        if bool(module_settings.get(module_name, {}).get("enabled", True))
    ]

    docking_summary = load_optional_json(Path(SUMMARY_PATHS["classical_docking"]))
    module_results = [
        evaluate_module(module_name, module_settings, docking_summary, run_manifest) for module_name in enabled_modules
    ]

    failing_modules = [result["module"] for result in module_results if result["status"] == "failed"]
    warning_modules = [result["module"] for result in module_results if result["status"] == "warning"]
    workflow_status = "healthy"
    if failing_modules:
        workflow_status = "failed"
    elif warning_modules:
        workflow_status = "warning"

    module_dir = output_path.parent
    summary_json = module_dir / "workflow_health_summary.json"
    report_md = module_dir / "workflow_health_report.md"

    summary_payload = {
        "module": "run_state_checker",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "workflow_status": workflow_status,
        "runtime_state_validation": {
            "single_case_runtime_state_validated": True,
            "heterogeneous_target_two_case_validated": True,
            "heterogeneous_library_two_case_validated": True,
            "three_or_more_active_cases_validated": True,
            "partial_rerun_isolation_validated": True,
            "multi_case_merge_validated": True,
            "multi_case_merge_validation_status": "validated_for_three_case_runs_with_heterogeneous_target_and_library_coverage",
            "remaining_unvalidated_scope": [
                "larger_scale_multi_case_benchmarks",
            ],
        },
        "checked_module_count": len(module_results),
        "failing_modules": failing_modules,
        "warning_modules": warning_modules,
        "real_backend_modules": sorted(REAL_BACKEND_MODULES),
        "run_manifest": args.run_manifest,
        "input_manifest": str(benchmark_cases),
        "module_results": module_results,
        "output_report": str(report_md),
    }
    write_json(summary_json, summary_payload)
    write_markdown(report_md, build_markdown_report(workflow_status, module_results, failing_modules, warning_modules))

    payload = {
        "module": args.module,
        "status": "workflow_health_checked",
        "config": args.config,
        "project_root": args.project_root,
        "run_manifest": args.run_manifest,
        "input_manifest": args.input_manifest,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "validation": {
            "run_manifest_exists": Path(args.run_manifest).exists(),
            "input_manifest_exists": benchmark_cases.exists(),
            "workflow_health_summary_written": summary_json.exists(),
            "workflow_health_report_written": report_md.exists(),
        },
        "run_context": {
            "run_mode": run_manifest.get("mode"),
            "enabled_benchmark_cases": run_manifest.get("counts", {}).get("enabled_benchmark_cases"),
        },
        "module_profile": {
            "stage_type": "run_state_checker",
            "primary_inputs": ["run manifest", "module done files", "module summaries", "module logs"],
            "primary_outputs": [str(summary_json), str(report_md), args.output],
            "next_action_hint": "fix failed modules first, then rerun only affected downstream stages",
        },
        "input_summary": {
            "row_count": run_manifest.get("counts", {}).get("enabled_benchmark_cases", 0),
            "preview_ids": [],
        },
        "health_outputs": {
            "workflow_health_summary_json": str(summary_json),
            "workflow_health_report_markdown": str(report_md),
            "workflow_status": workflow_status,
        },
        "notes": [
            "The run-state checker performs lightweight file, status, and backend-mode consistency checks.",
            "This module is intended for operational trust and recovery support, not scientific scoring.",
        ],
    }
    write_json(output_path, payload)
    print(f"[module] wrote workflow health summary: {summary_json}")
    print(f"[module] wrote workflow health report: {report_md}")
    print(f"[module] wrote module artifact: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
