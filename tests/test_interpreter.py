"""Tests for interpreter rules table, citations, conflict handling, and strict status outputs."""

import pytest
from backend.interpreter import (
    interpret_evidence,
    get_documented_rules,
    ANTIBIOTIC_PANEL,
)


def test_strict_three_status_enforcement():
    """Verify that every single antibiotic strictly receives one of the 3 allowed statuses."""
    detections = [
        {
            "gene_symbol": "blaKPC-2",
            "sequence_name": "c1",
            "scope": "core",
            "element_type": "AMR",
            "element_subtype": "BETA-LACTAM",
            "class": "BETA-LACTAM",
            "subclass": "CARBAPENEM",
            "method": "BLASTX",
            "identity": 100.0,
            "coverage": 100.0,
        }
    ]
    interps = interpret_evidence(detections, "Klebsiella pneumoniae", {"warnings": []})

    allowed = {"Resistance predicted", "Susceptibility predicted", "Indeterminate"}
    assert len(interps) == len(ANTIBIOTIC_PANEL)
    for item in interps:
        assert item["status"] in allowed
        assert "citations" in item
        assert len(item["citations"]) > 0


def test_missing_evidence_does_not_imply_susceptibility_for_unsupported_species():
    """Uncharacterized species must NEVER receive Susceptibility predicted."""
    empty_detections = []
    interps = interpret_evidence(empty_detections, "Environmental soil isolate", {"warnings": []})

    for item in interps:
        assert item["status"] != "Susceptibility predicted", (
            f"Antibiotic {item['antibiotic']} incorrectly predicted susceptible for an unknown species!"
        )


def test_colistin_negative_is_indeterminate():
    """Absence of mcr gene must result in Indeterminate for colistin."""
    empty_detections = []
    interps = interpret_evidence(empty_detections, "Klebsiella pneumoniae", {"warnings": []})
    colistin = next(i for i in interps if i["antibiotic"] == "Colistin")
    assert colistin["status"] == "Indeterminate"
    assert "chromosomal regulatory mutations" in colistin["rationale"]


def test_conservative_conflict_handling_borderline_evidence():
    """
    Borderline hit (<90% identity or <80% coverage) must not be called resistant,
    but MUST prevent susceptibility prediction (conflict/borderline -> Indeterminate).
    """
    borderline_kpc = [
        {
            "gene_symbol": "blaKPC-2",
            "sequence_name": "c1",
            "scope": "core",
            "element_type": "AMR",
            "element_subtype": "BETA-LACTAM",
            "class": "BETA-LACTAM",
            "subclass": "CARBAPENEM",
            "method": "BLASTX",
            "identity": 75.0,  # Below 90% threshold
            "coverage": 60.0,  # Below 80% threshold
        }
    ]
    interps = interpret_evidence(borderline_kpc, "Klebsiella pneumoniae", {"warnings": []})
    meropenem = next(i for i in interps if i["antibiotic"] == "Meropenem")

    assert meropenem["status"] == "Indeterminate"
    assert "borderline" in meropenem["rationale"].lower() or "conflicting" in meropenem["rationale"].lower()


def test_carbapenemase_confers_carbapenem_resistance():
    detections = [
        {
            "gene_symbol": "blaNDM-1",
            "sequence_name": "c1",
            "scope": "core",
            "element_type": "AMR",
            "element_subtype": "BETA-LACTAM",
            "class": "BETA-LACTAM",
            "subclass": "CARBAPENEM",
            "method": "BLASTX",
            "identity": 100.0,
            "coverage": 100.0,
        }
    ]
    interps = interpret_evidence(detections, "Klebsiella pneumoniae", {"warnings": []})
    meropenem = next(i for i in interps if i["antibiotic"] == "Meropenem")
    imipenem = next(i for i in interps if i["antibiotic"] == "Imipenem")
    ertapenem = next(i for i in interps if i["antibiotic"] == "Ertapenem")

    assert meropenem["status"] == "Resistance predicted"
    assert imipenem["status"] == "Resistance predicted"
    assert ertapenem["status"] == "Resistance predicted"
    assert meropenem["rule_id"] == "RULE-CARB-001"


def test_mrsa_mecA_confers_oxacillin_cefoxitin_resistance():
    detections = [
        {
            "gene_symbol": "mecA",
            "sequence_name": "c2",
            "scope": "core",
            "element_type": "AMR",
            "element_subtype": "BETA-LACTAM",
            "class": "BETA-LACTAM",
            "subclass": "METHICILLIN",
            "method": "BLASTX",
            "identity": 100.0,
            "coverage": 100.0,
        }
    ]
    interps = interpret_evidence(detections, "Staphylococcus aureus", {"warnings": []})
    oxacillin = next(i for i in interps if i["antibiotic"] == "Oxacillin")
    cefoxitin = next(i for i in interps if i["antibiotic"] == "Cefoxitin")

    assert oxacillin["status"] == "Resistance predicted"
    assert cefoxitin["status"] == "Resistance predicted"
    assert oxacillin["rule_id"] == "RULE-MRSA-001"


def test_assembly_warnings_prevent_susceptibility_inference():
    """Assembly QC warnings must force negative findings into Indeterminate."""
    empty_detections = []
    metrics = {"warnings": ["High N-base proportion", "Short fragmented contigs"]}
    interps = interpret_evidence(empty_detections, "Escherichia coli", metrics)

    for item in interps:
        assert item["status"] in ["Indeterminate", "Resistance predicted"]
        assert item["status"] != "Susceptibility predicted"


def test_auditable_rules_table_has_citations_and_scopes():
    rules = get_documented_rules()
    assert len(rules) >= 10
    for rule in rules:
        assert "rule_id" in rule
        assert "citations" in rule
        assert len(rule["citations"]) > 0
        assert "supported_organisms" in rule
        assert "evidence_requirements" in rule
