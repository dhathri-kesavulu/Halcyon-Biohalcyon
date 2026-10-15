"""Focused automated test suite for Genome Firewall PDF report generation.

These tests use synthetic software fixtures to verify structural correctness,
styling, error handling, escaping, and page generation of the PDF report.
These are software unit/integration tests and do not represent biological validation.
"""

import io
from typing import Any
import pypdf
import pytest

from backend.report import (
    generate_pdf_report,
    create_provenance,
    DISCLAIMER_TEXT,
    LIMITATIONS_TEXT,
    HAS_REPORTLAB,
)


def _synthetic_full_result() -> dict[str, Any]:
    """Synthetic test fixture representing a complete successful analysis."""
    return {
        "sample_id": "SYNTHETIC-SAMPLE-01",
        "organism": "Klebsiella pneumoniae",
        "status": "SUCCESS",
        "errors": [],
        "warnings": ["Low contig N50 (<50,000 bp)"],
        "provenance": create_provenance(
            sample_id="SYNTHETIC-SAMPLE-01",
            input_sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            organism="Klebsiella pneumoniae",
            engine="NCBI AMRFinderPlus (Live)",
            engine_version="3.12.0",
            database_version="2024-05-02.1",
            rules_version="1.0.0",
            is_live=True,
            mode_label="Live AMRFinderPlus Engine Execution",
        ),
        "genome_metrics": {
            "sequence_count": 42,
            "total_length": 5420100,
            "gc_content_pct": 57.35,
            "ambiguous_count": 18,
            "ambiguous_pct": 0.0003,
            "n50": 125000,
            "warnings": ["Low contig N50 (<50,000 bp)"],
        },
        "detections": [
            {
                "gene_symbol": "blaKPC-2",
                "sequence_name": "contig_04",
                "contig_id": "contig_04",
                "class": "BETA-LACTAM",
                "subclass": "CARBAPENEM",
                "method": "BLASTX",
                "identity": 100.0,
                "coverage": 100.0,
                "start": 1200,
                "stop": 2085,
                "strand": "+",
            },
            {
                "gene_symbol": "aac(6')-Ib-cr",
                "sequence_name": "contig_09",
                "contig_id": "contig_09",
                "class": "AMINOGLYCOSIDE",
                "subclass": "AMINOGLYCOSIDE/QUINOLONE",
                "method": "BLASTX",
                "identity": 99.4,
                "coverage": 100.0,
                "start": 3400,
                "stop": 3980,
                "strand": "-",
            },
        ],
        "interpretations": [
            {
                "antibiotic": "Meropenem",
                "drug_class": "Carbapenem",
                "status": "Resistance predicted",
                "rule_id": "RULE-CARB-001",
                "rationale": "High-level carbapenem resistance conferred by acquired blaKPC carbapenemase.",
                "evidence": ["blaKPC-2 (contig_04:1200-2085)"],
                "citations": ["CLSI M100: 2024"],
            },
            {
                "antibiotic": "Ciprofloxacin",
                "drug_class": "Fluoroquinolone",
                "status": "Resistance predicted",
                "rule_id": "RULE-FLQ-002",
                "rationale": "Fluoroquinolone acetyltransferase aac(6')-Ib-cr detected.",
                "evidence": ["aac(6')-Ib-cr (contig_09)"],
                "citations": ["EUCAST: 2021"],
            },
            {
                "antibiotic": "Colistin",
                "drug_class": "Polymyxin",
                "status": "Indeterminate",
                "rule_id": "RULE-INDET-001",
                "rationale": "No acquired mcr genes detected, but chromosomal pmrAB/mgrB mutations cannot be ruled out.",
                "evidence": [],
                "citations": ["EUCAST: 2021"],
            },
        ],
        "summary": {
            "total_antibiotics_evaluated": 3,
            "resistant_count": 2,
            "susceptible_count": 0,
            "indeterminate_count": 1,
        },
        "disclaimer": DISCLAIMER_TEXT,
        "limitations": LIMITATIONS_TEXT.split("\n"),
    }


def test_pdf_reportlab_is_available():
    """Verify reportlab is properly installed and detected."""
    assert HAS_REPORTLAB is True


def test_pdf_valid_result_signature_and_bytes():
    """Verify that a valid result produces non-empty bytes with the %PDF- signature."""
    payload = _synthetic_full_result()
    pdf_bytes = generate_pdf_report(payload)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF-")


def test_pdf_parsing_and_expected_fields():
    """Parse generated PDF with pypdf to verify core metadata and sections are present."""
    payload = _synthetic_full_result()
    pdf_bytes = generate_pdf_report(payload)

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1

    full_text = "\n".join([page.extract_text() for page in reader.pages])

    # Core titles and disclaimers
    assert "Genome Firewall" in full_text
    assert "Antibiotic Resistance Analysis" in full_text
    assert "RESEARCH USE ONLY" in full_text
    assert "CLINICAL & REGULATORY NOTICE" in full_text

    # Sample metadata & provenance
    assert "SYNTHETIC-SAMPLE-01" in full_text
    assert "Klebsiella pneumoniae" in full_text
    assert "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"[:16] in full_text
    assert "LIVE EXECUTION (NCBI AMRFinderPlus Active)" in full_text

    # Assembly metrics
    assert "5,420,100 bp" in full_text
    assert "57.35%" in full_text
    assert "Low contig N50" in full_text

    # Detected findings & interpretations
    assert "blaKPC-2" in full_text
    assert "aac(6')-Ib-cr" in full_text
    assert "Meropenem" in full_text
    assert "Resistance predicted" in full_text
    assert "Indeterminate" in full_text

    # Limitations & references
    assert "Biological & Algorithmic Limitations:" in full_text
    assert "CLSI" in full_text
    assert "EUCAST" in full_text


def test_pdf_all_three_statuses_render():
    """Verify that Resistance predicted, Susceptibility predicted, and Indeterminate all render."""
    payload = _synthetic_full_result()
    payload["interpretations"] = [
        {
            "antibiotic": "Meropenem",
            "drug_class": "Carbapenem",
            "status": "Resistance predicted",
            "rule_id": "RULE-001",
            "rationale": "blaKPC-2 present",
            "evidence": ["blaKPC-2"],
        },
        {
            "antibiotic": "Amikacin",
            "drug_class": "Aminoglycoside",
            "status": "Susceptibility predicted",
            "rule_id": "RULE-002",
            "rationale": "Species intrinsically susceptible; no aminoglycoside modifying enzymes detected.",
            "evidence": [],
        },
        {
            "antibiotic": "Colistin",
            "drug_class": "Polymyxin",
            "status": "Indeterminate",
            "rule_id": "RULE-003",
            "rationale": "Chromosomal efflux/LPS modifications unverified.",
            "evidence": [],
        },
    ]

    pdf_bytes = generate_pdf_report(payload)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join([page.extract_text() for page in reader.pages])

    assert "Resistance predicted" in full_text
    assert "Susceptibility predicted" in full_text
    assert "Indeterminate" in full_text


def test_pdf_missing_optional_fields_no_crash():
    """Defensive test: minimal / missing optional fields must not crash generation."""
    minimal_payload = {
        "sample_id": "MINIMAL-01",
    }
    pdf_bytes = generate_pdf_report(minimal_payload)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join([page.extract_text() for page in reader.pages])
    assert "MINIMAL-01" in full_text
    assert "Not recorded" in full_text or "Not available" in full_text or "Not specified" in full_text


def test_pdf_empty_findings_no_fabricated_susceptibility():
    """Verify that when detections are empty, no fake susceptibility or genes are shown."""
    payload = _synthetic_full_result()
    payload["detections"] = []
    payload["interpretations"] = [
        {
            "antibiotic": "Meropenem",
            "drug_class": "Carbapenem",
            "status": "Indeterminate",
            "rule_id": "RULE-INDET-001",
            "rationale": "No acquired carbapenemase genes detected; phenotypic AST required.",
            "evidence": [],
        }
    ]
    payload["summary"] = {
        "total_antibiotics_evaluated": 1,
        "resistant_count": 0,
        "susceptible_count": 0,
        "indeterminate_count": 1,
    }

    pdf_bytes = generate_pdf_report(payload)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join([page.extract_text() for page in reader.pages])

    assert "No acquired AMR determinants or verified resistance mutations detected" in full_text
    assert "Susceptibility predicted: 0" in full_text
    assert "Resistance predicted: 0" in full_text
    assert "Indeterminate: 1" in full_text
    assert "Indeterminate" in full_text


def test_pdf_demo_precomputed_mode_clearly_labelled():
    """Verify precomputed demo results are clearly labelled as demonstration fixture."""
    payload = _synthetic_full_result()
    payload["provenance"]["is_live"] = False
    payload["provenance"]["is_live_analysis"] = False
    payload["provenance"]["mode_label"] = "Precomputed Benchmark Fixture (Offline)"

    pdf_bytes = generate_pdf_report(payload)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join([page.extract_text() for page in reader.pages])

    assert "DEMONSTRATION FIXTURE MODE" in full_text
    assert "Precomputed Reference Data" in full_text
    assert "LIVE EXECUTION (NCBI AMRFinderPlus Active)" not in full_text


def test_pdf_failed_analysis_cannot_generate_misleading_successful_report():
    """Failed execution must clearly display failure banner and error messages."""
    payload = _synthetic_full_result()
    payload["status"] = "FAILED"
    payload["errors"] = ["AMRFinderPlus timed out after 120s", "Subprocess exit code 124"]

    pdf_bytes = generate_pdf_report(payload)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join([page.extract_text() for page in reader.pages])

    assert "ANALYSIS EXECUTION FAILED" in full_text
    assert "AMRFinderPlus timed out after 120s" in full_text
    assert "LIVE EXECUTION (NCBI AMRFinderPlus Active)" not in full_text


def test_pdf_special_characters_and_xml_escaping():
    """Special characters (<, >, &, \", ') must be escaped safely without crashing ReportLab."""
    payload = _synthetic_full_result()
    payload["sample_id"] = "SAMPLE<XSS>&'TEST\""
    payload["organism"] = "Bacterium <sp. & strain>"
    payload["interpretations"] = [
        {
            "antibiotic": "Beta-Lactam <A&B>",
            "drug_class": "Class <1 & 2>",
            "status": "Resistance predicted",
            "rule_id": "RULE<001>&'2'",
            "rationale": "Detected identity > 99.5% & coverage <= 100.0% in <contig_1>.",
            "evidence": ["blaTEM-1 <variant & mutant>"],
        }
    ]

    pdf_bytes = generate_pdf_report(payload)
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "\n".join([page.extract_text() for page in reader.pages])
    assert "SAMPLE<XSS>" in full_text
    assert "identity > 99.5%" in full_text


def test_pdf_long_explanations_and_many_findings_multi_page():
    """A large panel with 20+ findings and long text must gracefully paginate across pages."""
    payload = _synthetic_full_result()

    # Generate 25 findings
    many_detections = []
    for i in range(25):
        many_detections.append({
            "gene_symbol": f"testGene_{i:02d}",
            "sequence_name": f"contig_{i:02d}",
            "contig_id": f"contig_{i:02d}",
            "class": "MULTIDRUG",
            "subclass": "EFFLUX",
            "method": "BLASTX",
            "identity": 98.5,
            "coverage": 95.0,
            "start": 1000 * i,
            "stop": 1000 * i + 850,
            "strand": "+" if i % 2 == 0 else "-",
        })
    payload["detections"] = many_detections

    # Generate 20 antibiotic interpretations with long text
    long_interps = []
    for i in range(20):
        long_interps.append({
            "antibiotic": f"Antibiotic-{i:02d}",
            "drug_class": "Synthetic Class",
            "status": "Resistance predicted" if i % 2 == 0 else "Indeterminate",
            "rule_id": f"RULE-SYNTH-{i:03d}",
            "rationale": (
                f"Detailed mechanistical explanation for test antibiotic {i}: "
                "conferred by multi-gene efflux pump overexpression and regulatory mutations. "
                "This requires thorough clinical correlation and laboratory phenotypic testing."
            ),
            "evidence": [f"testGene_{i:02d}"],
        })
    payload["interpretations"] = long_interps

    pdf_bytes = generate_pdf_report(payload)
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))

    # Must span multiple pages
    assert len(reader.pages) >= 2

    # Check page 2 text contains running headers and content
    p2_text = reader.pages[1].extract_text()
    assert "Genome Firewall" in p2_text or "Page 2" in p2_text or "Antibiotic-" in p2_text


def test_pdf_reproducible_and_reflects_supplied_result():
    """Verify that different input results produce distinct reports reflecting their own data."""
    payload_a = _synthetic_full_result()
    payload_a["sample_id"] = "SAMPLE-ALPHA-999"
    payload_a["detections"] = [{"gene_symbol": "blaNDM-1", "sequence_name": "contig_A"}]

    payload_b = _synthetic_full_result()
    payload_b["sample_id"] = "SAMPLE-BETA-777"
    payload_b["detections"] = [{"gene_symbol": "vanA", "sequence_name": "contig_B"}]

    pdf_a = generate_pdf_report(payload_a)
    pdf_b = generate_pdf_report(payload_b)

    reader_a = pypdf.PdfReader(io.BytesIO(pdf_a))
    reader_b = pypdf.PdfReader(io.BytesIO(pdf_b))

    text_a = "\n".join([p.extract_text() for p in reader_a.pages])
    text_b = "\n".join([p.extract_text() for p in reader_b.pages])

    assert "SAMPLE-ALPHA-999" in text_a
    assert "blaNDM-1" in text_a
    assert "SAMPLE-BETA-777" not in text_a
    assert "vanA" not in text_a

    assert "SAMPLE-BETA-777" in text_b
    assert "vanA" in text_b
    assert "SAMPLE-ALPHA-999" not in text_b
    assert "blaNDM-1" not in text_b
