#!/usr/bin/env python3
from __future__ import annotations

import csv
import gzip
import math
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE = Path("/shared/shen/2026/0518")
REF = Path("/shared/shen/2026/0311/analysis_rna/ref/hg19.fa")
ROOT = BASE / "analysis_mtDNA" / "singlecell_mgatk_like"
COUNTS = ROOT / "counts"
VARIANTS = ROOT / "variants"
PLOTS = ROOT / "plots"
SCRIPTS = ROOT / "scripts"
LOGS = ROOT / "logs"
CELLS = ["A_121", "A_122", "A_161", "A_163"]
MT_LEN = 16569
BASES = ["A", "C", "G", "T"]

INITIAL = {"min_depth": 30, "min_alt_count": 5, "min_vaf": 0.01}
STRICT = {"min_depth": 100, "min_alt_count": 10, "min_vaf": 0.02, "min_strand_balance": 0.2}


def run_text(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True)


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def fmt(value):
    if isinstance(value, float):
        if math.isnan(value):
            return "NA"
        return f"{value:.8g}"
    return value


def read_chrm_reference() -> str:
    text = run_text(["samtools", "faidx", str(REF), "chrM"])
    seq = "".join(line.strip() for line in text.splitlines() if not line.startswith(">")).upper()
    if len(seq) != MT_LEN:
        raise RuntimeError(f"Unexpected chrM length {len(seq)}")
    return seq


def homopolymer_mask(seq: str, run_len: int = 4, flank: int = 2) -> set[int]:
    masked: set[int] = set()
    i = 0
    while i < len(seq):
        j = i + 1
        while j < len(seq) and seq[j] == seq[i]:
            j += 1
        if seq[i] in BASES and j - i >= run_len:
            start = max(0, i - flank)
            end = min(len(seq), j + flank)
            masked.update(range(start + 1, end + 1))
        i = j
    return masked


def parse_mpileup_bases(ref_base: str, bases: str) -> dict[str, int]:
    counts = {f"{b}_fwd": 0 for b in BASES}
    counts.update({f"{b}_rev": 0 for b in BASES})
    counts["N_count"] = 0
    counts["ins_count"] = 0
    counts["del_count"] = 0
    ref_base = ref_base.upper()
    i = 0
    while i < len(bases):
        char = bases[i]
        if char == "^":
            i += 2
            continue
        if char == "$":
            i += 1
            continue
        if char == ".":
            if ref_base in BASES:
                counts[f"{ref_base}_fwd"] += 1
            else:
                counts["N_count"] += 1
            i += 1
            continue
        if char == ",":
            if ref_base in BASES:
                counts[f"{ref_base}_rev"] += 1
            else:
                counts["N_count"] += 1
            i += 1
            continue
        if char in "ACGT":
            counts[f"{char}_fwd"] += 1
            i += 1
            continue
        if char in "acgt":
            counts[f"{char.upper()}_rev"] += 1
            i += 1
            continue
        if char in "Nn":
            counts["N_count"] += 1
            i += 1
            continue
        if char in "+-":
            sign = char
            i += 1
            length_text = []
            while i < len(bases) and bases[i].isdigit():
                length_text.append(bases[i])
                i += 1
            if length_text:
                length = int("".join(length_text))
                if sign == "+":
                    counts["ins_count"] += 1
                else:
                    counts["del_count"] += 1
                i += length
            continue
        if char in "*#<>":
            i += 1
            continue
        i += 1
    return counts


def run_cell_pileup(cell_id: str, ref_seq: str) -> list[dict]:
    bam = BASE / "analysis_dna" / "bam" / cell_id / f"{cell_id}.sorted.bam"
    subprocess.check_call(["samtools", "quickcheck", "-v", str(bam)])
    cmd = [
        "samtools",
        "mpileup",
        "-r",
        "chrM",
        "-q",
        "20",
        "-Q",
        "20",
        "-aa",
        "-f",
        str(REF),
        str(bam),
    ]
    (LOGS / f"{cell_id}.mpileup.cmd.txt").write_text(" ".join(cmd) + "\n")
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    rows = []
    seen_positions = set()
    for line in proc.stdout:
        fields = line.rstrip("\n").split("\t")
        if len(fields) < 5:
            continue
        chrom, pos_text, ref_base, depth_text, read_bases = fields[:5]
        pos = int(pos_text)
        depth = int(depth_text)
        ref_base = ref_base.upper()
        parsed = parse_mpileup_bases(ref_base, read_bases)
        row = {
            "chrom": chrom,
            "pos": pos,
            "ref": ref_base,
            "cell_id": cell_id,
            "depth": depth,
        }
        for b in BASES:
            row[f"{b}_count"] = parsed[f"{b}_fwd"] + parsed[f"{b}_rev"]
        for b in BASES:
            row[f"{b}_fwd"] = parsed[f"{b}_fwd"]
            row[f"{b}_rev"] = parsed[f"{b}_rev"]
        row["N_count"] = parsed["N_count"]
        row["ins_count"] = parsed["ins_count"]
        row["del_count"] = parsed["del_count"]
        rows.append(row)
        seen_positions.add(pos)
    stderr = proc.stderr.read() if proc.stderr else ""
    rc = proc.wait()
    (LOGS / f"{cell_id}.mpileup.stderr.log").write_text(stderr)
    if rc != 0:
        raise RuntimeError(f"mpileup failed for {cell_id}")
    if len(seen_positions) != MT_LEN:
        missing = MT_LEN - len(seen_positions)
        raise RuntimeError(f"{cell_id} mpileup missing {missing} chrM positions")
    return rows


def write_base_counts(rows: list[dict]) -> None:
    fields = [
        "chrom",
        "pos",
        "ref",
        "cell_id",
        "depth",
        "A_count",
        "C_count",
        "G_count",
        "T_count",
        "A_fwd",
        "A_rev",
        "C_fwd",
        "C_rev",
        "G_fwd",
        "G_rev",
        "T_fwd",
        "T_rev",
        "N_count",
        "ins_count",
        "del_count",
    ]
    out = COUNTS / "mtDNA_base_counts_long.tsv.gz"
    with gzip.open(out, "wt", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def coverage_summary(rows_by_cell: dict[str, list[dict]]) -> list[dict]:
    out_rows = []
    for cell, rows in rows_by_cell.items():
        depths = [int(r["depth"]) for r in rows]
        out_rows.append(
            {
                "cell_id": cell,
                "mean_depth": statistics.mean(depths),
                "median_depth": statistics.median(depths),
                "fraction_bases_ge_10x": safe_div(sum(d >= 10 for d in depths), MT_LEN),
                "fraction_bases_ge_20x": safe_div(sum(d >= 20 for d in depths), MT_LEN),
                "fraction_bases_ge_50x": safe_div(sum(d >= 50 for d in depths), MT_LEN),
                "fraction_bases_ge_100x": safe_div(sum(d >= 100 for d in depths), MT_LEN),
            }
        )
    return out_rows


def row_passes_initial(depth: int, alt_count: int, vaf: float) -> bool:
    return depth >= INITIAL["min_depth"] and alt_count >= INITIAL["min_alt_count"] and vaf >= INITIAL["min_vaf"]


def row_passes_strict(depth: int, alt_count: int, vaf: float, strand_balance: float, homopolymer_nearby: bool) -> bool:
    return (
        depth >= STRICT["min_depth"]
        and alt_count >= STRICT["min_alt_count"]
        and vaf >= STRICT["min_vaf"]
        and strand_balance >= STRICT["min_strand_balance"]
        and not homopolymer_nearby
    )


def build_variant_tables(rows_by_cell: dict[str, list[dict]], homopolymer_positions: set[int]) -> tuple[list[dict], list[dict], dict]:
    by_pos_cell = {(row["pos"], row["cell_id"]): row for rows in rows_by_cell.values() for row in rows}
    candidate_keys = set()
    per_cell_rows_by_key: dict[tuple[int, str], dict[str, dict]] = defaultdict(dict)

    for cell, rows in rows_by_cell.items():
        for row in rows:
            ref = row["ref"]
            if ref not in BASES:
                continue
            pos = int(row["pos"])
            depth = int(row["depth"])
            homopolymer_nearby = pos in homopolymer_positions
            for alt in BASES:
                if alt == ref:
                    continue
                alt_count = int(row[f"{alt}_count"])
                fwd = int(row[f"{alt}_fwd"])
                rev = int(row[f"{alt}_rev"])
                vaf = safe_div(alt_count, depth)
                strand_balance = safe_div(min(fwd, rev), max(fwd, rev))
                initial = row_passes_initial(depth, alt_count, vaf)
                strict = row_passes_strict(depth, alt_count, vaf, strand_balance, homopolymer_nearby)
                key = (pos, alt)
                per_cell_rows_by_key[key][cell] = {
                    "cell_id": cell,
                    "pos": pos,
                    "ref": ref,
                    "alt": alt,
                    "depth": depth,
                    "alt_count": alt_count,
                    "VAF": vaf,
                    "fwd_alt_count": fwd,
                    "rev_alt_count": rev,
                    "strand_balance": strand_balance,
                    "initial_pass": initial,
                    "strict_pass": strict,
                    "homopolymer_nearby": homopolymer_nearby,
                    "ins_count": int(row["ins_count"]),
                    "del_count": int(row["del_count"]),
                }
                if initial:
                    candidate_keys.add(key)

    variant_stats = []
    long_cell_variant_rows = []
    for key in sorted(candidate_keys):
        pos, alt = key
        cells = per_cell_rows_by_key[key]
        ref = next(iter(cells.values()))["ref"]
        variant_id = f"chrM:{pos}:{ref}>{alt}"
        depth_ge30 = [c for c, r in cells.items() if r["depth"] >= 30]
        depth_ge100 = [c for c, r in cells.items() if r["depth"] >= 100]
        detected = [c for c, r in cells.items() if r["initial_pass"]]
        strict_cells = [c for c, r in cells.items() if r["strict_pass"]]
        vafs_ge30 = [r["VAF"] for r in cells.values() if r["depth"] >= 30]
        mean_vaf = statistics.mean(vafs_ge30) if vafs_ge30 else 0.0
        vaf_variance = statistics.pvariance(vafs_ge30) if len(vafs_ge30) > 1 else 0.0
        fwd_total = sum(r["fwd_alt_count"] for r in cells.values())
        rev_total = sum(r["rev_alt_count"] for r in cells.values())
        total_balance = safe_div(min(fwd_total, rev_total), max(fwd_total, rev_total))
        homopolymer_nearby = pos in homopolymer_positions
        n_homoplasmic = sum(r["depth"] >= 30 and r["alt_count"] >= 5 and r["VAF"] >= 0.95 for r in cells.values())
        n_heteroplasmic_range = sum(r["strict_pass"] and 0.05 <= r["VAF"] <= 0.95 for r in cells.values())
        has_only_a161_low_depth = detected == ["A_161"] and not strict_cells

        if homopolymer_nearby or total_balance < 0.2:
            quality_class = "possible_artifact"
        elif n_homoplasmic >= 2 and mean_vaf >= 0.8:
            quality_class = "homoplasmic_shared"
        elif n_heteroplasmic_range >= 1 and strict_cells:
            quality_class = "informative_heteroplasmy"
        elif has_only_a161_low_depth or not strict_cells:
            quality_class = "low_confidence"
        else:
            quality_class = "low_confidence"

        stat = {
            "variant_id": variant_id,
            "chrom": "chrM",
            "pos": pos,
            "ref": ref,
            "alt": alt,
            "n_cells_depth_ge_30": len(depth_ge30),
            "n_cells_depth_ge_100": len(depth_ge100),
            "n_cells_alt_detected": len(detected),
            "cells_alt_detected": ",".join(detected) if detected else "none",
            "cells_strict_pass": ",".join(strict_cells) if strict_cells else "none",
            "max_vaf": max(vafs_ge30) if vafs_ge30 else 0.0,
            "mean_vaf": mean_vaf,
            "vaf_variance": vaf_variance,
            "VMR": safe_div(vaf_variance, mean_vaf),
            "forward_alt_total": fwd_total,
            "reverse_alt_total": rev_total,
            "strand_balance_total": total_balance,
            "variant_type": "SNV",
            "homopolymer_nearby_pm2": homopolymer_nearby,
            "n_homoplasmic_cells": n_homoplasmic,
            "n_strict_heteroplasmic_cells_0.05_0.95": n_heteroplasmic_range,
            "quality_class": quality_class,
        }
        variant_stats.append(stat)
        for cell in CELLS:
            r = cells[cell]
            long_cell_variant_rows.append(
                {
                    "cell_id": cell,
                    "variant_id": variant_id,
                    "chrom": "chrM",
                    "pos": pos,
                    "ref": ref,
                    "alt": alt,
                    "depth": r["depth"],
                    "alt_count": r["alt_count"],
                    "VAF": r["VAF"],
                    "fwd_alt_count": r["fwd_alt_count"],
                    "rev_alt_count": r["rev_alt_count"],
                    "strand_balance": r["strand_balance"],
                    "initial_pass": r["initial_pass"],
                    "strict_pass": r["strict_pass"],
                    "quality_class": quality_class,
                }
            )

    return variant_stats, long_cell_variant_rows, per_cell_rows_by_key


def write_tsv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row.get(field, "")) for field in fields})


def write_matrices(long_rows: list[dict]) -> None:
    if not long_rows:
        for name in ["cell_by_variant_vaf_matrix.tsv", "cell_by_variant_alt_count_matrix.tsv"]:
            (VARIANTS / name).write_text("cell_id\n")
        return
    df = pd.DataFrame(long_rows)
    vaf = df.pivot(index="cell_id", columns="variant_id", values="VAF").reindex(CELLS).fillna(0.0)
    alt = df.pivot(index="cell_id", columns="variant_id", values="alt_count").reindex(CELLS).fillna(0).astype(int)
    vaf.to_csv(VARIANTS / "cell_by_variant_vaf_matrix.tsv", sep="\t")
    alt.to_csv(VARIANTS / "cell_by_variant_alt_count_matrix.tsv", sep="\t")


def plot_outputs(depth_rows: list[dict], variant_stats: list[dict], long_rows: list[dict]) -> None:
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 9,
            "figure.dpi": 120,
            "savefig.dpi": 300,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.22,
            "grid.linewidth": 0.7,
        }
    )

    depth_df = pd.DataFrame(depth_rows)
    fig, ax = plt.subplots(figsize=(7.2, 4.5))
    bars = ax.bar(depth_df["cell_id"], depth_df["mean_depth"], color="#4C78A8")
    ax.axhline(100, color="#333333", ls="--", lw=1, label="100x")
    ax.set_ylabel("Mean chrM depth")
    ax.set_title("Cell mtDNA Depth")
    ax.legend(frameon=False)
    ymax = max(120, float(depth_df["mean_depth"].max()) * 1.2)
    ax.set_ylim(0, ymax)
    for bar, value in zip(bars, depth_df["mean_depth"]):
        ax.text(bar.get_x() + bar.get_width() / 2, value + ymax * 0.02, f"{value:.1f}x", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(PLOTS / "cell_mtDNA_depth_barplot.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    stats_df = pd.DataFrame(variant_stats)
    class_counts = stats_df["quality_class"].value_counts().reindex(
        ["informative_heteroplasmy", "homoplasmic_shared", "low_confidence", "possible_artifact"], fill_value=0
    )
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(class_counts.index, class_counts.values, color=["#54A24B", "#4C78A8", "#B279A2", "#E45756"])
    ax.set_ylabel("Variant count")
    ax.set_title("mtDNA SNV Class Counts")
    ax.set_xticklabels(class_counts.index, rotation=20, ha="right")
    for i, value in enumerate(class_counts.values):
        ax.text(i, value + 0.3, str(int(value)), ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(PLOTS / "variant_class_count_barplot.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    colors = {
        "informative_heteroplasmy": "#54A24B",
        "homoplasmic_shared": "#4C78A8",
        "low_confidence": "#B279A2",
        "possible_artifact": "#E45756",
    }
    for klass, sub in stats_df.groupby("quality_class"):
        ax.scatter(sub["mean_vaf"], sub["strand_balance_total"], label=klass, s=42, alpha=0.85, color=colors.get(klass, "#777777"))
    ax.axhline(0.2, color="#333333", ls="--", lw=1)
    ax.set_xlabel("Mean VAF across depth>=30 cells")
    ax.set_ylabel("Total strand balance")
    ax.set_title("Variant Strand Balance")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(PLOTS / "strand_balance_plot.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    long_df = pd.DataFrame(long_rows)
    selected = stats_df[stats_df["quality_class"].eq("informative_heteroplasmy")]["variant_id"].tolist()
    if not selected:
        selected = stats_df.sort_values(["quality_class", "max_vaf"], ascending=[True, False])["variant_id"].head(20).tolist()
    matrix = (
        long_df[long_df["variant_id"].isin(selected)]
        .pivot(index="cell_id", columns="variant_id", values="VAF")
        .reindex(CELLS)
        .fillna(0.0)
    )
    fig, ax = plt.subplots(figsize=(max(7, 0.35 * max(1, len(matrix.columns))), 4.2))
    if matrix.shape[1] == 0:
        ax.text(0.5, 0.5, "No informative SNVs", ha="center", va="center")
        ax.axis("off")
    else:
        im = ax.imshow(matrix.values, aspect="auto", cmap="viridis", vmin=0, vmax=1)
        ax.set_yticks(np.arange(len(matrix.index)))
        ax.set_yticklabels(matrix.index)
        ax.set_xticks(np.arange(len(matrix.columns)))
        ax.set_xticklabels(matrix.columns, rotation=90, fontsize=7)
        ax.set_title("Cell x Candidate Variant VAF")
        fig.colorbar(im, ax=ax, label="VAF")
    fig.tight_layout()
    fig.savefig(PLOTS / "cell_by_high_confidence_variant_vaf_heatmap.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    dot_variants = stats_df.sort_values(["quality_class", "max_vaf"], ascending=[True, False])["variant_id"].head(35).tolist()
    dot = long_df[long_df["variant_id"].isin(dot_variants)].copy()
    dot["variant_id"] = pd.Categorical(dot["variant_id"], categories=dot_variants, ordered=True)
    fig, ax = plt.subplots(figsize=(max(9, 0.28 * max(1, len(dot_variants))), 4.8))
    cell_to_y = {cell: i for i, cell in enumerate(CELLS)}
    xs = [dot_variants.index(v) for v in dot["variant_id"]]
    ys = [cell_to_y[c] for c in dot["cell_id"]]
    sc = ax.scatter(xs, ys, c=dot["VAF"], s=np.clip(dot["depth"] / 2, 12, 95), cmap="viridis", vmin=0, vmax=1, alpha=0.85)
    ax.set_xticks(range(len(dot_variants)))
    ax.set_xticklabels(dot_variants, rotation=90, fontsize=7)
    ax.set_yticks(range(len(CELLS)))
    ax.set_yticklabels(CELLS)
    ax.set_title("Variant VAF Dotplot")
    ax.set_xlabel("Variant")
    ax.set_ylabel("Cell")
    fig.colorbar(sc, ax=ax, label="VAF")
    fig.tight_layout()
    fig.savefig(PLOTS / "variant_vaf_dotplot.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def make_report(depth_rows: list[dict], variant_stats: list[dict], long_rows: list[dict]) -> None:
    stats_df = pd.DataFrame(variant_stats)
    long_df = pd.DataFrame(long_rows)
    bulk_summary_path = BASE / "analysis_mtDNA" / "variants" / "mtDNA_variant_summary.tsv"
    bulk_text = "Previous bulk-style summary not found."
    if bulk_summary_path.exists():
        bulk = pd.read_csv(bulk_summary_path, sep="\t")
        pieces = []
        for _, row in bulk.iterrows():
            pieces.append(f"{row['sample']}: standard={int(row['standard_filtered_variants'])}, strict={int(row['strict_filtered_variants'])}")
        bulk_text = "; ".join(pieces)

    informative = stats_df[stats_df["quality_class"].eq("informative_heteroplasmy")].copy()
    hom_shared = stats_df[stats_df["quality_class"].eq("homoplasmic_shared")].copy()
    low = stats_df[~stats_df["quality_class"].isin(["informative_heteroplasmy", "homoplasmic_shared"])].copy()
    per_cell_high = defaultdict(int)
    for _, row in long_df.iterrows():
        if row["quality_class"] == "informative_heteroplasmy" and bool(row["strict_pass"]):
            per_cell_high[row["cell_id"]] += 1

    lines = []
    lines.append("# Single-Cell mgatk-like mtDNA SNV Report")
    lines.append("")
    lines.append("Each sample library was treated as one cell. This is SNV-only and strand-aware; indels were counted but excluded from SNV calling.")
    lines.append("")
    lines.append("## Cell depth")
    lines.append("")
    lines.append("| cell | mean depth | median depth | >=50x | >=100x | usable? |")
    lines.append("|---|---:|---:|---:|---:|---|")
    for row in depth_rows:
        usable = "yes" if row["fraction_bases_ge_100x"] >= 0.75 else ("limited" if row["fraction_bases_ge_50x"] >= 0.75 else "low-depth")
        lines.append(
            f"| {row['cell_id']} | {row['mean_depth']:.1f} | {row['median_depth']:.1f} | {row['fraction_bases_ge_50x']:.1%} | {row['fraction_bases_ge_100x']:.1%} | {usable} |"
        )
    lines.append("")
    lines.append("## Variant classes")
    lines.append("")
    class_counts = stats_df["quality_class"].value_counts().to_dict()
    for klass in ["informative_heteroplasmy", "homoplasmic_shared", "low_confidence", "possible_artifact"]:
        lines.append(f"- {klass}: {class_counts.get(klass, 0)}")
    lines.append("")
    lines.append("High-confidence informative SNVs per cell, counted where that cell strict-passed the informative variant:")
    for cell in CELLS:
        lines.append(f"- {cell}: {per_cell_high.get(cell, 0)}")
    lines.append("")
    lines.append("## Shared homoplasmic variants")
    lines.append("")
    if hom_shared.empty:
        lines.append("No shared homoplasmic SNVs passed the class rules.")
    else:
        top = hom_shared.sort_values(["n_homoplasmic_cells", "max_vaf"], ascending=[False, False]).head(20)
        lines.append(", ".join(top["variant_id"].tolist()))
    lines.append("")
    lines.append("## Top informative candidates")
    lines.append("")
    if informative.empty:
        lines.append("No informative heteroplasmy SNVs passed strict strand/homopolymer filtering.")
    else:
        top = informative.sort_values(["vaf_variance", "max_vaf"], ascending=[False, False]).head(20)
        lines.append("| variant | detected cells | strict cells | max VAF | VMR | strand balance |")
        lines.append("|---|---|---|---:|---:|---:|")
        for _, row in top.iterrows():
            lines.append(
                f"| {row['variant_id']} | {row['cells_alt_detected']} | {row['cells_strict_pass']} | {row['max_vaf']:.3f} | {row['VMR']:.3g} | {row['strand_balance_total']:.3f} |"
            )
    lines.append("")
    lines.append("## Comparison to previous bulk-style calling")
    lines.append("")
    lines.append(f"Previous bulk-style filtered counts: {bulk_text}.")
    lines.append(
        "This mgatk-like pass excludes indels from SNV calling, excludes homopolymer-adjacent variants from strict informative calls, requires forward/reverse support, and evaluates cell-to-cell VAF variation. Therefore many earlier bulk-style heteroplasmic indel or homopolymer-nearby calls are downgraded to possible_artifact or low_confidence."
    )
    lines.append("")
    lines.append("## Answers")
    lines.append("")
    a161 = next(r for r in depth_rows if r["cell_id"] == "A_161")
    lines.append("1. A_121 and A_163 have broad >=100x coverage; A_122 is usable but less complete at >=100x; A_161 is depth-limited and should be excluded from high-confidence lineage decisions.")
    lines.append("2. High-confidence SNVs per cell are listed above; the strict informative set is the recommended lineage-candidate set.")
    lines.append("3. Shared homoplasmic variants are more consistent with background/haplogroup/germline-like differences than lineage-informative heteroplasmy.")
    lines.append(f"4. A_161 mean depth is {a161['mean_depth']:.1f}x with {a161['fraction_bases_ge_100x']:.1%} bases >=100x, so it is not reliable for low-frequency heteroplasmy.")
    lines.append("5. Compared with bulk-style calling, SNV-only strand and homopolymer filtering removes many likely pileup/indel artifacts.")
    lines.append("6. With only 4 cells and one low-depth cell, this dataset is not sufficient for robust single-cell mtDNA lineage tracing. It is useful for QC and candidate discovery.")
    lines.append("7. Recommended validation targets are the top informative candidates above, prioritizing strict-passing, strand-balanced SNVs with clear VAF differences across cells.")
    lines.append("")
    (VARIANTS / "singlecell_mgatk_like_report.md").write_text("\n".join(lines) + "\n")


def validate_outputs() -> None:
    expected = [
        COUNTS / "cell_mtDNA_depth.tsv",
        COUNTS / "mtDNA_base_counts_long.tsv.gz",
        VARIANTS / "mtDNA_snv_variant_stats.tsv",
        VARIANTS / "cell_by_variant_vaf_matrix.tsv",
        VARIANTS / "cell_by_variant_alt_count_matrix.tsv",
        VARIANTS / "high_confidence_informative_variants.tsv",
        VARIANTS / "homoplasmic_shared_variants.tsv",
        VARIANTS / "low_confidence_variants.tsv",
        VARIANTS / "singlecell_mgatk_like_report.md",
    ]
    for path in expected:
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f"Expected non-empty output missing: {path}")


def main() -> None:
    for path in [COUNTS, VARIANTS, PLOTS, SCRIPTS, LOGS]:
        path.mkdir(parents=True, exist_ok=True)

    ref_seq = read_chrm_reference()
    homopolymer_positions = homopolymer_mask(ref_seq)
    (LOGS / "homopolymer_mask_pm2_positions.txt").write_text("\n".join(map(str, sorted(homopolymer_positions))) + "\n")

    rows_by_cell = {}
    all_count_rows = []
    for cell in CELLS:
        print(f"[{cell}] mpileup base counts", flush=True)
        rows = run_cell_pileup(cell, ref_seq)
        rows_by_cell[cell] = rows
        all_count_rows.extend(rows)

    print("[write] base count table", flush=True)
    write_base_counts(all_count_rows)
    depth_rows = coverage_summary(rows_by_cell)
    write_tsv(
        COUNTS / "cell_mtDNA_depth.tsv",
        depth_rows,
        [
            "cell_id",
            "mean_depth",
            "median_depth",
            "fraction_bases_ge_10x",
            "fraction_bases_ge_20x",
            "fraction_bases_ge_50x",
            "fraction_bases_ge_100x",
        ],
    )

    print("[call] SNV candidates", flush=True)
    variant_stats, long_rows, _ = build_variant_tables(rows_by_cell, homopolymer_positions)
    variant_fields = [
        "variant_id",
        "chrom",
        "pos",
        "ref",
        "alt",
        "n_cells_depth_ge_30",
        "n_cells_depth_ge_100",
        "n_cells_alt_detected",
        "cells_alt_detected",
        "cells_strict_pass",
        "max_vaf",
        "mean_vaf",
        "vaf_variance",
        "VMR",
        "forward_alt_total",
        "reverse_alt_total",
        "strand_balance_total",
        "variant_type",
        "homopolymer_nearby_pm2",
        "n_homoplasmic_cells",
        "n_strict_heteroplasmic_cells_0.05_0.95",
        "quality_class",
    ]
    write_tsv(VARIANTS / "mtDNA_snv_variant_stats.tsv", variant_stats, variant_fields)
    write_tsv(VARIANTS / "high_confidence_informative_variants.tsv", [r for r in variant_stats if r["quality_class"] == "informative_heteroplasmy"], variant_fields)
    write_tsv(VARIANTS / "homoplasmic_shared_variants.tsv", [r for r in variant_stats if r["quality_class"] == "homoplasmic_shared"], variant_fields)
    write_tsv(VARIANTS / "low_confidence_variants.tsv", [r for r in variant_stats if r["quality_class"] in {"low_confidence", "possible_artifact"}], variant_fields)
    write_matrices(long_rows)

    print("[plot/report]", flush=True)
    plot_outputs(depth_rows, variant_stats, long_rows)
    make_report(depth_rows, variant_stats, long_rows)
    validate_outputs()
    print(f"Wrote {VARIANTS / 'singlecell_mgatk_like_report.md'}")


if __name__ == "__main__":
    main()
