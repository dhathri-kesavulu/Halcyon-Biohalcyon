"""Genome Firewall: Browser-based Bacterial Genome Resistance-Evidence Analysis Prototype.

Frontend implementation using Streamlit.
Strict constraint: The frontend calls only the public function:
`analyze_genome(fasta_path, sample_id, organism=None) -> dict`
from `backend.pipeline`.
"""

import json
import os
import tempfile
import pandas as pd
import streamlit as st

# Strictly import ONLY the agreed public contract function from backend.pipeline
from backend.pipeline import analyze_genome

st.set_page_config(
    page_title="Genome Firewall | AMR Analysis",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for rich aesthetics and clear status badges
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.3rem;
        font-weight: 800;
        color: #1E293B;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .disclaimer-box {
        background-color: #FEF2F2;
        border-left: 5px solid #EF4444;
        padding: 1rem 1.2rem;
        border-radius: 6px;
        color: #991B1B;
        font-size: 0.95rem;
        margin-bottom: 1.5rem;
    }
    .mode-fixture-box {
        background-color: #FFFBEB;
        border-left: 5px solid #F59E0B;
        padding: 0.9rem 1.2rem;
        border-radius: 6px;
        color: #92400E;
        font-size: 0.92rem;
        margin-bottom: 1.5rem;
    }
    .mode-live-box {
        background-color: #ECFDF5;
        border-left: 5px solid #10B981;
        padding: 0.9rem 1.2rem;
        border-radius: 6px;
        color: #065F46;
        font-size: 0.92rem;
        margin-bottom: 1.5rem;
    }
    .kpi-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
    .status-resistant {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .status-susceptible {
        background-color: #DCFCE7;
        color: #166534;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .status-indeterminate {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .prov-code {
        font-family: monospace;
        background-color: #F1F5F9;
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
        font-size: 0.85rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Header
st.markdown('<div class="main-header">🛡️ Genome Firewall</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Bacterial Genome Resistance-Evidence Analysis Prototype & Provenance Auditor</div>',
    unsafe_allow_html=True,
)

# Mandatory Clinical Disclaimer
st.markdown(
    """
    <div class="disclaimer-box">
        <strong>⚠️ REGULATORY & CLINICAL DISCLAIMER</strong><br>
        <strong>RESEARCH USE ONLY:</strong> Genome Firewall is an exploratory hackathon prototype. It is <strong>NOT</strong> clinically validated, 
        cleared by any diagnostic authority, or a replacement for phenotypic laboratory Antimicrobial Susceptibility Testing (AST). 
        Predictions reflect algorithmic rule interpretations of assembled genomic sequence evidence.
    </div>
    """,
    unsafe_allow_html=True,
)

# Load Demo Catalog
DEMO_CATALOG_PATH = os.path.join("data", "demo", "catalog.json")
demo_catalog = {"fixtures": []}
if os.path.exists(DEMO_CATALOG_PATH):
    try:
        with open(DEMO_CATALOG_PATH, "r", encoding="utf-8") as f:
            demo_catalog = json.load(f)
    except Exception:
        pass

# Sidebar configuration
with st.sidebar:
    st.header("🧬 Sample Configuration")

    input_mode = st.radio(
        "Choose Input Source",
        ["Vetted Demonstration Genome", "Upload FASTA/FA/FNA"],
        index=0,
    )

    selected_fasta_path = None
    sample_id = "SAMPLE-01"
    organism = None

    if input_mode == "Vetted Demonstration Genome":
        fixtures = demo_catalog.get("fixtures", [])
        if fixtures:
            fixture_options = {
                f"{f['id']} - {f['name']}": f for f in fixtures
            }
            selected_label = st.selectbox(
                "Select Benchmark Demo Genome",
                list(fixture_options.keys()),
            )
            selected_fixture = fixture_options[selected_label]
            selected_fasta_path = os.path.join("data", "demo", selected_fixture["filename"])
            sample_id = selected_fixture["id"]
            organism = selected_fixture["organism"]

            st.caption(f"**Species**: *{organism}*")
            st.info(f"**Profile**: {selected_fixture['description']}")
        else:
            st.error("Demo catalog not found in `data/demo/catalog.json`.")

    else:
        uploaded_file = st.file_uploader(
            "Upload Assembled Bacterial Genome",
            type=["fasta", "fa", "fna"],
            help="Accepts assembled contigs in standard FASTA format.",
        )
        sample_id = st.text_input("Sample Identifier", value="CUSTOM-ISOLATE-01")
        organism_choice = st.selectbox(
            "Organism (Species Context)",
            [
                "Klebsiella pneumoniae",
                "Escherichia coli",
                "Staphylococcus aureus",
                "Pseudomonas aeruginosa",
                "Acinetobacter baumannii",
                "Other / Unknown",
            ],
            index=0,
        )
        if organism_choice == "Other / Unknown":
            organism = st.text_input("Custom Species Name (optional)", value="")
        else:
            organism = organism_choice

        if uploaded_file is not None:
            # Save uploaded file to a temporary file
            t_suffix = os.path.splitext(uploaded_file.name)[1] or ".fasta"
            with tempfile.NamedTemporaryFile(delete=False, suffix=t_suffix) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                selected_fasta_path = tmp_file.name

    st.markdown("---")
    st.markdown("### ⚖️ Rules Engine v1.0.0")
    st.caption(
        "Interprets AMR determinants into strict tripartite statuses: "
        "`Resistance predicted`, `Susceptibility predicted`, or `Indeterminate`. "
        "Missing resistance evidence **never** implies susceptibility by default."
    )

# Execution trigger
if selected_fasta_path:
    col_btn, _ = st.columns([2, 5])
    with col_btn:
        run_analysis = st.button("🚀 Run Resistance Analysis", type="primary", use_container_width=True)

    if run_analysis:
        with st.spinner("Inspecting genome metrics, querying AMR evidence, and evaluating rules..."):
            try:
                # Call ONLY the agreed public backend function
                result = analyze_genome(
                    fasta_path=selected_fasta_path,
                    sample_id=sample_id,
                    organism=organism if organism else None,
                )
                st.session_state["analysis_result"] = result
            except Exception as exc:
                st.session_state["analysis_error"] = str(exc)
                if "analysis_result" in st.session_state:
                    del st.session_state["analysis_result"]

# Display Error if any
if "analysis_error" in st.session_state and "analysis_result" not in st.session_state:
    err_msg = st.session_state["analysis_error"]
    st.error(f"❌ Analysis Execution Error: {err_msg}")
    if "AMRFinderPlus" in err_msg or "precomputed" in err_msg.lower():
        st.warning(
            "💡 **Help**: Live NCBI AMRFinderPlus is not installed in this environment. "
            "To evaluate custom unmapped FASTA genomes, configure AMRFinderPlus and its database. "
            "To view the full pipeline in action, select one of the vetted demonstration genomes from the sidebar."
        )

# Display Results
if "analysis_result" in st.session_state:
    result = st.session_state["analysis_result"]
    prov = result.get("provenance", {})
    metrics = result.get("genome_metrics", {})
    interps = result.get("interpretations", [])
    detections = result.get("detections", [])
    summary = result.get("summary", {})

    # Engine & Mode Banner
    if prov.get("is_live"):
        st.markdown(
            f"""
            <div class="mode-live-box">
                <strong>🟢 LIVE DETECTION ENGINE ACTIVE</strong>: Analysis executed using live 
                <code>{prov.get('engine')}</code> (Version: <code>{prov.get('engine_version')}</code>, 
                DB: <code>{prov.get('database_version')}</code>).
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="mode-fixture-box">
                <strong>⚠️ PRECOMPUTED DEMONSTRATION FIXTURE</strong>: {prov.get('mode_label')}.<br>
                <em>Findings are strictly derived from benchmark reference fixtures and not from live tool execution. 
                Live AMRFinderPlus is not present on this host.</em>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Executive Summary Metrics
    st.subheader("1. Executive Summary")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric("Total Antibiotics Evaluated", summary.get("total_antibiotics_evaluated", 0))
    with kpi2:
        st.metric("Resistance Predicted", summary.get("resistant_count", 0))
    with kpi3:
        st.metric("Susceptibility Predicted", summary.get("susceptible_count", 0))
    with kpi4:
        st.metric("Indeterminate Status", summary.get("indeterminate_count", 0))

    # Provenance and Genome QC side-by-side
    st.subheader("2. Provenance & Genome Assembly QC")
    col_prov, col_qc = st.columns(2)

    with col_prov:
        st.markdown("##### 🏷️ Provenance & Audit Trail")
        st.markdown(f"- **Sample ID**: `{prov.get('sample_id')}`")
        st.markdown(f"- **Organism Context**: *{prov.get('organism')}*")
        st.markdown(f"- **SHA-256 Hash**: <span class='prov-code'>{prov.get('input_sha256')}</span>", unsafe_allow_html=True)
        st.markdown(f"- **Engine**: `{prov.get('engine')}`")
        st.markdown(f"- **Engine Version**: `{prov.get('engine_version')}`")
        st.markdown(f"- **Database Version**: `{prov.get('database_version')}`")
        st.markdown(f"- **Rules Specification**: v`{prov.get('rules_version')}`")
        st.markdown(f"- **Timestamp (UTC)**: `{prov.get('timestamp_utc')}`")

    with col_qc:
        st.markdown("##### 🔬 Genome Assembly Metrics")
        st.markdown(f"- **Contigs / Sequences**: `{metrics.get('sequence_count')}`")
        st.markdown(f"- **Total Length**: `{metrics.get('total_length', 0):,} bp`")
        gc_str = f"{metrics.get('gc_content_pct')}%" if metrics.get("gc_content_pct") is not None else "N/A"
        st.markdown(f"- **GC Content**: `{gc_str}`")
        st.markdown(f"- **Assembly N50**: `{metrics.get('n50', 0):,} bp`")

        warnings = metrics.get("warnings", [])
        if warnings:
            st.warning("⚠️ **Assembly Quality Warnings**:\n" + "\n".join([f"- {w}" for w in warnings]))
        else:
            st.success("✅ Assembly quality checks passed. No input warnings.")

    # Antibiotic Susceptibility Table
    st.subheader("3. Antibiotic Susceptibility Interpretations")
    st.caption("Each antibiotic is categorized strictly into one of three statuses based on explicit rules.")

    filter_status = st.selectbox(
        "Filter by Prediction Status",
        ["All", "Resistance predicted", "Susceptibility predicted", "Indeterminate"],
        index=0,
    )

    filtered_interps = interps
    if filter_status != "All":
        filtered_interps = [i for i in interps if i["status"] == filter_status]

    if filtered_interps:
        table_rows = []
        for item in filtered_interps:
            status_val = item["status"]
            if status_val == "Resistance predicted":
                badge_html = f"<span class='status-resistant'>{status_val}</span>"
            elif status_val == "Susceptibility predicted":
                badge_html = f"<span class='status-susceptible'>{status_val}</span>"
            else:
                badge_html = f"<span class='status-indeterminate'>{status_val}</span>"

            evidence_str = "; ".join(item.get("evidence", [])) or "None"
            table_rows.append({
                "Antibiotic": item.get("antibiotic"),
                "Drug Class": item.get("drug_class"),
                "Status": status_val,
                "Rule ID": item.get("rule_id"),
                "Rationale": item.get("rationale"),
                "Evidence": evidence_str,
            })

        df_interps = pd.DataFrame(table_rows)
        st.dataframe(
            df_interps,
            column_config={
                "Antibiotic": st.column_config.TextColumn("Antibiotic", width="medium"),
                "Drug Class": st.column_config.TextColumn("Class", width="medium"),
                "Status": st.column_config.TextColumn("Prediction Status", width="medium"),
                "Rule ID": st.column_config.TextColumn("Rule ID", width="small"),
                "Rationale": st.column_config.TextColumn("Evidence Rationale", width="large"),
                "Evidence": st.column_config.TextColumn("Matched Determinants", width="medium"),
            },
            hide_index=True,
            use_container_width=True,
        )
    else:
        st.info(f"No antibiotics match the filter '{filter_status}'.")

    # Raw Detected AMR Determinants
    st.subheader("4. Detected AMR Determinants (Raw Tool Output)")
    if detections:
        det_rows = []
        for d in detections:
            det_rows.append({
                "Gene Symbol": d.get("gene_symbol"),
                "Sequence / Contig": d.get("sequence_name"),
                "Element Type": d.get("element_type"),
                "Class": d.get("class"),
                "Subclass": d.get("subclass"),
                "Method": d.get("method"),
                "Identity (%)": f"{d.get('identity')}%",
                "Coverage (%)": f"{d.get('coverage')}%",
            })
        df_det = pd.DataFrame(det_rows)
        st.dataframe(df_det, hide_index=True, use_container_width=True)
    else:
        st.info("No acquired resistance genes or known resistance mutations detected.")

    # Download Reports
    st.subheader("5. Export & Audit Trail Downloads")
    reports = result.get("reports", {})
    json_data = reports.get("json", json.dumps(result, indent=2))
    md_data = reports.get("markdown", "# Genome Firewall Report\n")
    csv_data = reports.get("csv", "")

    down_col1, down_col2, down_col3 = st.columns(3)
    with down_col1:
        st.download_button(
            label="📥 Download JSON Report",
            data=json_data,
            file_name=f"{prov.get('sample_id', 'sample')}_report.json",
            mime="application/json",
            use_container_width=True,
        )
    with down_col2:
        st.download_button(
            label="📄 Download Markdown Report",
            data=md_data,
            file_name=f"{prov.get('sample_id', 'sample')}_report.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with down_col3:
        st.download_button(
            label="📊 Download CSV Predictions",
            data=csv_data,
            file_name=f"{prov.get('sample_id', 'sample')}_predictions.csv",
            mime="text/csv",
            use_container_width=True,
        )

# Documentation / Rules Viewer Expander
with st.expander("📖 Explicit Rules Engine Specification (v1.0.0)"):
    st.markdown(
        """
        ### Interpretation Logic & Rationale
        Genome Firewall applies explicit, verified rules to evaluate genomic evidence:
        
        1. **Strict Tripartite Classification**:
           - **Resistance predicted**: High-confidence detection (≥90% identity, ≥80% coverage) of a verified resistance determinant, or established intrinsic species resistance.
           - **Susceptibility predicted**: Allowed **only** when the organism is fully characterized, assembly quality passes without critical warnings, all known resistance mechanisms for that drug class are covered, and zero resistance markers are detected.
           - **Indeterminate**: Assigned when the organism is uncharacterized, assembly has quality warnings, resistance mechanisms cannot be ruled out from gene absence alone (e.g. Colistin *mcr* vs chromosomal *mgrB*), or rules are unverified.
        
        2. **Absence of Evidence is NOT Evidence of Absence**:
           - The absence of a detected resistance gene **never** automatically marks an antibiotic as susceptible.
           - Example: Missing *mcr-1* does **not** confer susceptibility to Colistin, because chromosomal mutations (*pmrA/B*, *mgrB*) are frequent and cannot be ruled out without phenotypic AST.
        """
    )
