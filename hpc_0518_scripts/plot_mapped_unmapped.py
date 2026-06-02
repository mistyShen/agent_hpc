#!/usr/bin/env python3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


BASE = Path("/shared/shen/2026/0518")
STATS = BASE / "analysis_dna" / "stats"
PLOTS = BASE / "analysis_dna" / "plots"
INPUT = STATS / "dna_mt_depth_summary.tsv"
OUT_TSV = STATS / "mapped_unmapped_summary.tsv"


def setup_matplotlib():
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


def main():
    setup_matplotlib()
    PLOTS.mkdir(parents=True, exist_ok=True)
    STATS.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(INPUT, sep="\t")
    summary = df[["sample_id", "total_reads", "mapped_reads"]].copy()
    summary["unmapped_reads"] = summary["total_reads"] - summary["mapped_reads"]
    summary["mapped_fraction"] = summary["mapped_reads"] / summary["total_reads"]
    summary["unmapped_fraction"] = summary["unmapped_reads"] / summary["total_reads"]
    summary.to_csv(OUT_TSV, sep="\t", index=False)

    samples = summary["sample_id"].tolist()
    x = np.arange(len(samples))
    mapped_pct = summary["mapped_fraction"].to_numpy() * 100.0
    unmapped_pct = summary["unmapped_fraction"].to_numpy() * 100.0

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(x, mapped_pct, color="#4C78A8", label="Mapped")
    ax.bar(x, unmapped_pct, bottom=mapped_pct, color="#E45756", label="Unmapped")
    ax.set_xticks(x)
    ax.set_xticklabels(samples)
    ax.set_ylim(0, 105)
    ax.set_ylabel("Reads (%)")
    ax.set_title("Mapped vs Unmapped Reads")
    ax.legend(frameon=False, loc="upper right")
    for i, pct in enumerate(unmapped_pct):
        ax.text(i, min(mapped_pct[i] + pct + 1.0, 103), f"{pct:.2f}% unmapped", ha="center", va="bottom", fontsize=9)
    save(fig, "mapped_vs_unmapped_stacked_bar.png")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    bars = ax.bar(x, unmapped_pct, color="#E45756")
    ax.set_xticks(x)
    ax.set_xticklabels(samples)
    ax.set_ylabel("Unmapped reads (%)")
    ax.set_title("Unmapped Read Fraction")
    y_max = max(3.5, float(unmapped_pct.max()) * 1.25)
    ax.set_ylim(0, y_max)
    for bar, pct in zip(bars, unmapped_pct):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + y_max * 0.025,
            f"{pct:.2f}%",
            ha="center",
            va="bottom",
            fontsize=10,
        )
    save(fig, "unmapped_fraction_barplot.png")

    print(f"Wrote {OUT_TSV}")
    print(f"Wrote {PLOTS / 'mapped_vs_unmapped_stacked_bar.png'}")
    print(f"Wrote {PLOTS / 'unmapped_fraction_barplot.png'}")


if __name__ == "__main__":
    main()
