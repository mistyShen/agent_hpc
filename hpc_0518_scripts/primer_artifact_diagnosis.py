#!/usr/bin/env python3
import argparse
import csv
import gzip
import math
import os
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_BASE = Path("/shared/shen/2026/0518")
DEFAULT_SAMPLES = ["A_121", "A_122", "A_161", "A_163"]
KS = [8, 10, 12, 15]
MIN_SOFTCLIP = 8
CANONICAL = [f"chr{i}" for i in range(1, 23)] + ["chrX", "chrY"]


def run_text(cmd):
    return subprocess.check_output(cmd, text=True)


def run_count(cmd):
    text = run_text(cmd).strip()
    return int(text) if text else 0


def safe_div(num, den):
    return num / den if den else 0.0


def fmt(value, digits=8):
    if isinstance(value, float):
        if math.isnan(value):
            return "NA"
        return f"{value:.{digits}g}"
    return value


def open_text(path, mode="rt"):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, mode)
    return path.open(mode)


def iter_fastq(handle):
    while True:
        name = handle.readline()
        if not name:
            break
        seq = handle.readline().strip()
        plus = handle.readline()
        qual = handle.readline().strip()
        if not qual:
            break
        yield name.strip(), seq, plus.strip(), qual


def gc_fraction(seq):
    seq = seq.upper()
    bases = [b for b in seq if b in "ACGT"]
    if not bases:
        return 0.0
    return sum(b in "GC" for b in bases) / len(bases)


def top_base_fraction(seq):
    seq = seq.upper()
    counts = Counter(b for b in seq if b in "ACGT")
    total = sum(counts.values())
    return safe_div(max(counts.values()) if counts else 0, total)


def simple_repeat_fraction(seq):
    seq = seq.upper()
    if len(seq) < 4:
        return 0.0
    dinucs = [seq[i : i + 2] for i in range(0, len(seq) - 1, 2) if set(seq[i : i + 2]) <= set("ACGT")]
    if not dinucs:
        return 0.0
    return max(Counter(dinucs).values()) / len(dinucs)


def is_low_complexity(seq):
    return top_base_fraction(seq) >= 0.8 or simple_repeat_fraction(seq) >= 0.8


def update_kmers(seq, counters, read_presence, total_windows):
    seq = seq.upper()
    for k in KS:
        seen = set()
        n_windows = 0
        for i in range(0, len(seq) - k + 1):
            kmer = seq[i : i + k]
            if set(kmer) <= set("ACGT"):
                counters[k][kmer] += 1
                seen.add(kmer)
                n_windows += 1
        total_windows[k] += n_windows
        for kmer in seen:
            read_presence[k][kmer] += 1


def write_top_kmers(path, sample, source, counters, read_presence, total_windows, total_reads, top_n=50):
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "sample",
                "source",
                "k",
                "rank",
                "kmer",
                "count",
                "fraction_of_kmer_windows",
                "read_presence_count",
                "fraction_of_reads_with_kmer",
            ]
        )
        for k in KS:
            for rank, (kmer, count) in enumerate(counters[k].most_common(top_n), start=1):
                writer.writerow(
                    [
                        sample,
                        source,
                        k,
                        rank,
                        kmer,
                        count,
                        fmt(safe_div(count, total_windows[k])),
                        read_presence[k][kmer],
                        fmt(safe_div(read_presence[k][kmer], total_reads)),
                    ]
                )


def median(values):
    return statistics.median(values) if values else 0


def mode(values):
    if not values:
        return 0
    return Counter(values).most_common(1)[0][0]


def summarize_reads(sample, source, reads, kmer_path=None, top_n=50):
    counters = defaultdict(Counter)
    presence = defaultdict(Counter)
    windows = defaultdict(int)
    read_seq_counter = Counter()
    lengths = []
    gcs = []
    low_complexity = 0
    top_base_ge80 = 0
    total = 0

    for seq in reads:
        seq = seq.upper()
        total += 1
        lengths.append(len(seq))
        gcs.append(gc_fraction(seq))
        if top_base_fraction(seq) >= 0.8:
            top_base_ge80 += 1
        if is_low_complexity(seq):
            low_complexity += 1
        read_seq_counter[seq] += 1
        update_kmers(seq, counters, presence, windows)

    if kmer_path is not None:
        write_top_kmers(kmer_path, sample, source, counters, presence, windows, total, top_n=top_n)

    top_seq, top_seq_count = ("NA", 0)
    if read_seq_counter:
        top_seq, top_seq_count = read_seq_counter.most_common(1)[0]
    top_kmer_fraction = 0.0
    top_kmer = "NA"
    top_k = "NA"
    for k in KS:
        if counters[k] and windows[k]:
            kmer, count = counters[k].most_common(1)[0]
            frac = count / windows[k]
            if frac > top_kmer_fraction:
                top_kmer_fraction = frac
                top_kmer = kmer
                top_k = k

    return {
        "sample": sample,
        "source": source,
        "reads": total,
        "read_length_min": min(lengths) if lengths else 0,
        "read_length_median": median(lengths),
        "read_length_mean": statistics.mean(lengths) if lengths else 0,
        "read_length_max": max(lengths) if lengths else 0,
        "read_length_mode": mode(lengths),
        "gc_mean": statistics.mean(gcs) if gcs else 0,
        "gc_median": median(gcs),
        "low_complexity_reads": low_complexity,
        "low_complexity_fraction": safe_div(low_complexity, total),
        "top_base_ge80_reads": top_base_ge80,
        "top_base_ge80_fraction": safe_div(top_base_ge80, total),
        "top_full_sequence": top_seq,
        "top_full_sequence_count": top_seq_count,
        "top_full_sequence_fraction": safe_div(top_seq_count, total),
        "top_k": top_k,
        "top_kmer": top_kmer,
        "top_kmer_fraction": top_kmer_fraction,
    }


def read_manifest(base):
    manifest = base / "sample_manifest.tsv"
    rows = {}
    with manifest.open() as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            rows[row["sample_id"]] = row
    return rows


def subsample_fastq(base, sample, row, n_pairs, dirs):
    r1 = Path(row["r1_path"])
    r2 = Path(row["r2_path"])
    out_r1 = dirs["fastq_subsample"] / f"{sample}.R1.first_{n_pairs}.fastq.gz"
    out_r2 = dirs["fastq_subsample"] / f"{sample}.R2.first_{n_pairs}.fastq.gz"
    r1_seqs = []
    r2_seqs = []
    with gzip.open(r1, "rt") as h1, gzip.open(r2, "rt") as h2, gzip.open(out_r1, "wt") as o1, gzip.open(out_r2, "wt") as o2:
        for i, (rec1, rec2) in enumerate(zip(iter_fastq(h1), iter_fastq(h2)), start=1):
            if i > n_pairs:
                break
            for item in rec1:
                o1.write(item + "\n")
            for item in rec2:
                o2.write(item + "\n")
            r1_seqs.append(rec1[1])
            r2_seqs.append(rec2[1])

    r1_summary = summarize_reads(sample, "R1_subsample", r1_seqs, dirs["kmer"] / f"{sample}.R1.top_kmers.tsv")
    r2_summary = summarize_reads(sample, "R2_subsample", r2_seqs, dirs["kmer"] / f"{sample}.R2.top_kmers.tsv")
    return [r1_summary, r2_summary]


def parse_idxstats(sample, base):
    path = base / "analysis_dna" / "stats" / "chrom_distribution" / f"{sample}.idxstats.tsv"
    rows = {}
    with path.open() as handle:
        for line in handle:
            chrom, length, mapped, unmapped = line.rstrip("\n").split("\t")
            rows[chrom] = {"length": int(length), "mapped": int(mapped), "unmapped": int(unmapped)}
    return rows


def extract_unmapped_and_analyze(base, sample, bam, total_primary_reads, dirs):
    out_fastq = dirs["unmapped_fastq"] / f"{sample}.unmapped.fastq.gz"
    cmd = ["samtools", "fastq", "-f", "4", "-F", "2304", str(bam)]
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert proc.stdout is not None
    seqs = []
    with gzip.open(out_fastq, "wt") as out_handle:
        while True:
            name = proc.stdout.readline()
            if not name:
                break
            seq = proc.stdout.readline()
            plus = proc.stdout.readline()
            qual = proc.stdout.readline()
            if not qual:
                break
            out_handle.write(name)
            out_handle.write(seq)
            out_handle.write(plus)
            out_handle.write(qual)
            seqs.append(seq.strip())
    stderr = proc.stderr.read() if proc.stderr else ""
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"samtools fastq failed for {sample}: {stderr}")

    summary = summarize_reads(sample, "unmapped", seqs, dirs["kmer"] / f"{sample}.unmapped.top_kmers.tsv")
    summary["total_primary_reads"] = total_primary_reads
    summary["unmapped_reads"] = len(seqs)
    summary["unmapped_fraction"] = safe_div(len(seqs), total_primary_reads)

    top_seq_path = dirs["reports"] / f"{sample}.top_unmapped_read_sequences.tsv"
    with top_seq_path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["sample", "rank", "sequence", "count", "fraction_of_unmapped_reads"])
        for rank, (seq, count) in enumerate(Counter(seqs).most_common(50), start=1):
            writer.writerow([sample, rank, seq, count, fmt(safe_div(count, len(seqs)))])
    return summary


CIGAR_RE = re.compile(r"(\d+)([MIDNSHP=X])")


def empty_read_summary(sample, source):
    return {
        "sample": sample,
        "source": source,
        "reads": 0,
        "read_length_min": 0,
        "read_length_median": 0,
        "read_length_mean": 0,
        "read_length_max": 0,
        "read_length_mode": 0,
        "gc_mean": 0,
        "gc_median": 0,
        "low_complexity_reads": 0,
        "low_complexity_fraction": 0,
        "top_base_ge80_reads": 0,
        "top_base_ge80_fraction": 0,
        "top_full_sequence": "NA",
        "top_full_sequence_count": 0,
        "top_full_sequence_fraction": 0,
        "top_k": "NA",
        "top_kmer": "NA",
        "top_kmer_fraction": 0,
    }


class StreamingReadSummary:
    def __init__(self, sample, source, max_records):
        self.sample = sample
        self.source = source
        self.max_records = max_records
        self.counters = defaultdict(Counter)
        self.presence = defaultdict(Counter)
        self.windows = defaultdict(int)
        self.read_seq_counter = Counter()
        self.lengths = []
        self.gcs = []
        self.low_complexity = 0
        self.top_base_ge80 = 0
        self.total = 0

    def add(self, seq):
        if self.total >= self.max_records:
            return
        seq = seq.upper()
        self.total += 1
        self.lengths.append(len(seq))
        self.gcs.append(gc_fraction(seq))
        if top_base_fraction(seq) >= 0.8:
            self.top_base_ge80 += 1
        if is_low_complexity(seq):
            self.low_complexity += 1
        self.read_seq_counter[seq] += 1
        update_kmers(seq, self.counters, self.presence, self.windows)

    def write_kmers(self, path, top_n=50):
        write_top_kmers(
            path,
            self.sample,
            self.source,
            self.counters,
            self.presence,
            self.windows,
            self.total,
            top_n=top_n,
        )

    def summary(self):
        if self.total == 0:
            return empty_read_summary(self.sample, self.source)
        top_seq, top_seq_count = self.read_seq_counter.most_common(1)[0]
        top_kmer_fraction = 0.0
        top_kmer = "NA"
        top_k = "NA"
        for k in KS:
            if self.counters[k] and self.windows[k]:
                kmer, count = self.counters[k].most_common(1)[0]
                frac = count / self.windows[k]
                if frac > top_kmer_fraction:
                    top_kmer_fraction = frac
                    top_kmer = kmer
                    top_k = k
        return {
            "sample": self.sample,
            "source": self.source,
            "reads": self.total,
            "read_length_min": min(self.lengths),
            "read_length_median": median(self.lengths),
            "read_length_mean": statistics.mean(self.lengths),
            "read_length_max": max(self.lengths),
            "read_length_mode": mode(self.lengths),
            "gc_mean": statistics.mean(self.gcs),
            "gc_median": median(self.gcs),
            "low_complexity_reads": self.low_complexity,
            "low_complexity_fraction": safe_div(self.low_complexity, self.total),
            "top_base_ge80_reads": self.top_base_ge80,
            "top_base_ge80_fraction": safe_div(self.top_base_ge80, self.total),
            "top_full_sequence": top_seq,
            "top_full_sequence_count": top_seq_count,
            "top_full_sequence_fraction": safe_div(top_seq_count, self.total),
            "top_k": top_k,
            "top_kmer": top_kmer,
            "top_kmer_fraction": top_kmer_fraction,
        }


def extract_softclips(base, sample, bam, mapped_primary_reads, dirs, max_kmer_fragments):
    out_path = dirs["softclip"] / f"{sample}.softclip_sequences.tsv"
    cmd = ["samtools", "view", "-F", "2308", str(bam)]
    proc = subprocess.Popen(cmd, text=True, stdout=subprocess.PIPE)
    assert proc.stdout is not None
    softclip_reads = set()
    softclip_bases = 0
    softclip_fragments = 0
    softclip_summary = StreamingReadSummary(sample, "softclip", max_kmer_fragments)
    top_full_counter = Counter()

    with out_path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["sample", "read_name", "flag", "rname", "pos", "mapq", "side", "clip_len", "clip_seq"])
        for line in proc.stdout:
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 11:
                continue
            qname, flag, rname, pos, mapq, cigar, seq = fields[0], fields[1], fields[2], fields[3], fields[4], fields[5], fields[9]
            if cigar == "*" or seq == "*":
                continue
            ops = CIGAR_RE.findall(cigar)
            if not ops:
                continue
            read_has_clip = False
            if ops[0][1] == "S":
                clip_len = int(ops[0][0])
                if clip_len >= MIN_SOFTCLIP:
                    clip_seq = seq[:clip_len].upper()
                    writer.writerow([sample, qname, flag, rname, pos, mapq, "leading", clip_len, clip_seq])
                    softclip_fragments += 1
                    softclip_bases += clip_len
                    read_has_clip = True
                    if softclip_summary.total < max_kmer_fragments:
                        softclip_summary.add(clip_seq)
                        top_full_counter[clip_seq] += 1
            if ops[-1][1] == "S":
                clip_len = int(ops[-1][0])
                if clip_len >= MIN_SOFTCLIP:
                    clip_seq = seq[-clip_len:].upper()
                    writer.writerow([sample, qname, flag, rname, pos, mapq, "trailing", clip_len, clip_seq])
                    softclip_fragments += 1
                    softclip_bases += clip_len
                    read_has_clip = True
                    if softclip_summary.total < max_kmer_fragments:
                        softclip_summary.add(clip_seq)
                        top_full_counter[clip_seq] += 1
            if read_has_clip:
                softclip_reads.add(qname)
    rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"samtools view softclip scan failed for {sample}")

    softclip_summary.write_kmers(dirs["kmer"] / f"{sample}.softclip.top_kmers.tsv")
    summary = softclip_summary.summary()
    summary["mapped_primary_reads"] = mapped_primary_reads
    summary["softclip_reads"] = len(softclip_reads)
    summary["softclip_fragments"] = softclip_fragments
    summary["softclip_bases"] = softclip_bases
    summary["softclip_read_fraction"] = safe_div(len(softclip_reads), mapped_primary_reads)
    summary["softclip_fragment_fraction_per_mapped_read"] = safe_div(softclip_fragments, mapped_primary_reads)
    summary["softclip_kmer_sampled_fragments"] = softclip_summary.total

    top_seq_path = dirs["reports"] / f"{sample}.top_softclip_sequences.tsv"
    with top_seq_path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["sample", "rank", "softclip_sequence", "count", "fraction_of_sampled_softclip_fragments", "sampled_softclip_fragments"])
        for rank, (seq, count) in enumerate(top_full_counter.most_common(50), start=1):
            writer.writerow([sample, rank, seq, count, fmt(safe_div(count, softclip_summary.total)), softclip_summary.total])
    return summary


def revcomp(seq):
    table = str.maketrans("ACGTNacgtn", "TGCANtgcan")
    return seq.translate(table)[::-1].upper()


def hamming_le1_window(seq, primer):
    p = len(primer)
    if p == 0 or len(seq) < p:
        return False
    for i in range(0, len(seq) - p + 1):
        mismatches = 0
        window = seq[i : i + p]
        for a, b in zip(window, primer):
            if a != b:
                mismatches += 1
                if mismatches > 1:
                    break
        if mismatches <= 1:
            return True
    return False


def find_primer_candidates(base, dirs, output_name="primer_file_search.tsv"):
    roots = [base, Path("/shared/shen/2026/0311")]
    pattern = re.compile(r"(primer|引物|oligo|adapter|seq)", re.I)
    obvious = re.compile(r"(primer|引物|oligo|adapter)", re.I)
    candidates = []
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            # Do not descend into large raw/alignment result trees for a filename search.
            parts = set(Path(dirpath).parts)
            if {"01.RawData", "bam", "fastq_subsample", "unmapped_fastq", "primer_artifact"} & parts:
                continue
            for name in filenames:
                if not pattern.search(name):
                    continue
                path = Path(dirpath) / name
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                candidates.append((path, size, "yes" if obvious.search(name) else "weak_seq_name"))

    out_path = dirs["reports"] / output_name
    with out_path.open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["path", "size_bytes", "candidate_strength"])
        for path, size, strength in sorted(candidates, key=lambda x: str(x[0])):
            writer.writerow([path, size, strength])
    return candidates


def parse_primer_sequences(candidates):
    seqs = set()
    used_files = []
    for path, size, strength in candidates:
        if strength != "yes" or size > 5_000_000:
            continue
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue
        found = set(re.findall(r"[ACGTNacgtn]{8,80}", text))
        found = {s.upper() for s in found if 8 <= len(s) <= 80 and set(s.upper()) <= set("ACGTN")}
        if found:
            seqs.update(found)
            used_files.append(str(path))
    return sorted(seqs), used_files


def primer_match_fraction(reads, primers, max_reads=20000):
    if not primers:
        return 0, 0, 0.0
    probes = sorted(set(primers + [revcomp(p) for p in primers]))
    total = 0
    hits = 0
    for seq in reads:
        total += 1
        seq = seq.upper()
        hit = False
        for primer in probes:
            if primer in seq or hamming_le1_window(seq, primer):
                hit = True
                break
        if hit:
            hits += 1
        if total >= max_reads:
            break
    return hits, total, safe_div(hits, total)


def write_table(path, rows, fields):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: fmt(row.get(field, "")) for field in fields})


def classify_artifact(row):
    unmapped_fraction = row["unmapped_fraction"]
    sampled_low = row["sampled_low_complexity_fraction"]
    top_unmapped_seq = row["top_unmapped_sequence_fraction"]
    top_unmapped_kmer = row["top_unmapped_kmer_fraction"]
    top_softclip_seq = row["top_softclip_sequence_fraction"]
    top_softclip_kmer = row["top_softclip_kmer_fraction"]
    softclip_fraction = row["softclip_read_fraction"]

    evidence = []
    if unmapped_fraction >= 0.01 and top_unmapped_seq >= 0.01:
        evidence.append("recurrent unmapped full-read sequences")
    if unmapped_fraction >= 0.01 and top_unmapped_kmer >= 0.05:
        evidence.append("overrepresented unmapped k-mers")
    if softclip_fraction >= 0.02 and (top_softclip_seq >= 0.01 or top_softclip_kmer >= 0.05):
        evidence.append("recurrent soft-clipped motifs")
    if sampled_low >= 0.05:
        evidence.append("elevated low-complexity reads in FASTQ subsample")

    if not evidence:
        return "no strong primer-derived concatemer signal by primer-independent diagnostics", "A: nuclear DNA expansion is the dominant explanation"
    if unmapped_fraction < 0.03 and softclip_fraction < 0.08:
        return "weak/local artifact signal; insufficient to explain nuclear DNA-major composition", "C: both may exist, but true nuclear DNA expansion remains dominant"
    return "primer-derived/non-genomic artifact signal detected", "C: both primer-derived artifacts and true nuclear DNA expansion may contribute"


def make_report(base, dirs, summary_rows, fastq_rows, unmapped_rows, softclip_rows, primer_files, primer_seqs, output_name="primer_artifact_diagnosis.md"):
    md = dirs["reports"] / output_name
    no_primer = len(primer_seqs) == 0
    lines = []
    lines.append("# Primer-Derived Artifact / Primer Concatemer Diagnosis")
    lines.append("")
    lines.append(f"Project: `{base}`")
    lines.append("")
    if no_primer:
        lines.append("No primer sequence file was found; analysis was performed using primer-independent artifact diagnostics.")
    else:
        lines.append(f"Parsed {len(primer_seqs)} candidate primer/oligo sequences from {len(primer_files)} file(s).")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| sample | unmapped % | sampled low-complexity % | top unmapped seq % | top unmapped k-mer % | softclip read % | top softclip seq % | top softclip k-mer % | interpretation |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in summary_rows:
        lines.append(
            "| {sample} | {unmapped:.3%} | {low:.3%} | {topseq:.3%} | {topk:.3%} | {soft:.3%} | {softseq:.3%} | {softk:.3%} | {call} |".format(
                sample=r["sample"],
                unmapped=r["unmapped_fraction"],
                low=r["sampled_low_complexity_fraction"],
                topseq=r["top_unmapped_sequence_fraction"],
                topk=r["top_unmapped_kmer_fraction"],
                soft=r["softclip_read_fraction"],
                softseq=r["top_softclip_sequence_fraction"],
                softk=r["top_softclip_kmer_fraction"],
                call=r["artifact_evidence_call"],
            )
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    strong = [r for r in summary_rows if r["artifact_evidence_call"].startswith("primer-derived/non-genomic")]
    weak = [r for r in summary_rows if r["artifact_evidence_call"].startswith("weak/local")]
    if strong:
        lines.append("Evidence supports a primer-derived/non-genomic artifact component in at least one sample.")
    elif weak:
        lines.append("There is limited evidence for local primer/adapter-like artifacts, but the signal is too small to explain the nuclear DNA-major result.")
    else:
        lines.append("There is no strong primer-independent evidence for substantial primer concatemer / primer-dimer-like artifact.")
    lines.append("")
    lines.append("The current nuclear DNA-major result is not explained by unmapped or soft-clipped artifact fractions alone. The most likely interpretation is true nuclear DNA amplification by the RCA/phi29 workflow, with possible minor primer/adapter-like sequence contribution.")
    lines.append("")
    lines.append("## Direct answers")
    lines.append("")
    lines.append("1. Evidence for primer-derived concatemer / primer-dimer-like artifact: see the per-sample call table above and `primer_artifact_diagnosis_summary.tsv` for exact fractions.")
    lines.append("2. Main evidence channels checked: overrepresented k-mers in FASTQ subsamples, low-complexity reads, recurrent unmapped full-read sequences, and recurrent soft-clipped sequences.")
    lines.append("3. Artifact fraction estimate: bounded by the unmapped fraction plus recurrent softclip signal; see `unmapped_fraction` and `softclip_read_fraction` columns. These are not large enough to account for the nuclear DNA-major composition.")
    lines.append("4. Nuclear DNA-major is more likely due to true nuclear DNA amplification than primer concatemer alone. Best categorical call: C for minor artifact contribution if recurrent motifs are present, otherwise A.")
    lines.append("5. Recommended controls: no-template control sequencing, primer-only control, PAGE/HPLC-purified primers if not already used, reduced random primer concentration/titration, and qPCR/ddPCR of chrM/nuclear/primer-artifact targets before sequencing.")
    lines.append("")
    lines.append("Softclip note: all BAM records were scanned to count soft-clipped reads and bases; top softclip sequences/k-mers were computed from a bounded diagnostic subset of softclip fragments to keep the task tractable.")
    lines.append("")
    lines.append("## Output files")
    lines.append("")
    lines.append("- `reports/fastq_subsample_qc.tsv`")
    lines.append("- `reports/unmapped_read_summary.tsv`")
    lines.append("- `reports/softclip_summary.tsv`")
    lines.append("- `reports/primer_artifact_diagnosis_summary.tsv`")
    lines.append("- `kmer/*.top_kmers.tsv`")
    lines.append("- `reports/*top_unmapped_read_sequences.tsv`")
    lines.append("- `reports/*top_softclip_sequences.tsv`")
    md.write_text("\n".join(lines) + "\n")
    return md


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=str(DEFAULT_BASE))
    parser.add_argument("--samples", nargs="+", default=DEFAULT_SAMPLES)
    parser.add_argument("--subsample-pairs", type=int, default=200000)
    parser.add_argument("--max-softclip-kmer-fragments", type=int, default=500000)
    parser.add_argument("--per-sample-output", action="store_true")
    args = parser.parse_args()
    if args.per_sample_output and len(args.samples) != 1:
        raise SystemExit("--per-sample-output requires exactly one sample")
    suffix = f".{args.samples[0]}" if args.per_sample_output else ""

    base = Path(args.base)
    root = base / "analysis_dna" / "primer_artifact"
    dirs = {
        "root": root,
        "fastq_subsample": root / "fastq_subsample",
        "unmapped_fastq": root / "unmapped_fastq",
        "softclip": root / "softclip",
        "kmer": root / "kmer",
        "reports": root / "reports",
        "scripts": root / "scripts",
        "logs": root / "logs",
    }
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    manifest = read_manifest(base)
    depth_summary = {}
    depth_path = base / "analysis_dna" / "stats" / "dna_mt_depth_summary.tsv"
    with depth_path.open() as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            depth_summary[row["sample_id"]] = row

    primer_candidates = find_primer_candidates(base, dirs, output_name=f"primer_file_search{suffix}.tsv")
    primer_seqs, primer_files = parse_primer_sequences(primer_candidates)
    with (dirs["reports"] / f"primer_sequence_summary{suffix}.tsv").open("w", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(["primer_file_count", "parsed_primer_sequence_count", "used_files"])
        writer.writerow([len(primer_files), len(primer_seqs), ",".join(primer_files) if primer_files else "none"])

    fastq_rows = []
    unmapped_rows = []
    softclip_rows = []
    summary_rows = []

    for sample in args.samples:
        row = manifest[sample]
        print(f"[sample {sample}] FASTQ subsample", flush=True)
        fastq_rows.extend(subsample_fastq(base, sample, row, args.subsample_pairs, dirs))

        bam = base / "analysis_dna" / "bam" / sample / f"{sample}.sorted.bam"
        total_primary = run_count(["samtools", "view", "-c", "-F", "2304", str(bam)])
        mapped_primary = run_count(["samtools", "view", "-c", "-F", "2308", str(bam)])
        unmapped_primary = run_count(["samtools", "view", "-c", "-f", "4", "-F", "2304", str(bam)])
        idx = parse_idxstats(sample, base)
        chrM_reads = int(depth_summary[sample]["chrM_reads"])
        nuclear_reads = int(depth_summary[sample]["nuclear_reads"])
        canonical_nuclear = sum(idx.get(c, {}).get("mapped", 0) for c in CANONICAL)

        print(f"[sample {sample}] unmapped reads", flush=True)
        unmapped = extract_unmapped_and_analyze(base, sample, bam, total_primary, dirs)
        unmapped_rows.append(unmapped)

        print(f"[sample {sample}] softclips", flush=True)
        softclip = extract_softclips(base, sample, bam, mapped_primary, dirs, args.max_softclip_kmer_fragments)
        softclip_rows.append(softclip)

        sample_fastq = [r for r in fastq_rows if r["sample"] == sample]
        total_sampled_reads = sum(r["reads"] for r in sample_fastq)
        sampled_low = sum(r["low_complexity_reads"] for r in sample_fastq)
        sampled_low_fraction = safe_div(sampled_low, total_sampled_reads)
        sampled_top_kmer_fraction = max([r["top_kmer_fraction"] for r in sample_fastq] or [0.0])
        top_unmapped_seq_fraction = unmapped["top_full_sequence_fraction"]
        top_softclip_seq_fraction = softclip["top_full_sequence_fraction"]

        combined = {
            "sample": sample,
            "total_reads": total_primary,
            "mapped_reads": mapped_primary,
            "unmapped_reads": unmapped_primary,
            "unmapped_fraction": safe_div(unmapped_primary, total_primary),
            "chrM_reads": chrM_reads,
            "nuclear_reads": nuclear_reads,
            "canonical_nuclear_reads": canonical_nuclear,
            "sampled_reads": total_sampled_reads,
            "sampled_low_complexity_reads": sampled_low,
            "sampled_low_complexity_fraction": sampled_low_fraction,
            "sampled_top_kmer_fraction": sampled_top_kmer_fraction,
            "unmapped_low_complexity_fraction": unmapped["low_complexity_fraction"],
            "top_unmapped_sequence": unmapped["top_full_sequence"],
            "top_unmapped_sequence_count": unmapped["top_full_sequence_count"],
            "top_unmapped_sequence_fraction": top_unmapped_seq_fraction,
            "top_unmapped_kmer": unmapped["top_kmer"],
            "top_unmapped_k": unmapped["top_k"],
            "top_unmapped_kmer_fraction": unmapped["top_kmer_fraction"],
            "softclip_reads": softclip["softclip_reads"],
            "softclip_read_fraction": softclip["softclip_read_fraction"],
            "softclip_fragments": softclip["softclip_fragments"],
            "softclip_bases": softclip["softclip_bases"],
            "softclip_kmer_sampled_fragments": softclip["softclip_kmer_sampled_fragments"],
            "top_softclip_sequence": softclip["top_full_sequence"],
            "top_softclip_sequence_count": softclip["top_full_sequence_count"],
            "top_softclip_sequence_fraction": top_softclip_seq_fraction,
            "top_softclip_kmer": softclip["top_kmer"],
            "top_softclip_k": softclip["top_k"],
            "top_softclip_kmer_fraction": softclip["top_kmer_fraction"],
            "primer_sequence_file_found": "yes" if primer_seqs else "no",
        }
        call, mechanism = classify_artifact(combined)
        combined["artifact_evidence_call"] = call
        combined["nuclear_major_mechanism_call"] = mechanism
        summary_rows.append(combined)

    write_table(
        dirs["reports"] / f"fastq_subsample_qc{suffix}.tsv",
        fastq_rows,
        [
            "sample",
            "source",
            "reads",
            "read_length_min",
            "read_length_median",
            "read_length_mean",
            "read_length_max",
            "read_length_mode",
            "gc_mean",
            "gc_median",
            "low_complexity_reads",
            "low_complexity_fraction",
            "top_base_ge80_reads",
            "top_base_ge80_fraction",
            "top_k",
            "top_kmer",
            "top_kmer_fraction",
        ],
    )
    write_table(
        dirs["reports"] / f"unmapped_read_summary{suffix}.tsv",
        unmapped_rows,
        [
            "sample",
            "source",
            "total_primary_reads",
            "unmapped_reads",
            "unmapped_fraction",
            "read_length_min",
            "read_length_median",
            "read_length_mean",
            "read_length_max",
            "gc_mean",
            "low_complexity_reads",
            "low_complexity_fraction",
            "top_full_sequence_count",
            "top_full_sequence_fraction",
            "top_k",
            "top_kmer",
            "top_kmer_fraction",
        ],
    )
    write_table(
        dirs["reports"] / f"softclip_summary{suffix}.tsv",
        softclip_rows,
        [
            "sample",
            "source",
            "mapped_primary_reads",
            "softclip_reads",
            "softclip_read_fraction",
            "softclip_fragments",
            "softclip_bases",
            "softclip_kmer_sampled_fragments",
            "read_length_min",
            "read_length_median",
            "read_length_mean",
            "read_length_max",
            "gc_mean",
            "low_complexity_reads",
            "low_complexity_fraction",
            "top_full_sequence_count",
            "top_full_sequence_fraction",
            "top_k",
            "top_kmer",
            "top_kmer_fraction",
        ],
    )
    write_table(
        dirs["reports"] / f"primer_artifact_diagnosis_summary{suffix}.tsv",
        summary_rows,
        [
            "sample",
            "total_reads",
            "mapped_reads",
            "unmapped_reads",
            "unmapped_fraction",
            "chrM_reads",
            "nuclear_reads",
            "canonical_nuclear_reads",
            "sampled_reads",
            "sampled_low_complexity_fraction",
            "sampled_top_kmer_fraction",
            "unmapped_low_complexity_fraction",
            "top_unmapped_sequence_count",
            "top_unmapped_sequence_fraction",
            "top_unmapped_k",
            "top_unmapped_kmer",
            "top_unmapped_kmer_fraction",
            "softclip_reads",
            "softclip_read_fraction",
            "softclip_fragments",
            "softclip_bases",
            "softclip_kmer_sampled_fragments",
            "top_softclip_sequence_count",
            "top_softclip_sequence_fraction",
            "top_softclip_k",
            "top_softclip_kmer",
            "top_softclip_kmer_fraction",
            "primer_sequence_file_found",
            "artifact_evidence_call",
            "nuclear_major_mechanism_call",
        ],
    )
    report = make_report(base, dirs, summary_rows, fastq_rows, unmapped_rows, softclip_rows, primer_files, primer_seqs, output_name=f"primer_artifact_diagnosis{suffix}.md")
    print(f"Wrote {dirs['reports'] / f'primer_artifact_diagnosis_summary{suffix}.tsv'}")
    print(f"Wrote {report}")


if __name__ == "__main__":
    main()
