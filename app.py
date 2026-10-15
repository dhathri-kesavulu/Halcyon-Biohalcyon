"""
Genome Firewall - Streamlit Frontend Application.
Title: Genome Firewall — Evidence-Based Antibiotic Resistance Analysis.

Integration Contract:
Imports and calls exclusively:
  from backend.pipeline import analyze_genome
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import tempfile
from typing import Any, Dict, List, Optional

import streamlit as st

# Strict integration contract: only import analyze_genome from backend.pipeline
from backend.pipeline import analyze_genome
from backend.report import generate_pdf_report


st.set_page_config(
    page_title="Genome Firewall — Evidence-Based Antibiotic Resistance Analysis",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Plain, functional CSS for status distinctions and audit badges (no flashy animations)
st.markdown(
    """
    <style>
    .status-badge-resistant {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.85rem;
        color: #7F1D1D;
        background-color: #FEE2E2;
        border: 1px solid #FCA5A5;
    }
    .status-badge-susceptible {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.85rem;
        color: #065F46;
        background-color: #D1FAE5;
        border: 1px solid #6EE7B7;
    }
    .status-badge-indeterminate {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.85rem;
        color: #92400E;
        background-color: #FEF3C7;
        border: 1px solid #FCD34D;
    }
    .mode-badge-live {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.85rem;
        color: #065F46;
        background-color: #D1FAE5;
        border: 1px solid #34D399;
    }
    .mode-badge-fixture {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 4px;
        font-weight: 700;
        font-size: 0.85rem;
        color: #92400E;
        background-color: #FEF3C7;
        border: 1px solid #F59E0B;
    }
    .clinical-notice {
        background-color: #F3F4F6;
        border-left: 5px solid #4B5563;
        padding: 12px 16px;
        border-radius: 3px;
        font-size: 0.85rem;
        color: #1F2937;
        margin-top: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def build_csv_summary(interpretations: List[Dict[str, Any]]) -> str:
    """Generate a clean CSV summary string of antibiotic interpretation results."""
    output = io.StringIO()
    fieldnames = ["Antibiotic", "Drug Class", "Status", "Supporting Evidence", "Rule ID", "Explanation"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in interpretations:
        evidence_list = row.get("evidence_genes", [])
        evidence_str = ", ".join(evidence_list) if isinstance(evidence_list, list) else str(evidence_list)
        writer.writerow({
            "Antibiotic": row.get("antibiotic", ""),
            "Drug Class": row.get("drug_class", ""),
            "Status": row.get("status", ""),
            "Supporting Evidence": evidence_str,
            "Rule ID": row.get("rule_id", ""),
            "Explanation": row.get("confidence_or_criteria", ""),
        })
    return output.getvalue()


# 1. Title & Plain-Language Research Prototype Description
st.title("Genome Firewall — Evidence-Based Antibiotic Resistance Analysis")
st.markdown(
    "**Notice:** This application is an exploratory research prototype for resistance-evidence "
    "analysis from bacterial genome assemblies. It is **not a clinical diagnostic tool** and must not "
    "be used for therapeutic or clinical decision making. Laboratory antimicrobial susceptibility testing "
    "(AST) remains necessary to confirm phenotypic resistance profiles."
)

st.markdown("---")

# 2. Sidebar Inputs: Sample ID, Organism, and Quick-Load Option
with st.sidebar:
    st.header("Analysis Inputs")
    sample_id_input = st.text_input(
        "Sample Identifier *",
        value="SAMPLE-001",
        help="Unique identifier for the bacterial isolate being analyzed (required).",
    )
    organism_input = st.text_input(
        "Bacterial Organism (Optional)",
        value="",
        placeholder="e.g. Klebsiella pneumoniae",
        help="Optional species name. When provided, organism-specific AST rule correlations are evaluated.",
    )

    st.markdown("---")
    st.subheader("Reference Demo Datasets")
    st.caption("Load a bundled benchmark isolate to test the analysis pipeline:")
    demo_files = {
        "Klebsiella pneumoniae (KPC-2 Producer)": {
            "path": os.path.join("data", "demo", "klebsiella_pneumoniae_kpc.fasta"),
            "organism": "Klebsiella pneumoniae",
            "sample_id": "KP-KPC-BENCHMARK",
        },
        "Staphylococcus aureus (MRSA USA300)": {
            "path": os.path.join("data", "demo", "staphylococcus_aureus_mrsa.fasta"),
            "organism": "Staphylococcus aureus",
            "sample_id": "SA-MRSA-BENCHMARK",
        },
        "Escherichia coli (MDR ESBL)": {
            "path": os.path.join("data", "demo", "escherichia_coli_multidrug.fasta"),
            "organism": "Escherichia coli",
            "sample_id": "EC-MDR-BENCHMARK",
        },
    }

    selected_demo = st.selectbox("Select Benchmark Isolate:", list(demo_files.keys()))
    if st.button("Use Selected Benchmark Isolate"):
        chosen = demo_files[selected_demo]
        st.session_state["demo_fasta_path"] = chosen["path"]
        st.session_state["demo_organism"] = chosen["organism"]
        st.session_state["demo_sample_id"] = chosen["sample_id"]
        st.success(f"Selected: {selected_demo}")

# Synchronize input state if demo was loaded
if "demo_sample_id" in st.session_state and sample_id_input == "SAMPLE-001":
    sample_id_input = st.session_state["demo_sample_id"]
if "demo_organism" in st.session_state and not organism_input:
    organism_input = st.session_state["demo_organism"]

# 3. Main Input Area: FASTA/FA/FNA File Upload
st.subheader("1. Ingest Bacterial Genome Assembly")
uploaded_file = st.file_uploader(
    "Upload bacterial genome sequence file (.fasta, .fa, .fna)",
    type=["fasta", "fa", "fna"],
    help="Upload assembled contigs or scaffolds in standard nucleotide FASTA format.",
)

active_fasta_path: Optional[str] = None
is_temp_file = False

if uploaded_file is not None:
    # Save uploaded file safely to a temporary file
    temp_suffix = os.path.splitext(uploaded_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=temp_suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        active_fasta_path = tmp.name
        is_temp_file = True
    st.info(f"File uploaded: **{uploaded_file.name}** ({uploaded_file.size:,} bytes)")
elif "demo_fasta_path" in st.session_state:
    demo_p = st.session_state["demo_fasta_path"]
    if os.path.exists(demo_p):
        active_fasta_path = demo_p
        st.info(f"Using reference benchmark isolate: `{os.path.basename(demo_p)}`")

# 4. Analyze Button with Input Validation & Progress Indication
st.markdown("---")
analyze_btn = st.button("🔬 Run Evidence Analysis", type="primary", use_container_width=True)

if analyze_btn:
    # Input validation
    clean_sample_id = sample_id_input.strip() if sample_id_input else ""
    if not clean_sample_id:
        st.error("Validation Error: Please provide a valid Sample Identifier before proceeding.")
    elif not active_fasta_path or not os.path.isfile(active_fasta_path):
        st.error("Validation Error: Please upload a FASTA sequence file (.fasta, .fa, .fna) or select a benchmark isolate.")
    else:
        # Prevent stale analysis and reports on new run or error
        st.session_state["latest_analysis"] = None
        with st.spinner("Processing genome assembly, computing QC metrics, and applying explicit resistance rules..."):
            try:
                raw_organism = organism_input.strip() if organism_input else None
                analysis_output = analyze_genome(
                    fasta_path=active_fasta_path,
                    sample_id=clean_sample_id,
                    organism=raw_organism,
                )
                if analysis_output.get("status") == "FAILED":
                    errs = analysis_output.get("errors", [])
                    st.error(f"Analysis Failed: {', '.join(errs) if errs else 'Unknown execution error'}")
                    st.session_state["latest_analysis"] = None
                else:
                    st.session_state["latest_analysis"] = analysis_output
                    st.session_state["analyzed_sample_id"] = clean_sample_id
            except Exception as exc:
                st.error(f"Unexpected Backend Error during analysis: {str(exc)}")
                st.session_state["latest_analysis"] = None
            finally:
                # Clean up temporary uploaded file if created
                if is_temp_file and active_fasta_path and os.path.exists(active_fasta_path):
                    try:
                        os.remove(active_fasta_path)
                    except Exception:
                        pass

# 5. Display Analysis Results
if st.session_state.get("latest_analysis"):
    result: Dict[str, Any] = st.session_state["latest_analysis"]

    # Defensive extraction of all schema fields
    sample_id = result.get("sample_id", "UNKNOWN")
    organism_val = result.get("organism") or "Not specified"
    prov: Dict[str, Any] = result.get("provenance", {})
    metrics: Dict[str, Any] = result.get("genome_metrics", {})
    interps: List[Dict[str, Any]] = result.get("interpretation", [])
    evidence: List[Dict[str, Any]] = result.get("detected_evidence", [])
    disclaimers: List[str] = result.get("disclaimers", [])
    errors: List[str] = result.get("analysis_errors", [])

    is_live = prov.get("is_live_analysis", False)

    # 8. Honest Engine Mode & Detector/Database Status (Never hide an unavailable detector)
    st.subheader("2. Detection Engine Audit & Provenance")
    if is_live:
        st.markdown('<span class="mode-badge-live">● LIVE ANALYSIS (AMRFinderPlus Engine Active)</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="mode-badge-fixture">● DEMONSTRATION FIXTURE MODE (Precomputed Reference Data)</span>', unsafe_allow_html=True)
        st.warning(
            "**Notice on Engine Availability:** A verified local live AMRFinderPlus installation/database was not found. "
            "This analysis uses precomputed reference demonstration data to evaluate explicit rules without fabricating live sequence detection.",
            icon="⚠️",
        )

    col_meta1, col_meta2, col_meta3 = st.columns(3)
    with col_meta1:
        st.write(f"**Sample ID:** `{sample_id}`")
        st.write(f"**Organism:** {organism_val}")
        st.write(f"**Input FASTA SHA-256:** `{prov.get('input_sha256') or 'Unavailable'}`")
    with col_meta2:
        st.write(f"**Detection Engine:** {prov.get('engine', 'N/A')}")
        st.write(f"**Engine Version:** `{prov.get('engine_version') or 'N/A'}`")
        st.write(f"**Database Version:** `{prov.get('database_version') or 'N/A'}`")
    with col_meta3:
        st.write(f"**Ruleset Version:** `{prov.get('rules_version', 'N/A')}`")
        st.write(f"**Analysis Mode:** {'Live Subprocess' if is_live else 'Precomputed Demonstration'}")
        st.write(f"**Timestamp (UTC):** `{prov.get('timestamp_utc') or 'N/A'}`")

    if prov.get("provenance_notes"):
        st.caption(f"**Audit Notes:** {prov.get('provenance_notes')}")

    # Display any backend execution errors if present
    if errors:
        st.error(f"Backend Analysis Warnings/Errors ({len(errors)}):")
        for err in errors:
            st.markdown(f"- `{err}`")

    # 5. Genome Summary: Sequence count, Total length, GC percentage, and Warnings
    st.markdown("---")
    st.subheader("3. Genome Metrics & Assembly Quality Control")
    g_col1, g_col2, g_col3, g_col4 = st.columns(4)

    seq_count = metrics.get("sequence_count", 0)
    total_len = metrics.get("total_length_bp", 0)
    gc_pct = metrics.get("gc_content_pct")
    n50_val = metrics.get("n50_bp", 0)

    g_col1.metric("Sequence / Contig Count", f"{seq_count:,}")
    g_col2.metric("Total Assembly Length", f"{total_len:,} bp")
    g_col3.metric("GC Content", f"{gc_pct:.2f}%" if gc_pct is not None else "N/A")
    g_col4.metric("Contig N50", f"{n50_val:,} bp")

    warnings_list = metrics.get("warnings", [])
    if warnings_list:
        st.warning(f"**Assembly QC Warnings ({len(warnings_list)}):**")
        for w in warnings_list:
            st.markdown(f"- ⚠️ {w}")
    else:
        st.success("No input assembly anomalies detected.")

    # 6 & 7. Antibiotic Interpretation Table with Visible Distinction between Statuses
    st.markdown("---")
    st.subheader("4. Antibiotic Susceptibility & Resistance Predictions")
    st.caption(
        "Explicit three-state prediction: Resistance predicted, Susceptibility predicted, or Indeterminate. "
        "Missing resistance evidence does NOT imply susceptibility."
    )

    if not interps:
        st.info("No antibiotic interpretation rules were evaluated for this sample.")
    else:
        # Status summary tallies
        n_res = sum(1 for i in interps if i.get("status") == "Resistance predicted")
        n_sus = sum(1 for i in interps if i.get("status") == "Susceptibility predicted")
        n_ind = sum(1 for i in interps if i.get("status") == "Indeterminate")

        tally_col1, tally_col2, tally_col3 = st.columns(3)
        tally_col1.markdown(f"**Resistance Predicted:** `{n_res}`")
        tally_col2.markdown(f"**Susceptibility Predicted:** `{n_sus}`")
        tally_col3.markdown(f"**Indeterminate:** `{n_ind}`")

        # Table Display
        st.markdown("<br/>", unsafe_allow_html=True)
        for item in interps:
            abx_name = item.get("antibiotic", "Unknown Drug")
            drug_class = item.get("drug_class", "Unclassified")
            status = item.get("status", "Indeterminate")
            explanation = item.get("confidence_or_criteria", "No explanation provided.")
            evidence_genes = item.get("evidence_genes", [])
            rule_id = item.get("rule_id", "N/A")

            # Visible distinction between the 3 statuses
            if status == "Resistance predicted":
                badge_html = '<span class="status-badge-resistant">🔴 Resistance predicted</span>'
            elif status == "Susceptibility predicted":
                badge_html = '<span class="status-badge-susceptible">🟢 Susceptibility predicted</span>'
            else:
                badge_html = '<span class="status-badge-indeterminate">🟡 Indeterminate</span>'

            with st.container():
                col_drug, col_badge = st.columns([3, 1])
                with col_drug:
                    st.markdown(f"**{abx_name}** `({drug_class})`")
                with col_badge:
                    st.markdown(badge_html, unsafe_allow_html=True)

                evidence_display = f"**Supporting Evidence:** `{', '.join(evidence_genes)}` | " if evidence_genes else ""
                st.caption(f"{evidence_display}**Rule ID:** `{rule_id}` — {explanation}")
                st.markdown("<hr style='margin: 0.2rem 0 0.6rem 0; border: none; border-top: 1px solid #E5E7EB;'/>", unsafe_allow_html=True)

    # Raw Detected AMR Determinants Expandable Section
    with st.expander(f"View Detected Genomic AMR Determinants ({len(evidence)})", expanded=False):
        if evidence:
            determinants_table = []
            for det in evidence:
                determinants_table.append({
                    "Gene Symbol": det.get("gene_symbol", "N/A"),
                    "Element Class": det.get("class", "N/A"),
                    "Subclass": det.get("subclass", ""),
                    "Coverage %": f"{det.get('coverage', 0.0):.1f}%",
                    "Identity %": f"{det.get('identity', 0.0):.1f}%",
                    "Location": f"{det.get('contig_id', '')}:{det.get('start', 0)}-{det.get('stop', 0)}",
                    "Strand": det.get("strand", "+"),
                })
            st.dataframe(determinants_table, use_container_width=True)
        else:
            st.write("No acquired AMR determinants detected in this assembly.")

    # 9. Download Generated PDF Report, JSON Audit Trail, and CSV Summary
    st.markdown("---")
    st.subheader("5. Auditable Export & Downloads")

    safe_sample_id = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(sample_id))

    # Primary: PDF Report Download
    pdf_bytes = None
    pdf_err_msg = None
    try:
        if "reports" in result and isinstance(result["reports"], dict) and result["reports"].get("pdf"):
            pdf_bytes = result["reports"]["pdf"]
        else:
            pdf_bytes = generate_pdf_report(result)
    except Exception as exc:
        pdf_err_msg = str(exc)

    if pdf_bytes:
        st.download_button(
            label="📄 Download Report (PDF)",
            data=pdf_bytes,
            file_name=f"GF_{safe_sample_id}_report.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True,
            help="Download comprehensive clinical & audit resistance report as an auditable multi-page PDF document.",
        )
    else:
        warn_txt = pdf_err_msg or "PDF generation library unavailable."
        st.warning(f"PDF report could not be generated: {warn_txt}")

    st.markdown("<div style='height: 8px'></div>", unsafe_allow_html=True)
    dl_col1, dl_col2 = st.columns(2)

    # 1. JSON Report (redact binary pdf if present in reports)
    clean_result_json = dict(result)
    if "reports" in clean_result_json and isinstance(clean_result_json["reports"], dict):
        clean_result_json["reports"] = {k: v for k, v in clean_result_json["reports"].items() if k != "pdf"}
    json_data = json.dumps(clean_result_json, indent=2, ensure_ascii=False)
    dl_col1.download_button(
        label="📥 Download JSON Report",
        data=json_data,
        file_name=f"GF_{safe_sample_id}_audit.json",
        mime="application/json",
        use_container_width=True,
    )

    # 2. CSV Summary
    csv_data = build_csv_summary(interps)
    dl_col2.download_button(
        label="📥 Download CSV Summary",
        data=csv_data,
        file_name=f"GF_{safe_sample_id}_summary.csv",
        mime="text/csv",
        use_container_width=True,
    )

# Mandatory Clinical Notice & Boundaries
st.markdown(
    """
    <div class="clinical-notice">
        <strong>CLINICAL & REGULATORY NOTICE:</strong><br/>
        Genome Firewall is a research and hackathon demonstration prototype only. It has not been approved or cleared by any regulatory agency for clinical diagnostic procedures, therapeutic guidance, or in vitro diagnostic (IVD) use.<br/>
        This prototype does <strong>not</strong> substitute for conventional phenotypic antimicrobial susceptibility testing (AST) performed in accredited clinical microbiology laboratories. Genotypic absence of resistance markers must never be interpreted as clinical susceptibility without laboratory confirmation.
    </div>
    """,
    unsafe_allow_html=True,
)
