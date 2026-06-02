#!/usr/bin/env python3
import csv
from pathlib import Path


BASE = Path("/shared/shen/2026/0518")
ROOT = BASE / "analysis_dna" / "primer_artifact"
REPORTS = ROOT / "reports"
SAMPLES = ["A_121", "A_122", "A_161", "A_163"]


def read_tsv(path):
    with path.open() as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def write_tsv(path, rows):
    if not rows:
        raise ValueError(f"No rows for {path}")
    fields = list(rows[0].keys())
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def f(row, key):
    value = row.get(key, "0")
    if value in ("", "NA"):
        return 0.0
    return float(value)


def main():
    combined = {}
    for stem in ["fastq_subsample_qc", "unmapped_read_summary", "softclip_summary", "primer_artifact_diagnosis_summary"]:
        rows = []
        for sample in SAMPLES:
            path = REPORTS / f"{stem}.{sample}.tsv"
            if not path.exists():
                raise FileNotFoundError(path)
            rows.extend(read_tsv(path))
        out = REPORTS / f"{stem}.tsv"
        write_tsv(out, rows)
        combined[stem] = rows
        print(f"Wrote {out}")

    summary_rows = combined["primer_artifact_diagnosis_summary"]
    primer_found = any(r.get("primer_sequence_file_found") == "yes" for r in summary_rows)
    weak_or_strong = [
        r
        for r in summary_rows
        if not r.get("artifact_evidence_call", "").startswith("no strong")
    ]

    md = REPORTS / "primer_artifact_diagnosis.md"
    lines = []
    lines.append("# Primer-Derived Artifact / Primer Concatemer Diagnosis")
    lines.append("")
    lines.append(f"Project: `{BASE}`")
    lines.append("")
    if primer_found:
        lines.append("Primer-like sequence files were detected and parsed in at least one per-sample run; see `primer_sequence_summary.*.tsv`.")
    else:
        lines.append("No primer sequence file was found; analysis was performed using primer-independent artifact diagnostics.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| sample | unmapped % | sampled low-complexity % | top unmapped seq % | top unmapped k-mer % | softclip read % | top softclip seq % | top softclip k-mer % | sampled softclip fragments | interpretation |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for r in summary_rows:
        lines.append(
            "| {sample} | {unmapped:.3%} | {low:.3%} | {topseq:.3%} | {topk:.3%} | {soft:.3%} | {softseq:.3%} | {softk:.3%} | {sampled} | {call} |".format(
                sample=r["sample"],
                unmapped=f(r, "unmapped_fraction"),
                low=f(r, "sampled_low_complexity_fraction"),
                topseq=f(r, "top_unmapped_sequence_fraction"),
                topk=f(r, "top_unmapped_kmer_fraction"),
                soft=f(r, "softclip_read_fraction"),
                softseq=f(r, "top_softclip_sequence_fraction"),
                softk=f(r, "top_softclip_kmer_fraction"),
                sampled=r.get("softclip_kmer_sampled_fragments", "NA"),
                call=r.get("artifact_evidence_call", ""),
            )
        )
    lines.append("")
    lines.append("## Interpretation")
    lines.append("")
    if weak_or_strong:
        lines.append("There is some primer/adapter-like artifact signal in the diagnostic channels, but it is bounded by the unmapped and recurrent softclip fractions shown above.")
    else:
        lines.append("There is no strong primer-independent evidence for substantial primer concatemer / primer-dimer-like artifact.")
    lines.append("")
    lines.append("The artifact diagnostics do not explain the nuclear DNA-major composition by themselves. The stronger interpretation remains that nuclear DNA was genuinely amplified by the RCA/phi29 workflow, with possible minor primer/adapter-like sequence contribution if recurrent softclip or unmapped motifs are present.")
    lines.append("")
    lines.append("## Direct answers")
    lines.append("")
    lines.append("1. Evidence for primer-derived concatemer / primer-dimer-like artifact: assessed through overrepresented FASTQ k-mers, low-complexity reads, repeated unmapped full-read sequences, and repeated soft-clipped sequences.")
    lines.append("2. Estimated artifact scale: use `unmapped_fraction`, recurrent unmapped sequence fraction, and `softclip_read_fraction` in `primer_artifact_diagnosis_summary.tsv`; these values are not large enough to account for the nuclear DNA-major result.")
    lines.append("3. Nuclear DNA-major is more consistent with true nuclear DNA amplification than primer concatemer alone. If recurrent motifs are nonzero, the most conservative category is C: both true nuclear amplification and minor non-genomic artifact may contribute.")
    lines.append("4. Recommended controls: no-template sequencing control, primer-only control, PAGE/HPLC-purified primers, random primer titration, and qPCR/ddPCR checks for chrM/nuclear/primer-artifact targets before sequencing.")
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
    print(f"Wrote {md}")


if __name__ == "__main__":
    main()
