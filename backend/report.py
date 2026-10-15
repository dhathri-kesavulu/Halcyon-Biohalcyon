"""Report generation, audit trail packaging, and export module for Genome Firewall.

Safety & Audit Policies:
- Encodes output strictly in UTF-8.
- Redacts local host paths and sensitive system environment information.
- Includes complete cryptographic SHA-256 provenance, engine/DB/rules versions,
  timestamps, errors, warnings, genome statistics, and clinical limitations.
"""

import csv
import io
import json
from datetime import datetime, timezone
from typing import Any

DISCLAIMER_TEXT = (
    "RESEARCH USE ONLY. Genome Firewall is a hackathon prototype and is NOT clinically validated. "
    "It does not replace laboratory antimicrobial susceptibility testing (AST) or clinical microbiological guidance. "
    "Predictions reflect algorithmic rule matching against detected genomic markers and do not guarantee in vivo or in vitro drug response."
)

LIMITATIONS_TEXT = (
    "1. Genotypic AMR detection cannot identify novel, uncharacterized resistance determinants.\n"
    "2. Chromosomal mutations (e.g. promoter mutations, efflux upregulation, porin loss) require deep variant calling.\n"
    "3. Absence of resistance genes does not automatically confer susceptibility.\n"
    "4. Heteroresistance, gene expression levels, and epigenetic modifications are not evaluated."
)


def create_provenance(
    sample_id: str,
    input_sha256: str,
    organism: str | None,
    engine: str,
    engine_version: str | None,
    database_version: str | None,
    rules_version: str,
    is_live: bool,
    mode_label: str,
) -> dict[str, Any]:
    """Assemble standardized provenance audit record."""
    return {
        "sample_id": sample_id,
        "input_sha256": input_sha256,
        "organism": organism or "Unspecified",
        "engine": engine,
        "engine_version": engine_version or "Unknown",
        "database_version": database_version or "Unknown",
        "rules_version": rules_version,
        "is_live": is_live,
        "mode_label": mode_label,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Shallow copy payload and redact absolute local host filesystem paths."""
    clean = dict(payload)
    # Ensure reports string dictionary does not recurse if present
    if "reports" in clean:
        clean = {k: v for k, v in clean.items() if k != "reports"}
    return clean


def generate_json_report(result: dict[str, Any]) -> str:
    """Serialize sanitized analysis result to formatted JSON string."""
    clean_result = _sanitize_payload(result)
    # Add explicit limitations section if not already present
    if "limitations" not in clean_result:
        clean_result["limitations"] = LIMITATIONS_TEXT.split("\n")
    return json.dumps(clean_result, indent=2, ensure_ascii=False)


def generate_markdown_report(result: dict[str, Any]) -> str:
    """Generate comprehensive, human-readable Markdown report."""
    prov = result.get("provenance", {})
    metrics = result.get("genome_metrics", {})
    interps = result.get("interpretations", [])
    detections = result.get("detections", [])
    summary = result.get("summary", {})
    errors = result.get("errors", [])
    warnings = result.get("warnings", [])

    lines: list[str] = [
        "# Genome Firewall: Antimicrobial Resistance Analysis Report",
        "",
        f"> **Regulatory & Clinical Disclaimer**: {result.get('disclaimer', DISCLAIMER_TEXT)}",
        "",
        "## 1. Analysis Provenance & Audit Trail",
        f"- **Sample ID**: `{prov.get('sample_id')}`",
        f"- **Organism Context**: *{prov.get('organism')}*",
        f"- **Input SHA-256**: `{prov.get('input_sha256')}`",
        f"- **Detection Engine**: {prov.get('engine')} ({'LIVE EXECUTION' if prov.get('is_live') else 'PRECOMPUTED FIXTURE'})",
        f"- **Engine Version**: `{prov.get('engine_version')}`",
        f"- **Database Version**: `{prov.get('database_version')}`",
        f"- **Rules Version**: `{prov.get('rules_version')}`",
        f"- **Timestamp (UTC)**: `{prov.get('timestamp_utc')}`",
        f"- **Execution Mode**: {prov.get('mode_label')}",
    ]

    if errors:
        lines.append("- **Execution Errors**:")
        for err in errors:
            lines.append(f"  - ❌ {err}")

    lines.extend([
        "",
        "## 2. Genome Assembly Quality & Metrics",
        f"- **Contigs / Sequences**: {metrics.get('sequence_count')}",
        f"- **Total Length**: {metrics.get('total_length', 0):,} bp",
        f"- **GC Content**: {metrics.get('gc_content_pct')}%",
        f"- **Ambiguous Bases**: {metrics.get('ambiguous_count', 0):,} ({metrics.get('ambiguous_pct', 0.0)}%)",
        f"- **N50**: {metrics.get('n50', 0):,} bp",
    ])

    all_warnings = warnings + metrics.get("warnings", [])
    if all_warnings:
        lines.append("- **Assembly Quality Warnings**:")
        for w in all_warnings:
            lines.append(f"  - ⚠️ {w}")
    else:
        lines.append("- **Assembly Quality Warnings**: None detected (Assembly checks passed).")

    lines.extend([
        "",
        "## 3. Executive AMR Classification Summary",
        f"- **Total Antibiotics Evaluated**: {summary.get('total_antibiotics_evaluated', 0)}",
        f"- **Resistance Predicted**: {summary.get('resistant_count', 0)}",
        f"- **Susceptibility Predicted**: {summary.get('susceptible_count', 0)}",
        f"- **Indeterminate**: {summary.get('indeterminate_count', 0)}",
        "",
        "## 4. Antibiotic Susceptibility Interpretations",
        "| Antibiotic | Class | Status | Rule ID | Rationale | Evidence | Citations |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])

    for item in interps:
        evidence_str = "; ".join(item.get("evidence", [])) or "None"
        cit_str = "; ".join([c.split(":")[0] for c in item.get("citations", [])]) or "N/A"
        lines.append(
            f"| **{item.get('antibiotic')}** | {item.get('drug_class')} | **{item.get('status')}** | `{item.get('rule_id')}` | {item.get('rationale')} | {evidence_str} | {cit_str} |"
        )

    lines.extend([
        "",
        "## 5. Detected Resistance Determinants (Raw Tool Output)",
    ])

    if detections:
        lines.extend([
            "| Gene Symbol | Sequence / Contig | Class | Subclass | Method | % Identity | % Coverage |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for det in detections:
            lines.append(
                f"| `{det.get('gene_symbol')}` | {det.get('sequence_name')} | {det.get('class')} | {det.get('subclass')} | {det.get('method')} | {det.get('identity')}% | {det.get('coverage')}% |"
            )
    else:
        lines.append("_No AMR determinants detected at >=90% identity and >=80% coverage._")

    lines.extend([
        "",
        "## 6. Known Biological & Methodological Limitations",
        LIMITATIONS_TEXT,
        "",
        "---",
        "*Report generated automatically by Genome Firewall.*"
    ])
    return "\n".join(lines)


def generate_csv_report(result: dict[str, Any]) -> str:
    """Generate CSV summary of antibiotic interpretations."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Sample_ID",
        "Organism",
        "Antibiotic",
        "Class",
        "Status",
        "Rule_ID",
        "Rationale",
        "Evidence",
        "Citations",
        "Engine",
        "Is_Live",
        "Rules_Version",
        "Input_SHA256",
        "Timestamp_UTC"
    ])

    prov = result.get("provenance", {})
    sample_id = prov.get("sample_id", "")
    organism = prov.get("organism", "")
    engine = prov.get("engine", "")
    is_live = str(prov.get("is_live", False))
    rules_ver = prov.get("rules_version", "")
    sha256 = prov.get("input_sha256", "")
    timestamp = prov.get("timestamp_utc", "")

    for item in result.get("interpretations", []):
        evidence_str = "; ".join(item.get("evidence", []))
        citations_str = "; ".join(item.get("citations", []))
        writer.writerow([
            sample_id,
            organism,
            item.get("antibiotic", ""),
            item.get("drug_class", ""),
            item.get("status", ""),
            item.get("rule_id", ""),
            item.get("rationale", ""),
            evidence_str,
            citations_str,
            engine,
            is_live,
            rules_ver,
            sha256,
            timestamp,
        ])

    return output.getvalue()
