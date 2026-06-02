configfile: "config.yaml"

MODULES = [
    module_name
    for module_name, module_config in config["modules"].items()
    if module_name != "benchmark_run_manifest" and module_config.get("enabled", True)
]

MODULE_DEPENDENCIES = {
    "target_preparation": [],
    "compound_library_preparation": [],
    "classical_docking": ["target_preparation", "compound_library_preparation"],
    "ai_reranking": ["classical_docking"],
    "filtering": ["ai_reranking"],
    "clustering_and_prioritization": ["filtering"],
    "report_generation": [
        "target_preparation",
        "compound_library_preparation",
        "classical_docking",
        "ai_reranking",
        "filtering",
        "clustering_and_prioritization",
    ],
    "benchmark_evaluation": [
        "target_preparation",
        "compound_library_preparation",
        "classical_docking",
        "ai_reranking",
        "filtering",
        "clustering_and_prioritization",
    ],
    "run_state_checker": [
        "target_preparation",
        "compound_library_preparation",
        "classical_docking",
        "ai_reranking",
        "filtering",
        "clustering_and_prioritization",
        "report_generation",
        "benchmark_evaluation",
    ],
}


def module_inputs(wildcards):
    module_name = wildcards.module
    inputs = [config["project"]["run_manifest"]]
    inputs.extend(
        f"07_results/modules/{dependency}/done.json"
        for dependency in MODULE_DEPENDENCIES.get(module_name, [])
        if dependency in MODULES
    )
    return inputs


rule all:
    input:
        config["project"]["run_manifest"],
        expand("07_results/modules/{module}/done.json", module=MODULES)


rule build_run_manifest:
    input:
        datasets=config["benchmark"]["datasets_manifest"],
        targets=config["benchmark"]["targets_manifest"],
        libraries=config["benchmark"]["compound_libraries_manifest"],
        cases=config["benchmark"]["benchmark_cases_manifest"],
    output:
        config["project"]["run_manifest"]
    log:
        "07_results/logs/benchmark_run_manifest.log"
    shell:
        "python 01_tools/generate_run_manifest.py "
        "--project-name {config[project][name]} "
        "--project-root {config[project][server_root]} "
        "--datasets {input.datasets} "
        "--targets {input.targets} "
        "--libraries {input.libraries} "
        "--cases {input.cases} "
        "--output {output} > {log} 2>&1"


rule run_module:
    input:
        module_inputs
    output:
        "07_results/modules/{module}/done.json"
    log:
        "07_results/logs/{module}.log"
    params:
        script="06_scripts/modules/{module}.py",
        configfile="config.yaml",
        input_manifest=lambda wildcards: config["modules"][wildcards.module]["input_manifest"],
        project_root=config["project"]["server_root"],
        run_manifest=config["project"]["run_manifest"],
    shell:
        "python {params.script} "
        "--module {wildcards.module} "
        "--config {params.configfile} "
        "--project-root {params.project_root} "
        "--run-manifest {params.run_manifest} "
        "--input-manifest {params.input_manifest} "
        "--output {output} > {log} 2>&1"
