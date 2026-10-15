"""Genome metrics and quality inspection module using Biopython.

Strict input validation:
- Rejects empty files.
- Rejects malformed FASTA syntax.
- Rejects records with empty sequence content.
- Rejects sequences with no valid nucleotide characters.
- Computes standard bases (A, T, G, C, U) and explicitly handles IUPAC ambiguous bases.
- Never silently repairs invalid sequence data.
"""

import hashlib
import os
from typing import Any
from Bio import SeqIO

# Standard and IUPAC nucleotide sets
STANDARD_BASES = set("ACGTUacgtu")
IUPAC_AMBIGUOUS_BASES = set("RYSWKMBDHVNryswkmbdhvn")
VALID_NUCLEOTIDES = STANDARD_BASES | IUPAC_AMBIGUOUS_BASES


def calculate_sha256(filepath: str) -> str:
    """Calculate the cryptographic SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def calculate_n50(lengths: list[int]) -> int:
    """Calculate N50 from a list of sequence lengths."""
    if not lengths:
        return 0
    sorted_lengths = sorted(lengths, reverse=True)
    total_length = sum(sorted_lengths)
    target = total_length / 2.0
    cumulative = 0
    for length in sorted_lengths:
        cumulative += length
        if cumulative >= target:
            return length
    return 0


def parse_genome_fasta(filepath: str) -> dict[str, Any]:
    """
    Parse an assembled bacterial genome in FASTA/FA/FNA format using Biopython.

    Validation rules:
    - Rejects missing, empty, or whitespace-only files.
    - Rejects syntax-malformed FASTA records.
    - Rejects records containing zero sequence length.
    - Rejects sequences containing no valid nucleotide bases.
    - Identifies non-IUPAC characters and raises warnings or errors.

    GC Calculation Policy:
    - Standard bases counted: G and C.
    - Total standard denominator: A + T + G + C + U.
    - IUPAC ambiguous bases (R, Y, S, W, K, M, B, D, H, V, N) are tracked separately
      and are not arbitrarily counted as G or C.
    - Ambiguous percentage is reported explicitly.

    Returns:
        dict containing:
            - sequence_count (int)
            - total_length (int)
            - gc_content_pct (float | None)
            - standard_base_count (int)
            - ambiguous_count (int)
            - ambiguous_pct (float)
            - n50 (int)
            - min_length (int)
            - max_length (int)
            - warnings (list[str])
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"FASTA file not found: {filepath}")

    # Check for empty file or whitespace only
    file_size = os.path.getsize(filepath)
    if file_size == 0:
        raise ValueError("FASTA file is completely empty (0 bytes).")

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        raw_head = f.read(4096).strip()
        if not raw_head:
            raise ValueError("FASTA file contains only whitespace.")
        if not raw_head.startswith(">"):
            raise ValueError(
                "Malformed FASTA: File does not start with a valid FASTA header ('>')."
            )

    ext = os.path.splitext(filepath)[1].lower()
    allowed_exts = {".fasta", ".fa", ".fna"}
    warnings: list[str] = []

    if ext not in allowed_exts:
        warnings.append(
            f"File extension '{ext}' is non-standard. Expected one of .fasta, .fa, or .fna."
        )

    seq_count = 0
    total_length = 0
    gc_count = 0
    standard_base_count = 0
    ambiguous_count = 0
    non_nucleotide_count = 0
    n_count = 0
    short_seq_count = 0
    lengths: list[int] = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as handle:
            records = list(SeqIO.parse(handle, "fasta"))
    except Exception as exc:
        raise ValueError(f"Biopython failed to parse FASTA file: {str(exc)}") from exc

    if not records:
        raise ValueError("FASTA file contains no valid sequence records.")

    for idx, record in enumerate(records, start=1):
        seq_id = record.id or f"record_{idx}"
        seq_str = str(record.seq).strip()
        seq_len = len(seq_str)

        # Reject records with empty sequence
        if seq_len == 0:
            raise ValueError(
                f"Malformed FASTA: Sequence record '{seq_id}' (index {idx}) is completely empty."
            )

        # Validate sequence content
        record_valid_bases = 0
        record_non_nucleotide = 0

        for char in seq_str:
            if char in STANDARD_BASES:
                record_valid_bases += 1
                standard_base_count += 1
                if char in "GCgc":
                    gc_count += 1
            elif char in IUPAC_AMBIGUOUS_BASES:
                record_valid_bases += 1
                ambiguous_count += 1
                if char in "Nn":
                    n_count += 1
            else:
                record_non_nucleotide += 1
                non_nucleotide_count += 1

        if record_valid_bases == 0:
            raise ValueError(
                f"Invalid FASTA content: Record '{seq_id}' contains no valid nucleotide characters."
            )

        if record_non_nucleotide > 0:
            warnings.append(
                f"Record '{seq_id}' contains {record_non_nucleotide} non-IUPAC characters (e.g. invalid symbols/digits)."
            )

        seq_count += 1
        lengths.append(seq_len)
        total_length += seq_len

        if seq_len < 500:
            short_seq_count += 1

    # Calculate GC content on standard bases
    if standard_base_count > 0:
        gc_content_pct = round((gc_count / standard_base_count) * 100.0, 2)
    else:
        gc_content_pct = None
        warnings.append(
            "Could not calculate GC content: assembly contains zero standard nucleotides (A/T/G/C)."
        )

    # Calculate ambiguous fraction
    ambiguous_pct = round((ambiguous_count / total_length) * 100.0, 2) if total_length > 0 else 0.0

    if ambiguous_count > 0:
        warnings.append(
            f"Assembly contains {ambiguous_count:,} ambiguous IUPAC bases ({ambiguous_pct}% of total length)."
        )

    if total_length > 0 and (n_count / total_length) > 0.01:
        n_pct = (n_count / total_length) * 100.0
        warnings.append(
            f"High proportion of unresolved N bases: {n_pct:.2f}% of total assembly."
        )

    if short_seq_count > 0:
        warnings.append(
            f"{short_seq_count} contig(s) are shorter than 500 bp, which may reduce AMR gene detection sensitivity."
        )

    # Typical bacterial genomes range between ~0.5 Mbp and ~12 Mbp
    if total_length < 500000:
        warnings.append(
            f"Total assembly length ({total_length:,} bp) is under 0.5 Mbp; assembly may be partial or incomplete."
        )
    elif total_length > 12000000:
        warnings.append(
            f"Total assembly length ({total_length:,} bp) is unusually large for a bacterial genome (>12 Mbp)."
        )

    if gc_content_pct is not None and (gc_content_pct < 25.0 or gc_content_pct > 75.0):
        warnings.append(
            f"GC content ({gc_content_pct}%) is outside typical bacterial ranges (25%-75%)."
        )

    n50_val = calculate_n50(lengths)

    return {
        "sequence_count": seq_count,
        "total_length": total_length,
        "gc_content_pct": gc_content_pct,
        "standard_base_count": standard_base_count,
        "ambiguous_count": ambiguous_count,
        "ambiguous_pct": ambiguous_pct,
        "n50": n50_val,
        "min_length": min(lengths) if lengths else 0,
        "max_length": max(lengths) if lengths else 0,
        "warnings": warnings,
    }
