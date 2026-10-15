"""Tests for genome assembly parsing, input validation, and QC warnings."""

import os
import pytest
from backend.genome import calculate_sha256, calculate_n50, parse_genome_fasta


def test_calculate_sha256(tmp_path):
    f = tmp_path / "test.fasta"
    f.write_text(">seq1\nATGCATGC\n", encoding="utf-8")
    h = calculate_sha256(str(f))
    assert isinstance(h, str)
    assert len(h) == 64


def test_calculate_n50():
    lengths = [100, 200, 300, 400]
    assert calculate_n50(lengths) == 300
    assert calculate_n50([]) == 0


def test_parse_genome_fasta_valid_small(tmp_path):
    f = tmp_path / "valid_small.fasta"
    # 1000 bp ATGC -> 50% GC
    seq = "ATGC" * 250
    f.write_text(f">contig_1 length=1000\n{seq}\n", encoding="utf-8")

    metrics = parse_genome_fasta(str(f))
    assert metrics["sequence_count"] == 1
    assert metrics["total_length"] == 1000
    assert metrics["gc_content_pct"] == 50.0
    assert metrics["ambiguous_count"] == 0
    assert metrics["ambiguous_pct"] == 0.0
    assert metrics["n50"] == 1000
    assert any("under 0.5 Mbp" in w for w in metrics["warnings"])


def test_parse_genome_ambiguous_nucleotides(tmp_path):
    f = tmp_path / "ambiguous.fasta"
    # Sequence with standard bases and IUPAC ambiguous bases (R, Y, S, W, K, M, B, D, H, V, N)
    seq = "ATGC" * 100 + "NNNRYSSW" # 400 standard + 8 ambiguous = 408 total
    f.write_text(f">contig_ambig\n{seq}\n", encoding="utf-8")

    metrics = parse_genome_fasta(str(f))
    assert metrics["sequence_count"] == 1
    assert metrics["total_length"] == 408
    assert metrics["ambiguous_count"] == 8
    assert metrics["ambiguous_pct"] > 0
    assert metrics["gc_content_pct"] == 50.0  # GC calculated strictly on standard bases: 200/400
    warnings_str = " ".join(metrics["warnings"])
    assert "ambiguous IUPAC bases" in warnings_str


def test_parse_genome_empty_file_rejected(tmp_path):
    f = tmp_path / "empty.fasta"
    f.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="completely empty"):
        parse_genome_fasta(str(f))


def test_parse_genome_whitespace_file_rejected(tmp_path):
    f = tmp_path / "spaces.fasta"
    f.write_text("   \n\t  \n  ", encoding="utf-8")
    with pytest.raises(ValueError, match="only whitespace"):
        parse_genome_fasta(str(f))


def test_parse_genome_malformed_syntax_rejected(tmp_path):
    f = tmp_path / "malformed.fasta"
    f.write_text("This is not a fasta file, missing header\nATGCATGC", encoding="utf-8")
    with pytest.raises(ValueError, match="does not start with a valid FASTA header"):
        parse_genome_fasta(str(f))


def test_parse_genome_empty_sequence_record_rejected(tmp_path):
    f = tmp_path / "empty_record.fasta"
    f.write_text(">contig_empty\n>contig_valid\nATGCATGC\n", encoding="utf-8")
    with pytest.raises(ValueError, match="completely empty"):
        parse_genome_fasta(str(f))


def test_parse_genome_no_valid_nucleotides_rejected(tmp_path):
    f = tmp_path / "no_nucleotides.fasta"
    f.write_text(">contig_junk\n1234567890!@#$%^&*\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no valid nucleotide characters"):
        parse_genome_fasta(str(f))


def test_parse_genome_non_existent_raises():
    with pytest.raises(FileNotFoundError):
        parse_genome_fasta("non_existent_file_xyz.fasta")
