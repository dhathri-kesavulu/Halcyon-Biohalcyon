"""Tests for detector verification, unavailable status, explicit demo mode, and TSV parsing."""

import os
import tempfile
import pytest
from backend.detector import (
    verify_amrfinder_engine,
    run_detection,
    _parse_amrfinder_tsv,
)
from backend.genome import calculate_sha256


def test_verify_amrfinder_engine_structure():
    status = verify_amrfinder_engine()
    assert isinstance(status, dict)
    assert "is_available" in status
    assert "status_message" in status
    assert "supported_options" in status
    assert isinstance(status["is_available"], bool)


def test_live_analysis_when_engine_missing_returns_unavailable():
    """
    During live analysis (is_demo=False), if AMRFinderPlus is missing,
    it must return status='UNAVAILABLE' and NEVER silently substitute a demo fixture.
    """
    engine_status = verify_amrfinder_engine()
    if not engine_status["is_available"]:
        demo_fasta = os.path.join("data", "demo", "klebsiella_pneumoniae_kpc2_demo.fasta")
        sha = calculate_sha256(demo_fasta)

        # Calling with is_demo=False (default)
        result = run_detection(
            fasta_path=demo_fasta,
            sha256_hash=sha,
            organism="Klebsiella pneumoniae",
            is_demo=False,
        )

        assert result["status"] == "UNAVAILABLE"
        assert result["is_live"] is False
        assert result["detections"] == []
        assert "executable ('amrfinder') was not found" in result["error"] or "database" in result["error"]
        assert "Live Detection Engine Unavailable" in result["mode_label"]


def test_explicit_demo_mode_returns_precomputed_fixture():
    """When is_demo=True, precomputed fixtures are returned and explicitly labeled."""
    demo_fasta = os.path.join("data", "demo", "klebsiella_pneumoniae_kpc2_demo.fasta")
    assert os.path.exists(demo_fasta)
    sha = calculate_sha256(demo_fasta)

    result = run_detection(
        fasta_path=demo_fasta,
        sha256_hash=sha,
        organism="Klebsiella pneumoniae",
        is_demo=True,
    )

    assert result["status"] == "SUCCESS"
    assert result["is_live"] is False
    assert "Precomputed" in result["mode_label"]
    assert len(result["detections"]) > 0

    # Verify normalized detections and raw_evidence retention
    first_det = result["detections"][0]
    assert "gene_symbol" in first_det
    assert "identity" in first_det
    assert "coverage" in first_det
    assert "raw_evidence" in first_det


def test_explicit_demo_mode_unmatched_returns_failed():
    """When is_demo=True but no fixture matches, returns status='FAILED'."""
    result = run_detection(
        fasta_path="non_existent_isolate.fasta",
        sha256_hash="0000000000000000000000000000000000000000000000000000000000000000",
        organism="Unknown",
        is_demo=True,
    )

    assert result["status"] == "FAILED"
    assert result["is_live"] is False
    assert result["detections"] == []
    assert "does not match any registered demo fixture" in result["error"]


def test_parse_amrfinder_tsv_empty(tmp_path):
    """Empty TSV file or header-only TSV produces empty detections."""
    tsv = tmp_path / "empty.tsv"
    tsv.write_text(
        "Contig id\tStart\tStop\tStrand\tGene symbol\tSequence name\tScope\tElement type\tElement subtype\tClass\tSubclass\tMethod\tTarget length\tReference sequence length\t% Identity to reference sequence\t% Coverage of reference sequence\tAlignment length\tAccession of closest sequence\tName of closest sequence\tHMM id\tHMM description\n",
        encoding="utf-8"
    )
    detections = _parse_amrfinder_tsv(str(tsv))
    assert detections == []


def test_parse_amrfinder_tsv_with_hits(tmp_path):
    """Test TSV parsing into normalized format with retained raw evidence."""
    tsv = tmp_path / "hits.tsv"
    tsv.write_text(
        "Contig id\tStart\tStop\tStrand\tGene symbol\tSequence name\tScope\tElement type\tElement subtype\tClass\tSubclass\tMethod\tTarget length\tReference sequence length\t% Identity to reference sequence\t% Coverage of reference sequence\tAlignment length\tAccession of closest sequence\tName of closest sequence\tHMM id\tHMM description\n"
        "contig_1\t100\t980\t+\tblaKPC-2\tblaKPC-2\tcore\tAMR\tAMR\tBETA-LACTAM\tCARBAPENEM\tBLASTX\t882\t882\t100.00\t100.00\t882\tNG_049253.1\tblaKPC-2\t\t\n",
        encoding="utf-8"
    )
    detections = _parse_amrfinder_tsv(str(tsv))
    assert len(detections) == 1
    d = detections[0]
    assert d["gene_symbol"] == "blaKPC-2"
    assert d["sequence_name"] == "contig_1"
    assert d["class"] == "BETA-LACTAM"
    assert d["subclass"] == "CARBAPENEM"
    assert d["identity"] == 100.0
    assert d["coverage"] == 100.0
    assert "raw_evidence" in d
    assert d["raw_evidence"]["accession"] == "NG_049253.1"
