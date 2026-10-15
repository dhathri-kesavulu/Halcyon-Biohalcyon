"""Public entrypoint and orchestrator for Genome Firewall analysis.

Public Contract:
    analyze_genome(
        fasta_path: str,
        sample_id: str,
        organism: str | None = None,
        is_demo: bool = False,
        demo_id: str | None = None,
    ) -> dict[str, Any]

Schema Guarantees:
- Separates overall execution status ('SUCCESS', 'UNAVAILABLE', 'FAILED')
  from each antibiotic's interpretation status ('Resistance predicted', 'Susceptibility predicted', 'Indeterminate').
- Stable response shape across success, detection engine unavailability, and tool failures.
- Preserves complete provenance (SHA-256, engine, DB, rules version, timestamp, execution mode).
- Precomputed demonstration fixtures are isolated and never substituted during live analysis.
"""

import os
from typing import Any

from backend.detector import (
    run_detection,
    verify_amrfinder_engine,
    DetectionEngineUnavailableError,
)
from backend.genome import calculate_sha256, parse_genome_fasta
from backend.interpreter import (
    interpret_evidence,
    RULES_VERSION,
    ANTIBIOTIC_PANEL,
    CITATIONS,
)
from backend.report import (
    create_provenance,
    generate_json_report,
    generate_markdown_report,
    generate_csv_report,
    DISCLAIMER_TEXT,
    LIMITATIONS_TEXT,
)


def _build_fallback_interpretations(rationale_msg: str) -> list[dict[str, Any]]:
    """Build standardized Indeterminate interpretations when detection engine cannot execute."""
    fallback_list: list[dict[str, Any]] = []
    for drug in ANTIBIOTIC_PANEL:
        fallback_list.append({
            "antibiotic": drug["name"],
            "drug_class": drug["class"],
            "status": "Indeterminate",
            "rationale": rationale_msg,
            "confidence_or_criteria": rationale_msg,
            "evidence": ["No detector evidence available"],
            "evidence_genes": [],
            "rule_id": "RULE-INDET-001",
            "citations": [CITATIONS["CLSI_M100"]],
        })
    return fallback_list


def analyze_genome(
    fasta_path: str,
    sample_id: str,
    organism: str | None = None,
    is_demo: bool = False,
    demo_id: str | None = None,
) -> dict[str, Any]:
    """
    Public API to analyze an assembled bacterial genome for AMR determinants and predictions.

    Args:
        fasta_path: Absolute or relative path to FASTA/FA/FNA file.
        sample_id: User-provided or generated sample identifier.
        organism: Optional species name (e.g. 'Klebsiella pneumoniae', 'Escherichia coli').
        is_demo: Explicit flag to run against precomputed benchmark fixtures.
        demo_id: Optional identifier of the benchmark demo isolate.

    Returns:
        Structured result dictionary strictly adhering to the Genome Firewall schema.
    """
    if not fasta_path or not os.path.exists(fasta_path):
        raise FileNotFoundError(f"Input genome file not found: {fasta_path}")

    sample_id = (sample_id or "UNKNOWN-SAMPLE").strip()

    # 1. Compute input file SHA-256 for cryptographic provenance
    sha256_hash = calculate_sha256(fasta_path)

    # 2. Genome Assembly Inspection & QC (raises ValueError on empty/malformed/non-nucleotide files)
    genome_metrics = parse_genome_fasta(fasta_path)

    # 3. Determine if demo mode is explicitly enabled
    # Allows explicit parameter or vetted path within demo fixtures folder
    norm_path = os.path.normpath(fasta_path)
    is_vetted_demo_path = os.path.join("data", "demo") in norm_path or "data/demo" in fasta_path.replace("\\", "/")
    effective_is_demo = is_demo or (demo_id is not None) or is_vetted_demo_path

    # 4. Run Detection Engine
    detection_res = run_detection(
        fasta_path=fasta_path,
        sha256_hash=sha256_hash,
        organism=organism,
        is_demo=effective_is_demo,
        demo_id=demo_id,
    )

    execution_status = detection_res.get("status", "FAILED")
    errors: list[str] = []
    if detection_res.get("error"):
        errors.append(detection_res["error"])

    detections = detection_res.get("detections", [])

    # 5. Interpretation logic based on execution status
    if execution_status == "SUCCESS":
        interpretations = interpret_evidence(
            detections=detections,
            organism=organism,
            genome_metrics=genome_metrics,
        )
    elif execution_status == "UNAVAILABLE":
        interpretations = _build_fallback_interpretations(
            f"Execution status: UNAVAILABLE. {detection_res.get('error', 'Live AMRFinderPlus is not available.')}"
        )
    else:  # FAILED
        interpretations = _build_fallback_interpretations(
            f"Execution status: FAILED. {detection_res.get('error', 'AMR detection failed.')}"
        )

    # 6. Summary metrics
    resistant_count = sum(1 for i in interpretations if i["status"] == "Resistance predicted")
    susceptible_count = sum(1 for i in interpretations if i["status"] == "Susceptibility predicted")
    indeterminate_count = sum(1 for i in interpretations if i["status"] == "Indeterminate")

    summary = {
        "total_antibiotics_evaluated": len(interpretations),
        "resistant_count": resistant_count,
        "susceptible_count": susceptible_count,
        "indeterminate_count": indeterminate_count,
    }

    # 7. Complete Provenance Record
    provenance = create_provenance(
        sample_id=sample_id,
        input_sha256=sha256_hash,
        organism=organism,
        engine=detection_res.get("engine", "NCBI AMRFinderPlus"),
        engine_version=detection_res.get("engine_version"),
        database_version=detection_res.get("database_version"),
        rules_version=RULES_VERSION,
        is_live=detection_res.get("is_live", False),
        mode_label=detection_res.get("mode_label", "Unknown Mode"),
    )

    # Normalize detection fields for contig_id/sequence_name and coordinates
    for d in detections:
        seq = d.get("sequence_name") or d.get("contig_id") or "contig_01"
        d["sequence_name"] = seq
        d["contig_id"] = seq
        d["start"] = d.get("start", 0)
        d["stop"] = d.get("stop", 0)
        d["strand"] = d.get("strand", "+")

    # Compatibility aliases in genome_metrics
    genome_metrics["total_length_bp"] = genome_metrics.get("total_length", 0)
    genome_metrics["n50_bp"] = genome_metrics.get("n50", 0)
    genome_metrics["min_length_bp"] = genome_metrics.get("min_length", 0)
    genome_metrics["max_length_bp"] = genome_metrics.get("max_length", 0)

    result_payload: dict[str, Any] = {
        "sample_id": sample_id,
        "organism": organism or "Not specified",
        "status": execution_status,
        "errors": errors,
        "analysis_errors": errors,
        "warnings": list(genome_metrics.get("warnings", [])),
        "provenance": provenance,
        "genome_metrics": genome_metrics,
        "detections": detections,
        "detected_evidence": detections,
        "interpretations": interpretations,
        "interpretation": interpretations,
        "summary": summary,
        "limitations": LIMITATIONS_TEXT.split("\n"),
        "disclaimer": DISCLAIMER_TEXT,
        "disclaimers": [DISCLAIMER_TEXT] + LIMITATIONS_TEXT.split("\n"),
    }

    # 8. Attach pre-rendered export reports
    result_payload["reports"] = {
        "json": generate_json_report(result_payload),
        "markdown": generate_markdown_report(result_payload),
        "csv": generate_csv_report(result_payload),
    }

    return result_payload
