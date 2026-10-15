"""End-to-end integration tests for analyze_genome pipeline and schema consistency."""

import json
import os
import pytest
from backend.pipeline import analyze_genome
from backend.report import DISCLAIMER_TEXT


def test_analyze_genome_demo_mode_contract():
    """Verify schema contract on successful demo analysis."""
    demo_fasta = os.path.join("data", "demo", "klebsiella_pneumoniae_kpc2_demo.fasta")
    res = analyze_genome(
        fasta_path=demo_fasta,
        sample_id="KP-ST258-01",
        organism="Klebsiella pneumoniae",
        is_demo=True,
    )

    # Top-level required keys
    required_keys = [
        "status", "errors", "warnings", "provenance", "genome_metrics",
        "detections", "interpretations", "summary", "limitations", "reports", "disclaimer"
    ]
    for k in required_keys:
        assert k in res, f"Missing key in response: {k}"

    assert res["status"] == "SUCCESS"
    assert res["errors"] == []
    assert res["disclaimer"] == DISCLAIMER_TEXT

    # Provenance fields contract
    prov = res["provenance"]
    expected_prov = [
        "sample_id", "input_sha256", "organism", "engine", "engine_version",
        "database_version", "rules_version", "is_live", "mode_label", "timestamp_utc"
    ]
    for field in expected_prov:
        assert field in prov, f"Missing provenance field: {field}"

    assert len(prov["input_sha256"]) == 64
    assert prov["is_live"] is False
    assert "Precomputed" in prov["mode_label"]

    # Summary counts consistency
    summary = res["summary"]
    total = summary["total_antibiotics_evaluated"]
    assert total == summary["resistant_count"] + summary["susceptible_count"] + summary["indeterminate_count"]
    assert total == len(res["interpretations"])


def test_analyze_genome_live_mode_engine_unavailable(tmp_path):
    """
    When live analysis is invoked for a custom FASTA and the engine is missing,
    the pipeline returns status='UNAVAILABLE' with stable schema, populated errors,
    and all interpretations set to Indeterminate.
    """
    f = tmp_path / "custom_isolate.fasta"
    f.write_text(">c1\nATGCATGCATGCATGC\n" * 50, encoding="utf-8")

    # In this environment, AMRFinderPlus is not installed
    res = analyze_genome(
        fasta_path=str(f),
        sample_id="CUSTOM-01",
        organism="Klebsiella pneumoniae",
        is_demo=False,
    )

    # Stable schema must still hold
    assert res["status"] == "UNAVAILABLE"
    assert len(res["errors"]) > 0
    assert res["detections"] == []
    assert res["provenance"]["is_live"] is False
    assert "unavailable" in res["provenance"]["mode_label"].lower()

    # All interpretations must be Indeterminate
    assert len(res["interpretations"]) > 0
    for interp in res["interpretations"]:
        assert interp["status"] == "Indeterminate"
        assert "UNAVAILABLE" in interp["rationale"]

    assert res["summary"]["indeterminate_count"] == len(res["interpretations"])
    assert res["summary"]["resistant_count"] == 0
    assert res["summary"]["susceptible_count"] == 0


def test_analyze_genome_reports_consistency():
    demo_fasta = os.path.join("data", "demo", "escherichia_coli_ctxm14_demo.fasta")
    res = analyze_genome(
        fasta_path=demo_fasta,
        sample_id="EC-ST131-TEST",
        organism="Escherichia coli",
        is_demo=True,
    )

    reports = res["reports"]
    assert "json" in reports
    assert "markdown" in reports
    assert "csv" in reports

    # Parse json report
    parsed_json = json.loads(reports["json"])
    assert parsed_json["status"] == "SUCCESS"
    assert parsed_json["provenance"]["sample_id"] == "EC-ST131-TEST"

    # Markdown contains disclaimer and table
    assert "# Genome Firewall" in reports["markdown"]
    assert "RESEARCH USE ONLY" in reports["markdown"]

    # CSV contains table rows
    assert "Sample_ID,Organism,Antibiotic" in reports["csv"]
    assert "EC-ST131-TEST" in reports["csv"]
