#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


PUBLIC_DATASETS = {
    "scatac": {
        "title": "10x PBMC scATAC public tutorial data",
        "status": "manifest_only",
        "required_inputs": ["fragments.tsv.gz", "fragments.tsv.gz.tbi", "peak_bc_matrix.h5 或 peaks/barcodes/matrix"],
        "source_note": "用于 Signac/scATAC smoke test；实际下载可替换为 10x PBMC ATAC raw/filtered feature matrix 与 fragments。",
    },
    "multiome": {
        "title": "10x Human PBMC Multiome ATAC + Gene Expression",
        "status": "manifest_only",
        "required_inputs": ["filtered_feature_bc_matrix.h5", "atac_fragments.tsv.gz", "atac_fragments.tsv.gz.tbi"],
        "source_note": "用于 WNN/multi-modal clustering/linkage smoke test；大文件下载建议作为单独 Slurm 作业执行。",
    },
    "vdj": {
        "title": "10x Cell Ranger VDJ contig/clonotype outputs",
        "status": "manifest_only",
        "required_inputs": ["filtered_contig_annotations.csv", "clonotypes.csv"],
        "source_note": "用于 scirpy/scRepertoire clonotype/diversity/VJ usage smoke test。",
    },
    "spatial": {
        "title": "10x Visium public spatial expression data",
        "status": "manifest_only",
        "required_inputs": ["filtered_feature_bc_matrix.h5", "spatial/tissue_positions*.csv", "spatial/scalefactors_json.json"],
        "source_note": "可用 10x Visium 或 Bioconductor TENxVisiumData；图像数据较大，建议 Slurm 单独下载。",
    },
    "cite_seq": {
        "title": "Public CITE-seq / ADT feature-barcode matrix",
        "status": "manifest_only",
        "required_inputs": ["filtered_feature_bc_matrix.h5 或 mtx + ADT features"],
        "source_note": "用于 ADT QC、DSB/CLR normalization、RNA+protein WNN smoke test。",
    },
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare public single-cell data manifest placeholders.")
    parser.add_argument("--root", type=Path, default=Path("/shared/shen/2026/ultimate"))
    parser.add_argument("--mode", choices=["manifest"], default="manifest")
    args = parser.parse_args()
    root = args.root.resolve()
    generated = []
    for key, payload in PUBLIC_DATASETS.items():
        out_dir = root / "public_data" / key
        out_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dataset_key": key,
            "download_status": payload["status"],
            "title": payload["title"],
            "required_inputs": payload["required_inputs"],
            "source_note": payload["source_note"],
            "validation_status": "requires_download",
            "reason": "当前作业只写入公共数据契约，真实数据下载与解析由后续模态 smoke job 执行。",
        }
        path = out_dir / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        generated.append(str(path))
    print(json.dumps({"generated": generated}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

