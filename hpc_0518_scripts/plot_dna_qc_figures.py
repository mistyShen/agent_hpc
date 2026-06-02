#!/usr/bin/env python3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE = Path("/shared/shen/2026/0518")
STATS = BASE / "analysis_dna" / "stats"
PLOTS = BASE / "analysis_dna" / "plots"
PLOTS.mkdir(parents=True, exist_ok=True)
CHROMS = [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY", "chrM"]


def setup():
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


def save(fig, name):
    fig.tight_layout()
    fig.savefig(PLOTS / name, dpi=300, bbox_inches="tight")
    plt.close(fig)


def label_bars(ax, bars, fmt="{:.2f}", dy=3):
    ymax = ax.get_ylim()[1]
    for bar in bars:
        h = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            h + ymax * 0.015,
            fmt.format(h),
            ha="center",
            va="bottom",
            fontsize=9,
        )


def stacked_reads(summary):
    samples = summary["sample_id"].tolist()
    x = np.arange(len(samples))
    nuclear = summary["nuclear_reads"].to_numpy() / 1e6
    chrm = summary["chrM_reads"].to_numpy() / 1e6

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x, nuclear, color="#4C78A8", label="Nuclear reads")
    ax.bar(x, chrm, bottom=nuclear, color="#F58518", label="chrM reads")
    ax.set_xticks(x)
    ax.set_xticklabels(samples)
    ax.set_ylabel("Mapped reads (million)")
    ax.set_title("Mapped DNA Reads: Nuclear vs chrM")
    ax.legend(frameon=False)
    save(fig, "dna_nuclear_vs_chrM_reads_stacked_bar.png")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(x, summary["chrM_reads"], color="#F58518")
    ax.set_xticks(x)
    ax.set_xticklabels(samples)
    ax.set_ylabel("chrM mapped reads")
    ax.set_title("chrM Reads")
    label_bars(ax, bars, fmt="{:.0f}")
    save(fig, "chrM_reads_barplot.png")


def fraction_plot(summary):
    samples = summary["sample_id"].tolist()
    x = np.arange(len(samples))
    y = summary["chrM_fraction_mapped"] * 100
    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(x, y, color="#F58518")
    ax.set_xticks(x)
    ax.set_xticklabels(samples)
    ax.set_ylabel("chrM fraction of mapped reads (%)")
    ax.set_title("Mitochondrial Read Fraction")
    label_bars(ax, bars, fmt="{:.3f}")
    save(fig, "chrM_fraction_barplot.png")


def depth_plots(summary):
    samples = summary["sample_id"].tolist()
    x = np.arange(len(samples))

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(x, summary["mtDNA_depth"], color="#E45756")
    ax.axhline(100, color="#333333", lw=1, ls="--", label="100x")
    ax.set_xticks(x)
    ax.set_xticklabels(samples)
    ax.set_ylabel("mtDNA depth (x)")
    ax.set_title("Mean mtDNA Depth")
    ax.legend(frameon=False)
    label_bars(ax, bars, fmt="{:.1f}")
    save(fig, "mtDNA_depth_barplot.png")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(x, summary["mean_nuclear_depth"], color="#4C78A8")
    ax.set_xticks(x)
    ax.set_xticklabels(samples)
    ax.set_ylabel("Mean nuclear depth (x)")
    ax.set_title("Mean Nuclear Genome Depth")
    label_bars(ax, bars, fmt="{:.4f}")
    save(fig, "nuclear_depth_barplot.png")


def chrm_profile(samples):
    fig, ax = plt.subplots(figsize=(11, 4.8))
    for sample in samples:
        path = STATS / "mtDNA_coverage" / f"{sample}.chrM.depth.tsv"
        df = pd.read_csv(path, sep="\t", names=["chrom", "position", "depth"])
        ax.plot(df["position"], df["depth"], lw=1.2, label=sample)
    ax.set_xlabel("chrM position")
    ax.set_ylabel("Depth")
    ax.set_title("chrM Depth Profile")
    ax.legend(frameon=False, ncol=4, loc="upper right")
    save(fig, "chrM_depth_profile.png")


def uniformity_plot(uniform):
    samples = uniform["sample_id"].tolist()
    x = np.arange(len(samples))
    width = 0.24
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    metrics = [
        ("fraction_chrM_bases_depth_ge_10", ">=10x", "#72B7B2"),
        ("fraction_chrM_bases_depth_ge_30", ">=30x", "#54A24B"),
        ("fraction_chrM_bases_depth_ge_100", ">=100x", "#E45756"),
    ]
    for i, (col, label, color) in enumerate(metrics):
        ax.bar(x + (i - 1) * width, uniform[col] * 100, width=width, color=color, label=label)
    ax.set_xticks(x)
    ax.set_xticklabels(samples)
    ax.set_ylim(0, 105)
    ax.set_ylabel("chrM bases covered (%)")
    ax.set_title("mtDNA Coverage Uniformity")
    ax.legend(frameon=False, ncol=3)
    save(fig, "mtDNA_coverage_uniformity_barplot.png")


def chromosome_distribution(samples):
    rows = []
    for sample in samples:
        path = STATS / "chrom_distribution" / f"{sample}.idxstats.tsv"
        df = pd.read_csv(path, sep="\t", names=["chrom", "length", "mapped_reads", "unmapped_reads"])
        df = df[df["chrom"].isin(CHROMS)].copy()
        total = df["mapped_reads"].sum()
        df["fraction"] = np.where(total > 0, df["mapped_reads"] / total * 100, 0)
        df["sample_id"] = sample
        rows.append(df)
    data = pd.concat(rows, ignore_index=True)

    fig, ax = plt.subplots(figsize=(13, 5.2))
    x = np.arange(len(CHROMS))
    for sample in samples:
        y = (
            data[data["sample_id"] == sample]
            .set_index("chrom")
            .reindex(CHROMS)["fraction"]
            .fillna(0)
            .to_numpy()
        )
        ax.plot(x, y, marker="o", ms=3.5, lw=1.5, label=sample)
    ax.set_xticks(x)
    ax.set_xticklabels(CHROMS, rotation=45, ha="right")
    ax.set_ylabel("Mapped reads by chromosome (%)")
    ax.set_title("Chromosome Mapped Read Distribution")
    ax.legend(frameon=False, ncol=4, loc="upper right")
    save(fig, "chromosome_read_distribution.png")


def main():
    setup()
    summary = pd.read_csv(STATS / "dna_mt_depth_summary.tsv", sep="\t")
    uniform = pd.read_csv(STATS / "mtDNA_coverage_uniformity.tsv", sep="\t")
    samples = summary["sample_id"].tolist()

    stacked_reads(summary)
    fraction_plot(summary)
    depth_plots(summary)
    chrm_profile(samples)
    uniformity_plot(uniform)
    chromosome_distribution(samples)
    print(f"Wrote plots to {PLOTS}")


if __name__ == "__main__":
    main()
