#!/usr/bin/env python3
from __future__ import annotations

import csv
import math
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


BASE = Path("/shared/shen/2026/0518")
REF = Path("/shared/shen/2026/0311/analysis_rna/ref/hg19.fa")
OUT_ROOT = BASE / "analysis_mtDNA"
VARIANTS_DIR = OUT_ROOT / "variants"
PLOTS_DIR = OUT_ROOT / "plots"
SCRIPTS_DIR = OUT_ROOT / "scripts"
LOGS_DIR = OUT_ROOT / "logs"
SAMPLES = ["A_121", "A_122", "A_161", "A_163"]
MT_LEN = 16569

STANDARD = {"min_depth": 30, "min_alt_count": 5, "min_vaf": 0.01}
STRICT = {"min_depth": 100, "min_alt_count": 10, "min_vaf": 0.02}
HOMOPLASMY_VAF = 0.95


def run_text(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, text=True)


def parse_pileup_bases(ref_base: str, bases: str) -> tuple[Counter, Counter]:
    """Return nucleotide counts and indel counts from one mpileup read-bases field."""
    ref_base = ref_base.upper()
    base_counts: Counter[str] = Counter()
    indel_counts: Counter[str] = Counter()
    i = 0
    while i < len(bases):
        char = bases[i]
        if char == "^":
            i += 2
            continue
        if char == "$":
            i += 1
            continue
        if char in ".,":  # reference base on forward/reverse strand
            base_counts[ref_base] += 1
            i += 1
            continue
        if char in "ACGTNacgtn":
            base_counts[char.upper()] += 1
            i += 1
            continue
        if char in "+-":
            sign = char
            i += 1
            match = re.match(r"\d+", bases[i:])
            if not match:
                continue
            length = int(match.group(0))
            i += len(match.group(0))
            seq = bases[i : i + length].upper()
            i += length
            if seq and set(seq) <= set("ACGTN"):
                indel_counts[f"{sign}{seq}"] += 1
            continue
        # Deletion placeholder or reference skip; do not count as an alt allele.
        if char in "*#<>":
            i += 1
            continue
        i += 1
    return base_counts, indel_counts


def classify_variant(vaf: float) -> str:
    return "homoplasmic" if vaf >= HOMOPLASMY_VAF else "heteroplasmic"


def passes(row: dict, filt: dict) -> bool:
    return (
        row["depth"] >= filt["min_depth"]
        and row["alt_count"] >= filt["min_alt_count"]
        and row["vaf"] >= filt["min_vaf"]
    )


def call_sample(sample: str) -> tuple[list[dict], dict]:
    bam = BASE / "analysis_dna" / "bam" / sample / f"{sample}.sorted.bam"
    if not bam.exists():
        raise FileNotFoundError(bam)
    subprocess.check_call(["samtools", "quickcheck", "-v", str(bam)])

    cmd = [
        "samtools",
        "mpileup",
        "-aa",
        "-B",
        "-q",
        "20",
        "-Q",
        "20",
        "-f",
        str(REF),
        "-r",
        "chrM",
        str(bam),
    ]
    rows: list[dict] = []
    depths: list[int] = []
    callable_ge30 = 0
    callable_ge100 = 0
    log_path = LOGS_DIR / f"{sample}.mpileup.cmd.txt"
    log_path.write_text(" ".join(cmd) + "\n")

    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    for line in proc.stdout:
        fields = line.rstrip("\n").split("\t")
        if len(fields) < 5:
            continue
        chrom, pos_text, ref_base, depth_text, bases = fields[:5]
        pos = int(pos_text)
        ref_base = ref_base.upper()
        depth = int(depth_text)
        depths.append(depth)
        if depth >= 30:
            callable_ge30 += 1
        if depth >= 100:
            callable_ge100 += 1

        base_counts, indel_counts = parse_pileup_bases(ref_base, bases)
        for alt in ["A", "C", "G", "T"]:
            if alt == ref_base:
                continue
            alt_count = base_counts[alt]
            if alt_count <= 0:
                continue
            vaf = alt_count / depth if depth else 0.0
            rows.append(
                {
                    "sample": sample,
                    "chrom": chrom,
                    "pos": pos,
                    "ref": ref_base,
                    "alt": alt,
                    "variant_type": "SNV",
                    "depth": depth,
                    "alt_count": alt_count,
                    "vaf": vaf,
                    "zygosity_call": classify_variant(vaf),
                    "passes_standard": passes({"depth": depth, "alt_count": alt_count, "vaf": vaf}, STANDARD),
                    "passes_strict": passes({"depth": depth, "alt_count": alt_count, "vaf": vaf}, STRICT),
                }
            )
        for alt, alt_count in indel_counts.items():
            if alt_count <= 0:
                continue
            vaf = alt_count / depth if depth else 0.0
            rows.append(
                {
                    "sample": sample,
                    "chrom": chrom,
                    "pos": pos,
                    "ref": ref_base,
                    "alt": alt,
                    "variant_type": "insertion" if alt.startswith("+") else "deletion",
                    "depth": depth,
                    "alt_count": alt_count,
                    "vaf": vaf,
                    "zygosity_call": classify_variant(vaf),
                    "passes_standard": passes({"depth": depth, "alt_count": alt_count, "vaf": vaf}, STANDARD),
                    "passes_strict": passes({"depth": depth, "alt_count": alt_count, "vaf": vaf}, STRICT),
                }
            )
    stderr = proc.stderr.read() if proc.stderr else ""
    rc = proc.wait()
    (LOGS_DIR / f"{sample}.mpileup.stderr.log").write_text(stderr)
    if rc != 0:
        raise RuntimeError(f"mpileup failed for {sample}; see {LOGS_DIR / f'{sample}.mpileup.stderr.log'}")

    standard_rows = [row for row in rows if row["passes_standard"]]
    strict_rows = [row for row in rows if row["passes_strict"]]
    top_rows = sorted(standard_rows, key=lambda r: (-r["vaf"], -r["alt_count"], r["pos"]))[:10]
    top_vaf = ";".join(
        f"{r['pos']}{r['ref']}>{r['alt']}:{r['vaf']:.3f}({r['alt_count']}/{r['depth']})"
        for r in top_rows
    )
    summary = {
        "sample": sample,
        "chrM_positions": len(depths),
        "mean_depth": statistics.mean(depths) if depths else 0,
        "median_depth": statistics.median(depths) if depths else 0,
        "min_depth": min(depths) if depths else 0,
        "max_depth": max(depths) if depths else 0,
        "positions_depth_ge30": callable_ge30,
        "fraction_positions_depth_ge30": callable_ge30 / MT_LEN,
        "positions_depth_ge100": callable_ge100,
        "fraction_positions_depth_ge100": callable_ge100 / MT_LEN,
        "raw_mtDNA_variants": len(rows),
        "standard_filtered_variants": len(standard_rows),
        "standard_heteroplasmic_variants": sum(r["zygosity_call"] == "heteroplasmic" for r in standard_rows),
        "standard_homoplasmic_variants": sum(r["zygosity_call"] == "homoplasmic" for r in standard_rows),
        "strict_filtered_variants": len(strict_rows),
        "strict_heteroplasmic_variants": sum(r["zygosity_call"] == "heteroplasmic" for r in strict_rows),
        "strict_homoplasmic_variants": sum(r["zygosity_call"] == "homoplasmic" for r in strict_rows),
        "top_vaf_variants_standard": top_vaf,
    }
    return rows, summary


def write_table(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        for row in rows:
            out = {}
            for key, value in row.items():
                if isinstance(value, float):
                    out[key] = f"{value:.8g}"
                else:
                    out[key] = value
            writer.writerow(out)


def setup_matplotlib() -> None:
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "figure.dpi": 120,
            "savefig.dpi": 300,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.22,
            "grid.linewidth": 0.7,
        }
    )


def plot_outputs(summary_df: pd.DataFrame, filtered_df: pd.DataFrame) -> None:
    setup_matplotlib()
    samples = summary_df["sample"].tolist()
    x = range(len(samples))

    fig, ax = plt.subplots(figsize=(8, 5))
    width = 0.35
    ax.bar([i - width / 2 for i in x], summary_df["standard_filtered_variants"], width=width, label="Filtered", color="#4C78A8")
    ax.bar([i + width / 2 for i in x], summary_df["strict_filtered_variants"], width=width, label="Strict", color="#E45756")
    ax.set_xticks(list(x))
    ax.set_xticklabels(samples)
    ax.set_ylabel("mtDNA variant count")
    ax.set_title("mtDNA Variant Counts")
    ax.legend(frameon=False)
    ymax = max(1, int(max(summary_df["standard_filtered_variants"].max(), summary_df["strict_filtered_variants"].max()) * 1.2))
    ax.set_ylim(0, ymax + 1)
    for i, value in enumerate(summary_df["standard_filtered_variants"]):
        ax.text(i - width / 2, value + 0.2, str(int(value)), ha="center", va="bottom", fontsize=9)
    for i, value in enumerate(summary_df["strict_filtered_variants"]):
        ax.text(i + width / 2, value + 0.2, str(int(value)), ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "mtDNA_variant_counts_barplot.png", dpi=300, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 5))
    if not filtered_df.empty:
        for sample in samples:
            values = filtered_df.loc[filtered_df["sample"] == sample, "vaf"].astype(float).values
            if len(values):
                ax.hist(values, bins=[0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 0.95, 1.01], alpha=0.45, label=sample)
        ax.set_xscale("symlog", linthresh=0.02)
    ax.set_xlabel("Variant allele fraction (VAF)")
    ax.set_ylabel("Variant count")
    ax.set_title("Filtered mtDNA VAF Distribution")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(PLOTS_DIR / "mtDNA_vaf_distribution.png", dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    for path in [VARIANTS_DIR, PLOTS_DIR, SCRIPTS_DIR, LOGS_DIR]:
        path.mkdir(parents=True, exist_ok=True)

    all_rows: list[dict] = []
    summaries: list[dict] = []
    for sample in SAMPLES:
        print(f"[{sample}] calling chrM variants", flush=True)
        rows, summary = call_sample(sample)
        all_rows.extend(rows)
        summaries.append(summary)

    raw_path = VARIANTS_DIR / "mtDNA_variants_raw.tsv"
    filtered_path = VARIANTS_DIR / "mtDNA_variants_filtered.tsv"
    strict_path = VARIANTS_DIR / "mtDNA_variants_strict.tsv"
    summary_path = VARIANTS_DIR / "mtDNA_variant_summary.tsv"

    standard_rows = [row for row in all_rows if row["passes_standard"]]
    strict_rows = [row for row in all_rows if row["passes_strict"]]
    write_table(raw_path, all_rows)
    write_table(filtered_path, standard_rows)
    write_table(strict_path, strict_rows)
    write_table(summary_path, summaries)

    summary_df = pd.read_csv(summary_path, sep="\t")
    filtered_df = pd.read_csv(filtered_path, sep="\t") if filtered_path.stat().st_size else pd.DataFrame()
    plot_outputs(summary_df, filtered_df)

    print(f"Wrote {summary_path}")
    print(f"Wrote {filtered_path}")
    print(f"Wrote {strict_path}")
    print(f"Wrote {PLOTS_DIR / 'mtDNA_variant_counts_barplot.png'}")
    print(f"Wrote {PLOTS_DIR / 'mtDNA_vaf_distribution.png'}")


if __name__ == "__main__":
    main()
