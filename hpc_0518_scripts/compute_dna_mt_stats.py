#!/usr/bin/env python3
import csv
import math
import statistics
import subprocess
from pathlib import Path


BASE = Path("/shared/shen/2026/0518")
MANIFEST = BASE / "sample_manifest.tsv"
BAM_DIR = BASE / "analysis_dna" / "bam"
STATS_DIR = BASE / "analysis_dna" / "stats"
CHROM_DIR = STATS_DIR / "chrom_distribution"
COV_DIR = STATS_DIR / "mtDNA_coverage"
MTDNA_DENOMINATOR = 16569.0
NUCLEAR_DENOMINATOR = 2.9e9
CANONICAL = [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"]
AUTOSOMES = [f"chr{i}" for i in range(1, 23)]


def run_text(cmd):
    return subprocess.check_output(cmd, text=True)


def run_count(cmd):
    out = run_text(cmd).strip()
    return int(out) if out else 0


def safe_div(num, den):
    return num / den if den else 0.0


def fmt_float(x, digits=8):
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "NA"
    return f"{x:.{digits}g}"


def read_manifest():
    with MANIFEST.open() as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return list(reader)


def parse_idxstats(sample, bam):
    out_path = CHROM_DIR / f"{sample}.idxstats.tsv"
    text = run_text(["samtools", "idxstats", str(bam)])
    out_path.write_text(text)
    rows = []
    for line in text.splitlines():
        chrom, length, mapped, unmapped = line.split("\t")
        rows.append(
            {
                "chrom": chrom,
                "length": int(length),
                "mapped_reads": int(mapped),
                "unmapped_reads": int(unmapped),
            }
        )
    return rows


def write_top_chromosomes(sample, idx_rows, total_mapped):
    out_path = STATS_DIR / f"{sample}_top_chromosomes.tsv"
    ranked = [r for r in idx_rows if r["chrom"] != "*"]
    ranked.sort(key=lambda r: r["mapped_reads"], reverse=True)
    with out_path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "sample_id",
                "rank",
                "chrom",
                "length",
                "mapped_reads",
                "reads_per_mb",
                "fraction_of_total_mapped",
                "category",
            ]
        )
        for rank, row in enumerate(ranked[:25], start=1):
            chrom = row["chrom"]
            if chrom == "chrM":
                category = "chrM"
            elif chrom in CANONICAL:
                category = "canonical_nuclear"
            else:
                category = "noncanonical_nonchrM"
            reads_per_mb = safe_div(row["mapped_reads"], row["length"] / 1e6)
            writer.writerow(
                [
                    sample,
                    rank,
                    chrom,
                    row["length"],
                    row["mapped_reads"],
                    fmt_float(reads_per_mb),
                    fmt_float(safe_div(row["mapped_reads"], total_mapped)),
                    category,
                ]
            )


def bedcov_total(regions, bam):
    if not regions:
        return 0
    bed = STATS_DIR / "_tmp_regions.bed"
    with bed.open("w") as handle:
        for chrom, length in regions:
            handle.write(f"{chrom}\t0\t{length}\n")
    text = run_text(["samtools", "bedcov", str(bed), str(bam)])
    total = 0
    for line in text.splitlines():
        fields = line.split("\t")
        if fields:
            total += int(float(fields[-1]))
    return total


def chrM_depth(sample, bam):
    out_path = COV_DIR / f"{sample}.chrM.depth.tsv"
    text = run_text(["samtools", "depth", "-aa", "-r", "chrM", str(bam)])
    out_path.write_text(text)
    depths = []
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) >= 3:
            depths.append(int(fields[2]))
    if not depths:
        return {
            "chrM_bases": 0,
            "mean_depth": 0.0,
            "median_depth": 0.0,
            "min_depth": 0,
            "max_depth": 0,
            "coverage_cv": 0.0,
            "fraction_chrM_bases_depth_ge_10": 0.0,
            "fraction_chrM_bases_depth_ge_30": 0.0,
            "fraction_chrM_bases_depth_ge_100": 0.0,
            "positions": 0,
        }
    total = sum(depths)
    mean = total / len(depths)
    stdev = statistics.pstdev(depths) if len(depths) > 1 else 0.0
    return {
        "chrM_bases": total,
        "mean_depth": mean,
        "median_depth": statistics.median(depths),
        "min_depth": min(depths),
        "max_depth": max(depths),
        "coverage_cv": safe_div(stdev, mean),
        "fraction_chrM_bases_depth_ge_10": sum(d >= 10 for d in depths) / len(depths),
        "fraction_chrM_bases_depth_ge_30": sum(d >= 30 for d in depths) / len(depths),
        "fraction_chrM_bases_depth_ge_100": sum(d >= 100 for d in depths) / len(depths),
        "positions": len(depths),
    }


def cv(values):
    values = [v for v in values if v is not None]
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    if mean == 0:
        return 0.0
    return statistics.pstdev(values) / mean


def judge(chrM_fraction, nuclear_fraction, mt_depth, top_fraction, autosome_cv, covered_autosomes):
    if chrM_fraction < 0.01 and nuclear_fraction >= 0.95:
        composition = "nuclear DNA-major"
    elif chrM_fraction >= 0.05:
        composition = "mtDNA-enriched"
    else:
        composition = "nuclear DNA-major with low/modest chrM signal"

    if top_fraction >= 0.25 or autosome_cv >= 1.0:
        nuclear_judgment = "nuclear DNA with noticeable amplification bias"
    elif covered_autosomes >= 18:
        nuclear_judgment = "low-depth nuclear genome DNA"
    else:
        nuclear_judgment = "sparse nuclear DNA signal"

    if chrM_fraction >= 0.05:
        enrichment = "mtDNA-enriched relative to nuclear background"
    elif chrM_fraction >= 0.01:
        enrichment = "weak/modest mtDNA signal; nuclear DNA remains dominant"
    else:
        enrichment = "no meaningful mtDNA enrichment; chrM fraction is very low"

    if mt_depth < 100:
        failure = "mtDNA depth insufficient for reliable variant-level analysis"
    elif composition != "mtDNA-enriched":
        failure = "mtDNA depth detectable but composition remains nuclear-dominant"
    else:
        failure = "mtDNA coverage adequate for QC-level depth assessment; variant/lineage not run in this workflow"
    return composition, nuclear_judgment, enrichment, failure


def main():
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    CHROM_DIR.mkdir(parents=True, exist_ok=True)
    COV_DIR.mkdir(parents=True, exist_ok=True)

    samples = read_manifest()
    depth_rows = []
    mt_rows = []
    uniform_rows = []
    rca_rows = []

    for row in samples:
        sample = row["sample_id"]
        bam = BAM_DIR / sample / f"{sample}.sorted.bam"
        if not bam.exists():
            raise FileNotFoundError(f"Missing BAM for {sample}: {bam}")
        subprocess.check_call(["samtools", "quickcheck", "-v", str(bam)])

        total_reads = run_count(["samtools", "view", "-c", "-F", "2304", str(bam)])
        mapped_reads = run_count(["samtools", "view", "-c", "-F", "2308", str(bam)])
        chrM_reads = run_count(["samtools", "view", "-c", "-F", "2308", str(bam), "chrM"])
        nuclear_reads = mapped_reads - chrM_reads

        idx_rows = parse_idxstats(sample, bam)
        idx_by_chrom = {r["chrom"]: r for r in idx_rows}
        total_mapped_idx = sum(r["mapped_reads"] for r in idx_rows if r["chrom"] != "*")
        canonical_nuclear_reads = sum(idx_by_chrom.get(c, {}).get("mapped_reads", 0) for c in CANONICAL)
        noncanonical_nonchrM_reads = max(total_mapped_idx - canonical_nuclear_reads - idx_by_chrom.get("chrM", {}).get("mapped_reads", 0), 0)
        canonical_rows = [idx_by_chrom[c] for c in CANONICAL if c in idx_by_chrom]
        top_row = max(canonical_rows, key=lambda r: r["mapped_reads"]) if canonical_rows else None
        top_chrom = top_row["chrom"] if top_row else "NA"
        top_reads = top_row["mapped_reads"] if top_row else 0
        top_fraction = safe_div(top_reads, canonical_nuclear_reads)
        autosome_rates = [
            safe_div(idx_by_chrom[c]["mapped_reads"], idx_by_chrom[c]["length"] / 1e6)
            for c in AUTOSOMES
            if c in idx_by_chrom and idx_by_chrom[c]["length"] > 0
        ]
        autosome_cv = cv(autosome_rates)
        covered_autosomes = sum(idx_by_chrom.get(c, {}).get("mapped_reads", 0) > 0 for c in AUTOSOMES)

        chrM_stats = chrM_depth(sample, bam)
        chrM_bases = chrM_stats["chrM_bases"]
        nuclear_regions = [(c, idx_by_chrom[c]["length"]) for c in CANONICAL if c in idx_by_chrom and idx_by_chrom[c]["length"] > 0]
        nuclear_bases = bedcov_total(nuclear_regions, bam)

        mtDNA_depth = chrM_bases / MTDNA_DENOMINATOR
        mean_nuclear_depth = nuclear_bases / NUCLEAR_DENOMINATOR
        chrM_fraction_total = safe_div(chrM_reads, total_reads)
        chrM_fraction_mapped = safe_div(chrM_reads, mapped_reads)
        nuclear_fraction_mapped = safe_div(nuclear_reads, mapped_reads)

        composition, nuclear_judgment, enrichment, failure = judge(
            chrM_fraction_mapped,
            nuclear_fraction_mapped,
            mtDNA_depth,
            top_fraction,
            autosome_cv,
            covered_autosomes,
        )

        depth_rows.append(
            {
                "sample_id": sample,
                "total_reads": total_reads,
                "mapped_reads": mapped_reads,
                "chrM_reads": chrM_reads,
                "nuclear_reads": nuclear_reads,
                "chrM_fraction_total": chrM_fraction_total,
                "chrM_fraction_mapped": chrM_fraction_mapped,
                "nuclear_fraction_mapped": nuclear_fraction_mapped,
                "chrM_bases": chrM_bases,
                "mtDNA_depth": mtDNA_depth,
                "nuclear_bases": nuclear_bases,
                "mean_nuclear_depth": mean_nuclear_depth,
            }
        )
        mt_rows.append({"sample_id": sample, "chrM_bases": chrM_bases, "mtDNA_depth": mtDNA_depth})
        uniform_rows.append(
            {
                "sample_id": sample,
                "chrM_positions": chrM_stats["positions"],
                "mean_depth": chrM_stats["mean_depth"],
                "median_depth": chrM_stats["median_depth"],
                "min_depth": chrM_stats["min_depth"],
                "max_depth": chrM_stats["max_depth"],
                "coverage_cv": chrM_stats["coverage_cv"],
                "fraction_chrM_bases_depth_ge_10": chrM_stats["fraction_chrM_bases_depth_ge_10"],
                "fraction_chrM_bases_depth_ge_30": chrM_stats["fraction_chrM_bases_depth_ge_30"],
                "fraction_chrM_bases_depth_ge_100": chrM_stats["fraction_chrM_bases_depth_ge_100"],
            }
        )
        rca_rows.append(
            {
                "sample_id": sample,
                "nuclear_reads": nuclear_reads,
                "chrM_reads": chrM_reads,
                "total_mapped": mapped_reads,
                "chrM_fraction": chrM_fraction_mapped,
                "canonical_nuclear_reads": canonical_nuclear_reads,
                "noncanonical_nonchrM_reads": noncanonical_nonchrM_reads,
                "top_nuclear_chromosome": top_chrom,
                "top_nuclear_reads": top_reads,
                "top_nuclear_fraction_of_canonical_nuclear": top_fraction,
                "autosome_reads_per_mb_cv": autosome_cv,
                "mtDNA_depth": mtDNA_depth,
                "mean_nuclear_depth": mean_nuclear_depth,
                "composition_call": composition,
                "nuclear_pattern_judgment": nuclear_judgment,
                "mtDNA_enrichment_judgment": enrichment,
                "failure_interpretation": failure,
            }
        )
        write_top_chromosomes(sample, idx_rows, mapped_reads)

    def write_table(path, rows):
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, delimiter="\t", fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for item in rows:
                out = {}
                for key, value in item.items():
                    out[key] = fmt_float(value) if isinstance(value, float) else value
                writer.writerow(out)

    write_table(STATS_DIR / "dna_mt_depth_summary.tsv", depth_rows)
    write_table(STATS_DIR / "mtDNA_depth.tsv", mt_rows)
    write_table(STATS_DIR / "mtDNA_coverage_uniformity.tsv", uniform_rows)
    write_table(STATS_DIR / "RCA_nuclear_vs_mt_summary.tsv", rca_rows)

    print(f"Wrote {STATS_DIR / 'dna_mt_depth_summary.tsv'}")
    print(f"Wrote {STATS_DIR / 'RCA_nuclear_vs_mt_summary.tsv'}")
    print(f"Wrote {STATS_DIR / 'mtDNA_coverage_uniformity.tsv'}")


if __name__ == "__main__":
    main()
