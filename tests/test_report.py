"""Tests for audit report generation in JSON, Markdown, and CSV formats."""

import csv
import io
import json
from backend.report import (
    create_provenance,
    generate_json_report,
    generate_markdown_report,
    generate_csv_report,
    DISCLAIMER_TEXT,
)


def _mock_analysis_result():
    return {
        "status": "SUCCESS",
        "errors": [],
        "warnings": [],
        "provenance": create_provenance(
            sample_id="SAMPLE-TEST-01",
            input_sha256="a" * 64,
            organism="Klebsiella pneumoniae",
            engine="NCBI AMRFinderPlus (Live)",
            engine_version="3.12.0",
            database_version="2024-05-02.1",
            rules_version="1.0.0",
            is_live=True,
            mode_label="Live AMRFinderPlus Engine Execution",
        ),
        "genome_metrics": {
            "sequence_count": 10,
            "total_length": 5200000,
            "gc_content_pct": 57.2,
            "ambiguous_count": 12,
            "ambiguous_pct": 0.0,
            "n50": 500000,
            "warnings": [],
        },
        "detections": [
            {
                "gene_symbol": "blaKPC-2",
                "sequence_name": "contig_1",
                "class": "BETA-LACTAM",
                "subclass": "CARBAPENEM",
                "method": "BLASTX",
                "identity": 100.0,
                "coverage": 100.0,
            }
        ],
        "interpretations": [
            {
                "antibiotic": "Meropenem",
                "drug_class": "Carbapenem",
                "status": "Resistance predicted",
                "rationale": "blaKPC-2 detected",
                "evidence": ["blaKPC-2 (contig_1)"],
                "rule_id": "RULE-CARB-001",
                "citations": ["CLSI M100: 2024"],
            }
        ],
        "summary": {
            "total_antibiotics_evaluated": 1,
            "resistant_count": 1,
            "susceptible_count": 0,
            "indeterminate_count": 0,
        },
        "disclaimer": DISCLAIMER_TEXT,
    }


def test_generate_json_report():
    res = _mock_analysis_result()
    json_str = generate_json_report(res)
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)

    assert parsed["provenance"]["sample_id"] == "SAMPLE-TEST-01"
    assert parsed["provenance"]["input_sha256"] == "a" * 64
    assert "limitations" in parsed
    assert len(parsed["limitations"]) > 0
    assert parsed["summary"]["resistant_count"] == 1


def test_generate_csv_report():
    res = _mock_analysis_result()
    csv_str = generate_csv_report(res)
    assert isinstance(csv_str, str)

    reader = csv.DictReader(io.StringIO(csv_str))
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["Sample_ID"] == "SAMPLE-TEST-01"
    assert row["Antibiotic"] == "Meropenem"
    assert row["Status"] == "Resistance predicted"
    assert row["Rule_ID"] == "RULE-CARB-001"
    assert row["Is_Live"] == "True"


def test_generate_markdown_report():
    res = _mock_analysis_result()
    md_str = generate_markdown_report(res)
    assert "# Genome Firewall" in md_str
    assert "SAMPLE-TEST-01" in md_str
    assert "Meropenem" in md_str
    assert "RESEARCH USE ONLY" in md_str
    assert "Limitations" in md_str
