"""Integration tests validating the interface between friend's frontend and local backend."""

import json
import os
import tempfile
import pytest
from backend.pipeline import analyze_genome
from app import build_csv_summary


def test_friend_demo_kpc_isolate():
    """Verify analysis of friend's Klebsiella pneumoniae KPC demo benchmark."""
    kpc_fasta = os.path.join("data", "demo", "klebsiella_pneumoniae_kpc.fasta")
    assert os.path.exists(kpc_fasta), "Friend demo KPC fasta must exist"

    result = analyze_genome(
        fasta_path=kpc_fasta,
        sample_id="KP-KPC-BENCHMARK",
        organism="Klebsiella pneumoniae",
    )

    # 1. Frontend top-level and provenance expectations
    assert result["sample_id"] == "KP-KPC-BENCHMARK"
    assert result["organism"] == "Klebsiella pneumoniae"
    prov = result["provenance"]
    assert prov["is_live_analysis"] is False
    assert "input_sha256" in prov and len(prov["input_sha256"]) == 64
    assert prov["engine"] == "Precomputed Demonstration Fixture"
    assert "rules_version" in prov
    assert "timestamp_utc" in prov
    assert "provenance_notes" in prov

    # 2. Genome metrics
    metrics = result["genome_metrics"]
    assert metrics["sequence_count"] == 3
    assert metrics["total_length_bp"] > 0
    assert metrics["gc_content_pct"] is not None
    assert "n50_bp" in metrics

    # 3. Detected evidence
    evidence = result["detected_evidence"]
    assert len(evidence) > 0
    symbols = [d["gene_symbol"] for d in evidence]
    assert "blaKPC-2" in symbols
    assert "blaCTX-M-15" in symbols

    for det in evidence:
        assert "gene_symbol" in det
        assert "class" in det
        assert "subclass" in det
        assert "coverage" in det
        assert "identity" in det
        assert "contig_id" in det
        assert "start" in det
        assert "stop" in det
        assert "strand" in det

    # 4. Antibiotic interpretations
    interps = result["interpretation"]
    assert len(interps) > 0
    mero = next(i for i in interps if i["antibiotic"] == "Meropenem")
    assert mero["status"] == "Resistance predicted"
    assert "blaKPC-2" in mero["evidence_genes"]
    assert mero["confidence_or_criteria"] != ""
    assert mero["rule_id"] == "RULE-CARB-001"

    # 5. CSV export generation using friend's build_csv_summary
    csv_text = build_csv_summary(interps)
    assert "Antibiotic,Drug Class,Status" in csv_text
    assert "Meropenem,Carbapenem,Resistance predicted" in csv_text


def test_friend_demo_mrsa_isolate():
    """Verify analysis of friend's S. aureus MRSA demo benchmark."""
    mrsa_fasta = os.path.join("data", "demo", "staphylococcus_aureus_mrsa.fasta")
    assert os.path.exists(mrsa_fasta)

    result = analyze_genome(
        fasta_path=mrsa_fasta,
        sample_id="SA-MRSA-BENCHMARK",
        organism="Staphylococcus aureus",
    )

    assert result["sample_id"] == "SA-MRSA-BENCHMARK"
    evidence_symbols = [d["gene_symbol"] for d in result["detected_evidence"]]
    assert "mecA" in evidence_symbols

    oxacillin = next(i for i in result["interpretation"] if i["antibiotic"] == "Oxacillin")
    assert oxacillin["status"] == "Resistance predicted"
    assert oxacillin["rule_id"] == "RULE-MRSA-001"


def test_friend_demo_ecoli_multidrug_isolate():
    """Verify analysis of friend's E. coli MDR demo benchmark."""
    ecoli_fasta = os.path.join("data", "demo", "escherichia_coli_multidrug.fasta")
    assert os.path.exists(ecoli_fasta)

    result = analyze_genome(
        fasta_path=ecoli_fasta,
        sample_id="EC-MDR-BENCHMARK",
        organism="Escherichia coli",
    )

    assert result["sample_id"] == "EC-MDR-BENCHMARK"
    evidence_symbols = [d["gene_symbol"] for d in result["detected_evidence"]]
    assert "blaCTX-M-14" in evidence_symbols

    ceftriaxone = next(i for i in result["interpretation"] if i["antibiotic"] == "Ceftriaxone")
    assert ceftriaxone["status"] == "Resistance predicted"
    assert ceftriaxone["rule_id"] == "RULE-ESBL-001"


def test_live_custom_upload_without_detector_honest_reporting(tmp_path):
    """
    Ensure custom uploaded FASTA never silently falls back to mock results
    when the detector is unavailable.
    """
    custom_fasta = tmp_path / "novel_isolate.fasta"
    custom_fasta.write_text(">contig_01\nATGCATGCATGCATGC\n" * 50, encoding="utf-8")

    result = analyze_genome(
        fasta_path=str(custom_fasta),
        sample_id="CUSTOM-NOVEL-01",
        organism="Klebsiella pneumoniae",
        is_demo=False,
    )

    # Must be explicitly marked as not live, with zero detections, and no mock data
    assert result["provenance"]["is_live_analysis"] is False
    assert result["detected_evidence"] == []
    assert len(result["analysis_errors"]) > 0
    assert "unavailable" in result["provenance"]["provenance_notes"].lower()

    # All interpretations must be Indeterminate
    for interp in result["interpretation"]:
        assert interp["status"] == "Indeterminate"
        assert "UNAVAILABLE" in interp["confidence_or_criteria"]


def test_invalid_fasta_handling(tmp_path):
    """Ensure malformed or empty FASTA is rejected with clear ValueError."""
    empty_file = tmp_path / "corrupted.fasta"
    empty_file.write_text("NOT_A_FASTA_HEADER\nATGCATGC", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed FASTA"):
        analyze_genome(
            fasta_path=str(empty_file),
            sample_id="MALFORMED-01",
        )
