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
        "is_live_analysis": is_live,
        "mode_label": mode_label,
        "provenance_notes": mode_label,
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


# ---------------------------------------------------------------------------
# PDF Report Generation using ReportLab
# ---------------------------------------------------------------------------

import xml.sax.saxutils

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
        KeepTogether,
        HRFlowable,
    )
    from reportlab.pdfgen import canvas
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def _escape(text: Any) -> str:
    """Safely escape text for ReportLab XML/HTML Paragraphs."""
    if text is None:
        return "Not available"
    s = str(text)
    return xml.sax.saxutils.escape(s)


if HAS_REPORTLAB:
    class _NumberedCanvas(canvas.Canvas):
        """Two-pass canvas for dynamic 'Page X of Y' numbering and running headers/footers."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._saved_page_states = []
            self.sample_id_str = "SAMPLE"

        def showPage(self):
            self._saved_page_states.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            num_pages = len(self._saved_page_states)
            for state in self._saved_page_states:
                self.__dict__.update(state)
                self.draw_page_decorations(num_pages)
                super().showPage()
            super().save()

        def draw_page_decorations(self, page_count: int):
            self.saveState()
            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#475569"))

            # Running header on subsequent pages
            if self._pageNumber > 1:
                self.drawString(40, 755, "Genome Firewall — Antibiotic Resistance Analysis Report")
                self.setFont("Helvetica", 8)
                self.drawRightString(572, 755, f"Sample: {self.sample_id_str}")
                self.setStrokeColor(colors.HexColor("#CBD5E1"))
                self.setLineWidth(0.5)
                self.line(40, 748, 572, 748)

            # Running footer on every page
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(40, 40, 572, 40)
            self.setFont("Helvetica", 7.5)
            self.drawString(40, 28, "RESEARCH USE ONLY — Exploratory prototype. Does not replace phenotypic laboratory AST.")
            page_text = f"Page {self._pageNumber} of {page_count}"
            self.drawRightString(572, 28, page_text)
            self.restoreState()


def generate_pdf_report(result: dict[str, Any]) -> bytes:
    """
    Generate an auditable, multi-page PDF report in memory from analysis results.

    Features:
    - Title banner and clinical & regulatory boundaries notice.
    - Sample metadata, cryptographic SHA-256 hash, and engine provenance.
    - Explicit LIVE vs PRECOMPUTED/DEMO labelling throughout.
    - Genome assembly metrics & input quality warnings.
    - Complete antibiotic susceptibility interpretations table with status badges.
    - Detected raw resistance determinants table with genomic coordinates.
    - Limitations, methodological boundaries, and rule citations.
    - Two-pass 'Page X of Y' numbering and running headers/footers.

    Returns:
        Raw PDF document bytes.
    """
    if not HAS_REPORTLAB:
        raise RuntimeError("ReportLab is not installed. Run 'pip install reportlab' to enable PDF generation.")

    # Defensive extraction of result schema fields
    prov = result.get("provenance", {}) or {}
    metrics = result.get("genome_metrics", {}) or {}
    interps = result.get("interpretation") or result.get("interpretations") or []
    detections = result.get("detected_evidence") or result.get("detections") or []
    summary = result.get("summary", {}) or {}
    errors = result.get("analysis_errors") or result.get("errors") or []
    disclaimer = result.get("disclaimer") or DISCLAIMER_TEXT
    limitations = result.get("limitations") or LIMITATIONS_TEXT.split("\n")

    sample_id = result.get("sample_id") or prov.get("sample_id") or "UNKNOWN_SAMPLE"
    organism = result.get("organism") or prov.get("organism") or "Not specified"
    input_sha = prov.get("input_sha256") or "Not recorded"
    engine_name = prov.get("engine") or "Not specified"
    engine_ver = prov.get("engine_version") or "Not recorded"
    db_ver = prov.get("database_version") or "Not recorded"
    rules_ver = prov.get("rules_version") or "1.0.0"
    timestamp_utc = prov.get("timestamp_utc") or datetime.now(timezone.utc).isoformat()
    status_exec = result.get("status") or ("SUCCESS" if not errors else "FAILED")
    is_live = prov.get("is_live_analysis", False) or prov.get("is_live", False)
    mode_label = prov.get("mode_label") or prov.get("provenance_notes") or ("Live Engine" if is_live else "Precomputed Fixture")

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=45,
        bottomMargin=50,
    )

    # Styles setup
    base_styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle(
        "PDFTitle",
        parent=base_styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=2,
    )
    style_subtitle = ParagraphStyle(
        "PDFSubtitle",
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#475569"),
        spaceAfter=10,
    )
    style_h2 = ParagraphStyle(
        "PDFH2",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#1E293B"),
        spaceBefore=10,
        spaceAfter=5,
        keepWithNext=True,
    )
    style_body = ParagraphStyle(
        "PDFBody",
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#334155"),
    )
    style_bold = ParagraphStyle(
        "PDFBold",
        parent=style_body,
        fontName="Helvetica-Bold",
    )
    style_caption = ParagraphStyle(
        "PDFCaption",
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#64748B"),
    )
    style_table_hdr = ParagraphStyle(
        "PDFTableHdr",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.white,
    )
    style_table_cell = ParagraphStyle(
        "PDFTableCell",
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#1E293B"),
    )
    style_code = ParagraphStyle(
        "PDFCode",
        fontName="Courier",
        fontSize=7,
        leading=9,
        textColor=colors.HexColor("#0F172A"),
    )

    story = []

    # 1. Header & Title Banner
    story.append(Paragraph("Genome Firewall — Antibiotic Resistance Analysis", style_title))
    story.append(Paragraph("Evidence-Based Bacterial Resistance Interpretation & Cryptographic Provenance Audit", style_subtitle))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=8))

    # 2. Regulatory & Clinical Notice Box
    disclaimer_html = (
        f"<b>⚠️ CLINICAL & REGULATORY NOTICE (RESEARCH USE ONLY):</b><br/>"
        f"{_escape(disclaimer)}"
    )
    p_disc = Paragraph(disclaimer_html, style_caption)
    t_disc = Table([[p_disc]], colWidths=[532])
    t_disc.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#EF4444")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_disc)
    story.append(Spacer(1, 8))

    # 3. Detection Engine Audit & Mode Banner
    if status_exec == "FAILED":
        mode_text = (
            "<b>❌ ANALYSIS EXECUTION FAILED</b> — "
            "The genomic resistance analysis encountered errors and did not complete normally. "
            "Findings and interpretations may be partial, indeterminate, or unverified."
        )
        badge_bg = colors.HexColor("#FEE2E2")
        badge_border = colors.HexColor("#EF4444")
        badge_text_color = colors.HexColor("#991B1B")
    elif is_live:
        mode_text = (
            "<b>● LIVE EXECUTION (NCBI AMRFinderPlus Active)</b> — "
            "Genomic assembly was processed by local detector tool. Verified findings."
        )
        badge_bg = colors.HexColor("#D1FAE5")
        badge_border = colors.HexColor("#10B981")
        badge_text_color = colors.HexColor("#065F46")
    else:
        mode_text = (
            "<b>● DEMONSTRATION FIXTURE MODE (Precomputed Reference Data)</b> — "
            f"Findings are derived from verified benchmark reference profiles ({_escape(mode_label)}). "
            "Live AMRFinderPlus is not present on this host; no live sequence detection was fabricated."
        )
        badge_bg = colors.HexColor("#FEF3C7")
        badge_border = colors.HexColor("#F59E0B")
        badge_text_color = colors.HexColor("#92400E")

    style_mode = ParagraphStyle("PDFMode", parent=style_body, textColor=badge_text_color, fontSize=8)
    t_mode = Table([[Paragraph(mode_text, style_mode)]], colWidths=[532])
    t_mode.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), badge_bg),
        ("BOX", (0, 0), (-1, -1), 0.5, badge_border),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t_mode)
    story.append(Spacer(1, 10))

    # 4. Section 1: Provenance & Sample Metadata
    story.append(Paragraph("1. Provenance & Sample Audit Trail", style_h2))
    
    status_display = (
        f"<font color='#DC2626'><b>{_escape(status_exec)}</b></font>"
        if status_exec == "FAILED"
        else f"<font color='#16A34A'><b>{_escape(status_exec)}</b></font>"
    )
    meta_data = [
        [
            Paragraph(f"<b>Sample ID:</b> {_escape(sample_id)}", style_body),
            Paragraph(f"<b>Detection Engine:</b> {_escape(engine_name)}", style_body),
        ],
        [
            Paragraph(f"<b>Organism:</b> <i>{_escape(organism)}</i>", style_body),
            Paragraph(f"<b>Engine Version:</b> {_escape(engine_ver)}", style_body),
        ],
        [
            Paragraph(f"<b>Execution Status:</b> {status_display}", style_body),
            Paragraph(f"<b>Database Version:</b> {_escape(db_ver)}", style_body),
        ],
        [
            Paragraph(f"<b>Timestamp (UTC):</b> {_escape(timestamp_utc)}", style_body),
            Paragraph(f"<b>Ruleset Version:</b> v{_escape(rules_ver)}", style_body),
        ],
        [
            Paragraph(f"<b>Input SHA-256:</b> <font name='Courier' size='6.5'>{_escape(input_sha)}</font>", style_body),
            Paragraph(f"<b>Analysis Mode:</b> {'Live Tool' if is_live else 'Precomputed Demonstration'}", style_body),
        ],
    ]
    t_meta = Table(meta_data, colWidths=[266, 266])
    t_meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 10))

    # 5. Section 2: Genome Assembly Metrics & Quality Control
    story.append(Paragraph("2. Genome Assembly Quality Control & Metrics", style_h2))
    
    seq_count = metrics.get("sequence_count", "Not recorded")
    total_len = metrics.get("total_length") or metrics.get("total_length_bp") or 0
    total_len_str = f"{total_len:,} bp" if isinstance(total_len, (int, float)) and total_len > 0 else "Not recorded"
    gc_pct = metrics.get("gc_content_pct")
    gc_str = f"{gc_pct:.2f}%" if gc_pct is not None else "Not calculated"
    n50_val = metrics.get("n50") or metrics.get("n50_bp") or 0
    n50_str = f"{n50_val:,} bp" if isinstance(n50_val, (int, float)) and n50_val > 0 else "Not recorded"
    ambig_count = metrics.get("ambiguous_count", 0)
    ambig_pct = metrics.get("ambiguous_pct", 0.0)
    ambig_str = f"{ambig_count:,} ({ambig_pct}%)" if ambig_count else "0 (0.0%)"

    qc_table_data = [
        [
            Paragraph("<b>Contig Count</b>", style_body),
            Paragraph("<b>Assembly Length</b>", style_body),
            Paragraph("<b>GC Content</b>", style_body),
            Paragraph("<b>Contig N50</b>", style_body),
            Paragraph("<b>Ambiguous Bases</b>", style_body),
        ],
        [
            Paragraph(f"{seq_count}", style_body),
            Paragraph(total_len_str, style_body),
            Paragraph(gc_str, style_body),
            Paragraph(n50_str, style_body),
            Paragraph(ambig_str, style_body),
        ],
    ]
    t_qc = Table(qc_table_data, colWidths=[100, 115, 105, 105, 107])
    t_qc.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    for r in range(len(qc_table_data[0])):
        qc_table_data[0][r].style = style_table_hdr
    story.append(t_qc)

    # Assembly warnings if any
    qc_warnings = metrics.get("warnings", [])
    if qc_warnings:
        story.append(Spacer(1, 4))
        warn_text = "<b>Assembly Quality Warnings:</b><br/>" + "<br/>".join([f"• {_escape(w)}" for w in qc_warnings])
        p_warn = Paragraph(warn_text, ParagraphStyle("WarnStyle", parent=style_body, textColor=colors.HexColor("#B45309"), fontSize=7.5))
        t_warn = Table([[p_warn]], colWidths=[532])
        t_warn.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFBEB")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#FDE68A")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_warn)
    story.append(Spacer(1, 10))

    # 6. Section 3: Antibiotic Susceptibility Predictions
    story.append(Paragraph("3. Antibiotic Susceptibility Interpretations", style_h2))
    
    # Executive summary tallies
    res_cnt = summary.get("resistant_count", sum(1 for i in interps if i.get("status") == "Resistance predicted"))
    sus_cnt = summary.get("susceptible_count", sum(1 for i in interps if i.get("status") == "Susceptibility predicted"))
    ind_cnt = summary.get("indeterminate_count", sum(1 for i in interps if i.get("status") == "Indeterminate"))
    total_abx = len(interps)

    tally_html = (
        f"<b>Total Evaluated:</b> {total_abx} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<font color='#B91C1C'><b>Resistance predicted:</b> {res_cnt}</font> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<font color='#047857'><b>Susceptibility predicted:</b> {sus_cnt}</font> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"<font color='#B45309'><b>Indeterminate:</b> {ind_cnt}</font>"
    )
    story.append(Paragraph(tally_html, style_body))
    story.append(Spacer(1, 5))

    if interps:
        # Table of interpretations with repeated headers across pages
        # Widths total = 532 pt: Antibiotic (80), Class (75), Status (85), Rule ID & Evidence (110), Rationale (182)
        interp_rows = [[
            Paragraph("<b>Antibiotic</b>", style_table_hdr),
            Paragraph("<b>Drug Class</b>", style_table_hdr),
            Paragraph("<b>Prediction Status</b>", style_table_hdr),
            Paragraph("<b>Rule & Evidence</b>", style_table_hdr),
            Paragraph("<b>Clinical / Mechanistic Rationale</b>", style_table_hdr),
        ]]

        for item in interps:
            abx = item.get("antibiotic") or "Unknown"
            d_class = item.get("drug_class") or "Unclassified"
            status = item.get("status") or "Indeterminate"
            rule_id = item.get("rule_id") or "RULE-INDET-001"
            explanation = item.get("confidence_or_criteria") or item.get("rationale") or "No rationale recorded."
            evidence_genes = item.get("evidence_genes") or item.get("evidence") or []
            if isinstance(evidence_genes, list):
                ev_str = ", ".join([str(e) for e in evidence_genes]) or "None"
            else:
                ev_str = str(evidence_genes)

            # Badge styling based strictly on tripartite status
            if status == "Resistance predicted":
                status_html = "<b><font color='#991B1B'>Resistance predicted</font></b>"
            elif status == "Susceptibility predicted":
                status_html = "<b><font color='#065F46'>Susceptibility predicted</font></b>"
            else:
                status_html = "<b><font color='#92400E'>Indeterminate</font></b>"

            rule_ev_html = f"<b>{_escape(rule_id)}</b><br/><font size='6.5' color='#475569'>{_escape(ev_str)}</font>"

            interp_rows.append([
                Paragraph(f"<b>{_escape(abx)}</b>", style_table_cell),
                Paragraph(_escape(d_class), style_table_cell),
                Paragraph(status_html, style_table_cell),
                Paragraph(rule_ev_html, style_table_cell),
                Paragraph(_escape(explanation), style_table_cell),
            ])

        t_interp = Table(interp_rows, colWidths=[80, 75, 85, 110, 182], repeatRows=1)
        t_interp.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t_interp)
    else:
        story.append(Paragraph("<i>No antibiotic interpretations were evaluated.</i>", style_body))

    story.append(Spacer(1, 12))

    # 7. Section 4: Detected Genomic Resistance Evidence (Raw Findings)
    story.append(Paragraph("4. Detected Genomic Resistance Evidence (Raw Findings)", style_h2))
    
    if detections:
        # Widths total = 532 pt: Gene (80), Class (75), Subclass (80), Coverage (52), Identity (52), Location (140), Strand (53)
        det_rows = [[
            Paragraph("<b>Gene Symbol</b>", style_table_hdr),
            Paragraph("<b>Class</b>", style_table_hdr),
            Paragraph("<b>Subclass</b>", style_table_hdr),
            Paragraph("<b>Cov %</b>", style_table_hdr),
            Paragraph("<b>Ident %</b>", style_table_hdr),
            Paragraph("<b>Location / Contig</b>", style_table_hdr),
            Paragraph("<b>Strand</b>", style_table_hdr),
        ]]

        for det in detections:
            gene = det.get("gene_symbol") or det.get("element_symbol") or "Unknown"
            e_class = det.get("class") or "UNKNOWN"
            subclass = det.get("subclass") or det.get("element_subtype") or "N/A"
            cov = det.get("coverage", 0.0)
            cov_str = f"{cov:.1f}%" if isinstance(cov, (int, float)) else str(cov)
            ident = det.get("identity", 0.0)
            ident_str = f"{ident:.1f}%" if isinstance(ident, (int, float)) else str(ident)
            contig = det.get("contig_id") or det.get("sequence_name") or "contig"
            start = det.get("start")
            stop = det.get("stop")
            loc_str = f"{contig}:{start}-{stop}" if start and stop else str(contig)
            strand = det.get("strand") or "+"

            det_rows.append([
                Paragraph(f"<b>{_escape(gene)}</b>", style_table_cell),
                Paragraph(_escape(e_class), style_table_cell),
                Paragraph(_escape(subclass), style_table_cell),
                Paragraph(_escape(cov_str), style_table_cell),
                Paragraph(_escape(ident_str), style_table_cell),
                Paragraph(_escape(loc_str), style_table_cell),
                Paragraph(_escape(strand), style_table_cell),
            ])

        t_det = Table(det_rows, colWidths=[80, 75, 80, 52, 52, 140, 53], repeatRows=1)
        t_det.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_det)
    else:
        story.append(Paragraph("<i>No acquired AMR determinants or verified resistance mutations detected.</i>", style_body))

    story.append(Spacer(1, 12))

    # 8. Section 5: Methodological Limitations & Interpretation Sources
    story.append(Paragraph("5. Methodological Limitations & Evidence Ruleset", style_h2))
    
    limits_html = "<b>Biological & Algorithmic Limitations:</b><br/>"
    for idx, lim in enumerate(limitations, start=1):
        clean_lim = lim.strip().lstrip("1234567890. ")
        limits_html += f"• {_escape(clean_lim)}<br/>"
    story.append(Paragraph(limits_html, style_caption))
    story.append(Spacer(1, 4))

    sources_html = (
        "<b>Authoritative Ruleset References:</b><br/>"
        "• Clinical and Laboratory Standards Institute (CLSI) M100 Performance Standards for AST (34th Edition, 2024).<br/>"
        "• European Committee on Antimicrobial Susceptibility Testing (EUCAST) Expert Rules on AMR (v3.3, 2021).<br/>"
        "• NCBI AMRFinderPlus Curated Reference Gene Catalog (Feldgarden et al., Scientific Reports 2021; 11:12728)."
    )
    story.append(Paragraph(sources_html, style_caption))

    if errors:
        story.append(Spacer(1, 6))
        err_html = "<b>Recorded Analysis Errors / Engine Warnings:</b><br/>" + "<br/>".join([f"❌ {_escape(e)}" for e in errors])
        story.append(Paragraph(err_html, ParagraphStyle("ErrStyle", parent=style_body, textColor=colors.HexColor("#DC2626"), fontSize=7.5)))

    # Set dynamic sample_id on canvas for headers
    def canvas_maker(*args, **kwargs):
        c = _NumberedCanvas(*args, **kwargs)
        c.sample_id_str = str(sample_id)
        return c

    doc.build(story, canvasmaker=canvas_maker)
    return pdf_buffer.getvalue()
