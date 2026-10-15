"""Rule-based interpretation engine for AMR genomic evidence.

Auditable Rules Engine Specification (v1.0.0):
- Grounded in CLSI M100, EUCAST Expert Rules, and NCBI Reference Gene Catalog literature.
- Output per antibiotic is strictly one of:
    * 'Resistance predicted'
    * 'Susceptibility predicted'
    * 'Indeterminate'
- Missing resistance evidence NEVER automatically implies susceptibility.
- Conservative conflict handling: contradictory or borderline evidence yields 'Indeterminate'.
- No arbitrary confidence percentages; reports factual identity% and coverage% evidence.
"""

from typing import Any

RULES_VERSION = "1.0.0"

# Standard Literature Citations
CITATIONS = {
    "CLSI_M100": "CLSI M100: Performance Standards for Antimicrobial Susceptibility Testing, 34th Ed., 2024.",
    "EUCAST_RULES": "EUCAST: Intrinsic Resistance and Exceptional Phenotypes Expert Rules, v3.3, 2021.",
    "NCBI_AMRFINDER": (
        "Feldgarden M, et al. AMRFinderPlus and the Reference Gene Catalog facilitate examination of the NCBI "
        "curated collection of reference AMR genes. Sci Rep. 2021;11:12728."
    ),
    "SANCHES_MRSA": "Chambers HF, DeLeo FR. Waves of resistance: Staphylococcus aureus in the antibiotic era. Nat Rev Microbiol. 2009;7(9):629-641.",
    "POIREL_COLISTIN": "Poirel L, et al. Polymyxins: Antibacterial Activity, Susceptibility Testing, and Resistance Mechanisms Encoded by Plasmids or Chromosomes. Clin Microbiol Rev. 2017;30(2):557-596.",
}

# Catalog of evaluated antibiotics
ANTIBIOTIC_PANEL = [
    {"name": "Meropenem", "class": "Carbapenem", "gram": "Both"},
    {"name": "Imipenem", "class": "Carbapenem", "gram": "Both"},
    {"name": "Ertapenem", "class": "Carbapenem", "gram": "Negative"},
    {"name": "Ceftriaxone", "class": "Cephalosporin (3rd gen)", "gram": "Both"},
    {"name": "Ceftazidime", "class": "Cephalosporin (3rd gen)", "gram": "Negative"},
    {"name": "Cefepime", "class": "Cephalosporin (4th gen)", "gram": "Both"},
    {"name": "Ampicillin", "class": "Aminopenicillin", "gram": "Both"},
    {"name": "Piperacillin-tazobactam", "class": "Beta-lactam / BLI", "gram": "Both"},
    {"name": "Oxacillin", "class": "Penicillinase-resistant Penicillin", "gram": "Positive"},
    {"name": "Cefoxitin", "class": "Cephamycin (MRSA surrogate)", "gram": "Positive"},
    {"name": "Ciprofloxacin", "class": "Fluoroquinolone", "gram": "Both"},
    {"name": "Levofloxacin", "class": "Fluoroquinolone", "gram": "Both"},
    {"name": "Gentamicin", "class": "Aminoglycoside", "gram": "Both"},
    {"name": "Tobramycin", "class": "Aminoglycoside", "gram": "Both"},
    {"name": "Amikacin", "class": "Aminoglycoside", "gram": "Both"},
    {"name": "Tetracycline", "class": "Tetracycline", "gram": "Both"},
    {"name": "Trimethoprim-sulfamethoxazole", "class": "Folate pathway inhibitor", "gram": "Both"},
    {"name": "Colistin", "class": "Polymyxin", "gram": "Negative"},
    {"name": "Vancomycin", "class": "Glycopeptide", "gram": "Positive"},
]

# Auditable Rules Table with Explicit Evidence Requirements and Citations
RULES_TABLE = [
    {
        "rule_id": "RULE-CARB-001",
        "description": "Carbapenem resistance conferred by acquired carbapenemase genes.",
        "antibiotics": ["Meropenem", "Imipenem", "Ertapenem"],
        "supported_organisms": ["Klebsiella pneumoniae", "Escherichia coli", "Enterobacterales"],
        "target_mechanisms": ["blaKPC", "blaNDM", "blaVIM", "blaIMP", "blaOXA-48-like"],
        "evidence_requirements": "Identity >= 90.0%, Coverage >= 80.0%",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]],
    },
    {
        "rule_id": "RULE-ESBL-001",
        "description": "Extended-spectrum cephalosporin resistance conferred by ESBL enzymes.",
        "antibiotics": ["Ceftriaxone", "Ceftazidime", "Cefepime"],
        "supported_organisms": ["Klebsiella pneumoniae", "Escherichia coli", "Enterobacterales"],
        "target_mechanisms": ["blaCTX-M", "blaSHV ESBLs (e.g. SHV-12)", "blaTEM ESBLs"],
        "evidence_requirements": "Identity >= 90.0%, Coverage >= 80.0%",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]],
    },
    {
        "rule_id": "RULE-AMP-INTR-001",
        "description": "Intrinsic low-level ampicillin resistance in Klebsiella pneumoniae mediated by chromosomal blaSHV non-ESBL beta-lactamase.",
        "antibiotics": ["Ampicillin"],
        "supported_organisms": ["Klebsiella pneumoniae"],
        "target_mechanisms": ["Species intrinsic chromosomal blaSHV"],
        "evidence_requirements": "Species identification: Klebsiella pneumoniae",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["EUCAST_RULES"], CITATIONS["CLSI_M100"]],
    },
    {
        "rule_id": "RULE-BLAC-ACQ-001",
        "description": "Aminopenicillin resistance conferred by acquired narrow/broad spectrum beta-lactamases.",
        "antibiotics": ["Ampicillin"],
        "supported_organisms": ["Escherichia coli", "Enterobacterales"],
        "target_mechanisms": ["blaTEM", "blaSHV", "blaOXA-1"],
        "evidence_requirements": "Identity >= 90.0%, Coverage >= 80.0%",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]],
    },
    {
        "rule_id": "RULE-BLI-RES-001",
        "description": "Inhibitor-resistant beta-lactamase or carbapenemase conferring Piperacillin-tazobactam resistance.",
        "antibiotics": ["Piperacillin-tazobactam"],
        "supported_organisms": ["Klebsiella pneumoniae", "Escherichia coli"],
        "target_mechanisms": ["blaKPC", "blaNDM", "blaOXA-48", "blaOXA-1", "Inhibitor-resistant TEM/SHV"],
        "evidence_requirements": "Identity >= 90.0%, Coverage >= 80.0%",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]],
    },
    {
        "rule_id": "RULE-MRSA-001",
        "description": "Methicillin/oxacillin/cefoxitin resistance in Staphylococcus aureus conferred by mecA/mecC (PBP2a).",
        "antibiotics": ["Oxacillin", "Cefoxitin"],
        "supported_organisms": ["Staphylococcus aureus"],
        "target_mechanisms": ["mecA", "mecC"],
        "evidence_requirements": "Identity >= 90.0%, Coverage >= 80.0%",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["CLSI_M100"], CITATIONS["SANCHES_MRSA"]],
    },
    {
        "rule_id": "RULE-FQ-001",
        "description": "Fluoroquinolone resistance conferred by DNA gyrase/topoisomerase mutations or PMQR determinants.",
        "antibiotics": ["Ciprofloxacin", "Levofloxacin"],
        "supported_organisms": ["Klebsiella pneumoniae", "Escherichia coli"],
        "target_mechanisms": ["gyrA", "parC", "qnr", "oqxAB", "aac(6')-Ib-cr"],
        "evidence_requirements": "Identity >= 90.0%, Coverage >= 80.0%",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]],
    },
    {
        "rule_id": "RULE-AG-001",
        "description": "Aminoglycoside resistance conferred by modifying enzymes or 16S methyltransferases.",
        "antibiotics": ["Gentamicin", "Tobramycin", "Amikacin"],
        "supported_organisms": ["Klebsiella pneumoniae", "Escherichia coli"],
        "target_mechanisms": ["aac", "ant", "aph", "armA", "rmt"],
        "evidence_requirements": "Identity >= 90.0%, Coverage >= 80.0%",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]],
    },
    {
        "rule_id": "RULE-TET-001",
        "description": "Tetracycline resistance conferred by efflux pumps or ribosomal protection proteins.",
        "antibiotics": ["Tetracycline"],
        "supported_organisms": ["Klebsiella pneumoniae", "Escherichia coli"],
        "target_mechanisms": ["tet(A)", "tet(B)", "tet(M)", "tet(O)"],
        "evidence_requirements": "Identity >= 90.0%, Coverage >= 80.0%",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]],
    },
    {
        "rule_id": "RULE-SXT-001",
        "description": "Folate antagonist resistance conferred by sul and dfr alleles.",
        "antibiotics": ["Trimethoprim-sulfamethoxazole"],
        "supported_organisms": ["Klebsiella pneumoniae", "Escherichia coli"],
        "target_mechanisms": ["sul1", "sul2", "dfrA"],
        "evidence_requirements": "Identity >= 90.0%, Coverage >= 80.0%",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]],
    },
    {
        "rule_id": "RULE-COL-001",
        "description": "Acquired colistin resistance conferred by mcr phosphoethanolamine transferase genes.",
        "antibiotics": ["Colistin"],
        "supported_organisms": ["Klebsiella pneumoniae", "Escherichia coli", "Enterobacterales"],
        "target_mechanisms": ["mcr-1 through mcr-10"],
        "evidence_requirements": "Identity >= 90.0%, Coverage >= 80.0%",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["POIREL_COLISTIN"], CITATIONS["CLSI_M100"]],
    },
    {
        "rule_id": "RULE-INTR-GN-VANCO",
        "description": "Intrinsic resistance of Gram-negative bacteria to glycopeptides due to outer membrane barrier.",
        "antibiotics": ["Vancomycin"],
        "supported_organisms": ["Gram-negative bacteria"],
        "target_mechanisms": ["Intrinsic outer membrane impermeability"],
        "evidence_requirements": "Gram-negative species identification",
        "effect": "Resistance predicted",
        "citations": [CITATIONS["EUCAST_RULES"]],
    },
    {
        "rule_id": "RULE-SUSC-001",
        "description": "Susceptibility prediction criteria: Supported organism, warning-free assembly, zero detected acquired determinants or intrinsic resistance for this drug class.",
        "antibiotics": ["Selected supported panel drugs"],
        "supported_organisms": ["Klebsiella pneumoniae", "Escherichia coli", "Staphylococcus aureus"],
        "target_mechanisms": ["Absence of all known acquired resistance determinants"],
        "evidence_requirements": "Clean assembly QC, supported species context",
        "effect": "Susceptibility predicted",
        "citations": [CITATIONS["CLSI_M100"], CITATIONS["EUCAST_RULES"]],
    },
    {
        "rule_id": "RULE-INDET-001",
        "description": "Default state for unsupported species, ambiguous findings, conflicting evidence, or assembly warnings.",
        "antibiotics": ["Any"],
        "supported_organisms": ["Universal"],
        "target_mechanisms": ["Uncharacterized or insufficient evidence"],
        "evidence_requirements": "Missing, conflicting, or borderline evidence",
        "effect": "Indeterminate",
        "citations": [CITATIONS["CLSI_M100"]],
    },
]


def get_documented_rules() -> list[dict[str, Any]]:
    """Return all explicit rule definitions with citations and scopes."""
    return RULES_TABLE


def _match_gene_prefix(gene: str, prefixes: list[str]) -> bool:
    """Check if gene symbol starts with or contains any of the prefixes (case-insensitive)."""
    gene_upper = gene.upper()
    return any(p.upper() in gene_upper for p in prefixes)


def interpret_evidence(
    detections: list[dict[str, Any]],
    organism: str | None,
    genome_metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Interpret detected AMR determinants into antibiotic susceptibility status.

    Strict output constraint:
    Each antibiotic receives exactly one of:
    - 'Resistance predicted'
    - 'Susceptibility predicted'
    - 'Indeterminate'

    Returns:
        list of dicts containing:
            - antibiotic (str)
            - drug_class (str)
            - status (str)
            - rationale (str)
            - evidence (list[str])
            - rule_id (str)
            - citations (list[str])
    """
    interpretations: list[dict[str, Any]] = []

    # Normalize organism
    org_str = (organism or "").strip().lower()
    is_klebsiella = "klebsiella" in org_str
    is_ecoli = "escherichia" in org_str or "e. coli" in org_str or "e.coli" in org_str
    is_saureus = "staphylococcus" in org_str or "s. aureus" in org_str or "s.aureus" in org_str
    is_gram_negative = is_klebsiella or is_ecoli or "enterobacter" in org_str or "pseudomonas" in org_str or "acinetobacter" in org_str
    is_supported_species = is_klebsiella or is_ecoli or is_saureus

    # Partition detections: high-confidence vs borderline/insufficient evidence
    high_conf_detections = []
    borderline_detections = []

    for d in detections:
        ident = d.get("identity", 0.0)
        cov = d.get("coverage", 0.0)
        if ident >= 90.0 and cov >= 80.0:
            high_conf_detections.append(d)
        else:
            borderline_detections.append(d)

    def find_high_conf(prefixes: list[str]) -> list[dict[str, Any]]:
        return [d for d in high_conf_detections if _match_gene_prefix(d.get("gene_symbol", ""), prefixes)]

    def find_borderline(prefixes: list[str]) -> list[dict[str, Any]]:
        return [d for d in borderline_detections if _match_gene_prefix(d.get("gene_symbol", ""), prefixes)]

    carbapenemases = find_high_conf(["KPC", "NDM", "VIM", "IMP", "OXA-48", "OXA-181", "OXA-232", "IMI", "GES-2", "GES-5"])
    esbl_genes = find_high_conf(["CTX-M", "SHV-12", "SHV-2", "TEM-10", "TEM-12", "VEB", "PER"])
    all_beta_lactamases = find_high_conf(["bla", "mecA", "mecC", "ampC"])
    staph_mec = find_high_conf(["mecA", "mecC"])
    quinolone_markers = find_high_conf(["gyrA", "parC", "qnr", "oqxA", "oqxB", "aac(6')-Ib-cr"])
    aminoglycoside_markers = find_high_conf(["aac", "ant", "aph", "armA", "rmt"])
    tet_markers = find_high_conf(["tet"])
    sxt_markers = find_high_conf(["sul", "dfr"])
    colistin_markers = find_high_conf(["mcr"])

    has_assembly_warnings = len(genome_metrics.get("warnings", [])) > 0

    for drug_info in ANTIBIOTIC_PANEL:
        drug_name = drug_info["name"]
        drug_class = drug_info["class"]

        status = "Indeterminate"
        rationale = ""
        evidence_list: list[str] = []
        rule_id = "RULE-INDET-001"
        rule_citations = [CITATIONS["CLSI_M100"]]

        # -------------------------------------------------------------
        # 1. GRAM-NEGATIVE INTRINSIC RESISTANCE (VANCOMYCIN)
        # -------------------------------------------------------------
        if drug_name == "Vancomycin" and is_gram_negative:
            status = "Resistance predicted"
            rationale = "Intrinsic resistance: outer membrane permeability barrier in Gram-negative bacteria prevents glycopeptide entry."
            evidence_list = ["Gram-negative outer membrane barrier"]
            rule_id = "RULE-INTR-GN-VANCO"
            rule_citations = [CITATIONS["EUCAST_RULES"]]

        # -------------------------------------------------------------
        # 2. GRAM-POSITIVE BREAKPOINTS IN GRAM-NEGATIVES
        # -------------------------------------------------------------
        elif drug_name in ["Oxacillin", "Cefoxitin"] and is_gram_negative:
            status = "Indeterminate"
            rationale = "Oxacillin/cefoxitin breakpoint rules are defined for staphylococci, not applicable to Gram-negative species."
            evidence_list = []
            rule_id = "RULE-INDET-001"

        # -------------------------------------------------------------
        # 3. CARBAPENEMS
        # -------------------------------------------------------------
        elif drug_class == "Carbapenem":
            borderline_carb = find_borderline(["KPC", "NDM", "VIM", "IMP", "OXA-48", "OXA-181", "OXA-232"])
            if carbapenemases:
                status = "Resistance predicted"
                gene_names = [d["gene_symbol"] for d in carbapenemases]
                rationale = f"Detected high-confidence carbapenemase determinant(s): {', '.join(gene_names)}."
                evidence_list = [f"{d['gene_symbol']} ({d.get('sequence_name')}, id:{d.get('identity')}%, cov:{d.get('coverage')}%)" for d in carbapenemases]
                rule_id = "RULE-CARB-001"
                rule_citations = [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]]
            elif borderline_carb:
                # Conservative conflict handling: borderline hit cannot confirm resistance, but prevents susceptibility
                status = "Indeterminate"
                gene_names = [d["gene_symbol"] for d in borderline_carb]
                rationale = f"Conflicting/borderline carbapenemase evidence: {', '.join(gene_names)} (<90% identity or <80% coverage)."
                evidence_list = [f"{d['gene_symbol']} (borderline: id:{d.get('identity')}%, cov:{d.get('coverage')}%)" for d in borderline_carb]
                rule_id = "RULE-INDET-001"
            elif is_supported_species and not has_assembly_warnings:
                status = "Susceptibility predicted"
                rationale = f"Absence of carbapenemase determinants in verified {organism} assembly."
                evidence_list = ["Zero carbapenemase determinants detected"]
                rule_id = "RULE-SUSC-001"
                rule_citations = [CITATIONS["CLSI_M100"], CITATIONS["EUCAST_RULES"]]
            else:
                status = "Indeterminate"
                rationale = (
                    "No carbapenemase detected; susceptibility cannot be confirmed due to "
                    + ("assembly quality warnings" if has_assembly_warnings else "unsupported or unspecified species context")
                    + "."
                )
                rule_id = "RULE-INDET-001"

        # -------------------------------------------------------------
        # 4. 3rd & 4th GENERATION CEPHALOSPORINS
        # -------------------------------------------------------------
        elif drug_class.startswith("Cephalosporin"):
            cephp_res = carbapenemases or esbl_genes
            borderline_esbl = find_borderline(["CTX-M", "SHV", "TEM"])
            if cephp_res:
                status = "Resistance predicted"
                markers = carbapenemases + esbl_genes
                gene_names = [d["gene_symbol"] for d in markers]
                rationale = f"Detected ESBL or carbapenemase determinant: {', '.join(gene_names)}."
                evidence_list = [f"{d['gene_symbol']} ({d.get('sequence_name')}, id:{d.get('identity')}%)" for d in markers]
                rule_id = "RULE-ESBL-001"
                rule_citations = [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]]
            elif borderline_esbl:
                status = "Indeterminate"
                gene_names = [d["gene_symbol"] for d in borderline_esbl]
                rationale = f"Conflicting/borderline beta-lactamase evidence detected ({', '.join(gene_names)})."
                evidence_list = [f"{d['gene_symbol']} (borderline)" for d in borderline_esbl]
                rule_id = "RULE-INDET-001"
            elif is_supported_species and not has_assembly_warnings:
                status = "Susceptibility predicted"
                rationale = f"Absence of ESBL and carbapenemase determinants in verified {organism} assembly."
                evidence_list = ["Zero ESBL/carbapenemase determinants detected"]
                rule_id = "RULE-SUSC-001"
                rule_citations = [CITATIONS["CLSI_M100"], CITATIONS["EUCAST_RULES"]]
            else:
                status = "Indeterminate"
                rationale = "Cephalosporin susceptibility requires verified species context and warning-free assembly."
                rule_id = "RULE-INDET-001"

        # -------------------------------------------------------------
        # 5. AMPICILLIN
        # -------------------------------------------------------------
        elif drug_name == "Ampicillin":
            if is_klebsiella:
                status = "Resistance predicted"
                shv_genes = find_high_conf(["SHV"])
                if shv_genes:
                    gene_names = [d["gene_symbol"] for d in shv_genes]
                    rationale = f"Intrinsic resistance in Klebsiella pneumoniae mediated by chromosomal beta-lactamase ({', '.join(gene_names)})."
                    evidence_list = [f"{d['gene_symbol']} ({d.get('sequence_name')})" for d in shv_genes]
                else:
                    rationale = "Intrinsic resistance in Klebsiella pneumoniae: all isolates harbor chromosomal non-ESBL class A beta-lactamase."
                    evidence_list = ["Species intrinsic resistance rule"]
                rule_id = "RULE-AMP-INTR-001"
                rule_citations = [CITATIONS["EUCAST_RULES"], CITATIONS["CLSI_M100"]]
            elif all_beta_lactamases:
                status = "Resistance predicted"
                gene_names = [d["gene_symbol"] for d in all_beta_lactamases]
                rationale = f"Detected acquired beta-lactamase: {', '.join(gene_names)}."
                evidence_list = [f"{d['gene_symbol']} ({d.get('sequence_name')})" for d in all_beta_lactamases]
                rule_id = "RULE-BLAC-ACQ-001"
                rule_citations = [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]]
            elif is_ecoli and not has_assembly_warnings:
                status = "Susceptibility predicted"
                rationale = "Absence of acquired beta-lactamases in verified E. coli assembly."
                evidence_list = ["Zero beta-lactamase determinants detected"]
                rule_id = "RULE-SUSC-001"
                rule_citations = [CITATIONS["CLSI_M100"]]
            else:
                status = "Indeterminate"
                rationale = "Ampicillin susceptibility cannot be inferred without verified species context."
                rule_id = "RULE-INDET-001"

        # -------------------------------------------------------------
        # 6. PIPERACILLIN-TAZOBACTAM
        # -------------------------------------------------------------
        elif drug_name == "Piperacillin-tazobactam":
            bli_resistant = carbapenemases or find_high_conf(["OXA-1", "OXA-2", "TEM-30", "TEM-31", "SHV-10"])
            if bli_resistant:
                status = "Resistance predicted"
                gene_names = [d["gene_symbol"] for d in bli_resistant]
                rationale = f"Detected inhibitor-resistant beta-lactamase or carbapenemase: {', '.join(gene_names)}."
                evidence_list = [f"{d['gene_symbol']} ({d.get('sequence_name')})" for d in bli_resistant]
                rule_id = "RULE-BLI-RES-001"
                rule_citations = [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]]
            elif is_supported_species and not has_assembly_warnings and not esbl_genes:
                status = "Susceptibility predicted"
                rationale = "No inhibitor-resistant beta-lactamase, carbapenemase, or ESBL hyperproduction markers detected."
                evidence_list = ["Zero BLI-resistant markers detected"]
                rule_id = "RULE-SUSC-001"
                rule_citations = [CITATIONS["CLSI_M100"]]
            else:
                status = "Indeterminate"
                rationale = "Piperacillin-tazobactam susceptibility requires verified exclusion of inhibitor-resistant mutations and promoter variants."
                rule_id = "RULE-INDET-001"

        # -------------------------------------------------------------
        # 7. STAPHYLOCOCCUS: OXACILLIN & CEFOXITIN
        # -------------------------------------------------------------
        elif drug_name in ["Oxacillin", "Cefoxitin"]:
            if is_saureus:
                if staph_mec:
                    status = "Resistance predicted"
                    gene_names = [d["gene_symbol"] for d in staph_mec]
                    rationale = f"Methicillin resistance (MRSA) confirmed: detected PBP2a determinant {', '.join(gene_names)}."
                    evidence_list = [f"{d['gene_symbol']} ({d.get('sequence_name')})" for d in staph_mec]
                    rule_id = "RULE-MRSA-001"
                    rule_citations = [CITATIONS["CLSI_M100"], CITATIONS["SANCHES_MRSA"]]
                elif not has_assembly_warnings:
                    status = "Susceptibility predicted"
                    rationale = "Absence of mecA/mecC in verified S. aureus assembly indicates methicillin susceptibility (MSSA)."
                    evidence_list = ["Zero mecA/mecC detected"]
                    rule_id = "RULE-SUSC-001"
                    rule_citations = [CITATIONS["CLSI_M100"]]
                else:
                    status = "Indeterminate"
                    rationale = "S. aureus assembly quality warnings prevent reliable exclusion of mecA/mecC."
                    rule_id = "RULE-INDET-001"
            else:
                status = "Indeterminate"
                rationale = "Oxacillin/Cefoxitin rules strictly apply to Staphylococcus species."
                rule_id = "RULE-INDET-001"

        # -------------------------------------------------------------
        # 8. FLUOROQUINOLONES
        # -------------------------------------------------------------
        elif drug_class == "Fluoroquinolone":
            if quinolone_markers:
                status = "Resistance predicted"
                gene_names = [d["gene_symbol"] for d in quinolone_markers]
                rationale = f"Detected fluoroquinolone resistance marker(s): {', '.join(gene_names)}."
                evidence_list = [f"{d['gene_symbol']} ({d.get('sequence_name')})" for d in quinolone_markers]
                rule_id = "RULE-FQ-001"
                rule_citations = [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]]
            else:
                # Quinolone resistance can arise from single point mutations; cannot infer susceptibility without QRDR variant calling
                status = "Indeterminate"
                rationale = (
                    "No plasmid-mediated quinolone resistance determinants detected. However, "
                    "chromosomal QRDR (gyrA/parC) point mutations cannot be excluded without specialized variant calling."
                )
                evidence_list = ["No PMQR genes detected"]
                rule_id = "RULE-INDET-001"

        # -------------------------------------------------------------
        # 9. AMINOGLYCOSIDES
        # -------------------------------------------------------------
        elif drug_class == "Aminoglycoside":
            if aminoglycoside_markers:
                status = "Resistance predicted"
                gene_names = [d["gene_symbol"] for d in aminoglycoside_markers]
                rationale = f"Detected aminoglycoside-modifying enzyme or methyltransferase: {', '.join(gene_names)}."
                evidence_list = [f"{d['gene_symbol']} ({d.get('sequence_name')})" for d in aminoglycoside_markers]
                rule_id = "RULE-AG-001"
                rule_citations = [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]]
            elif is_supported_species and not has_assembly_warnings:
                status = "Susceptibility predicted"
                rationale = f"No aminoglycoside-modifying enzymes (AMEs) or 16S methyltransferases detected in {organism}."
                evidence_list = ["Zero aminoglycoside determinants detected"]
                rule_id = "RULE-SUSC-001"
                rule_citations = [CITATIONS["CLSI_M100"]]
            else:
                status = "Indeterminate"
                rationale = "Aminoglycoside susceptibility cannot be confirmed without complete species and QC context."
                rule_id = "RULE-INDET-001"

        # -------------------------------------------------------------
        # 10. TETRACYCLINES
        # -------------------------------------------------------------
        elif drug_class == "Tetracycline":
            if tet_markers:
                status = "Resistance predicted"
                gene_names = [d["gene_symbol"] for d in tet_markers]
                rationale = f"Detected tetracycline resistance determinant(s): {', '.join(gene_names)}."
                evidence_list = [f"{d['gene_symbol']} ({d.get('sequence_name')})" for d in tet_markers]
                rule_id = "RULE-TET-001"
                rule_citations = [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]]
            elif is_supported_species and not has_assembly_warnings:
                status = "Susceptibility predicted"
                rationale = f"No tetracycline efflux pumps or ribosomal protection genes detected in {organism}."
                evidence_list = ["Zero tetracycline determinants detected"]
                rule_id = "RULE-SUSC-001"
                rule_citations = [CITATIONS["CLSI_M100"]]
            else:
                status = "Indeterminate"
                rationale = "Tetracycline susceptibility requires verified species context."
                rule_id = "RULE-INDET-001"

        # -------------------------------------------------------------
        # 11. TRIMETHOPRIM-SULFAMETHOXAZOLE
        # -------------------------------------------------------------
        elif drug_name == "Trimethoprim-sulfamethoxazole":
            if sxt_markers:
                status = "Resistance predicted"
                gene_names = [d["gene_symbol"] for d in sxt_markers]
                rationale = f"Detected folate pathway resistance determinant(s): {', '.join(gene_names)}."
                evidence_list = [f"{d['gene_symbol']} ({d.get('sequence_name')})" for d in sxt_markers]
                rule_id = "RULE-SXT-001"
                rule_citations = [CITATIONS["CLSI_M100"], CITATIONS["NCBI_AMRFINDER"]]
            elif is_supported_species and not has_assembly_warnings:
                status = "Susceptibility predicted"
                rationale = f"No sul or dfr resistance determinants detected in {organism}."
                evidence_list = ["Zero sul/dfr determinants detected"]
                rule_id = "RULE-SUSC-001"
                rule_citations = [CITATIONS["CLSI_M100"]]
            else:
                status = "Indeterminate"
                rationale = "Folate antagonist susceptibility requires verified species context."
                rule_id = "RULE-INDET-001"

        # -------------------------------------------------------------
        # 12. COLISTIN
        # -------------------------------------------------------------
        elif drug_name == "Colistin":
            if colistin_markers:
                status = "Resistance predicted"
                gene_names = [d["gene_symbol"] for d in colistin_markers]
                rationale = f"Detected plasmid-mediated colistin resistance (mcr): {', '.join(gene_names)}."
                evidence_list = [f"{d['gene_symbol']} ({d.get('sequence_name')})" for d in colistin_markers]
                rule_id = "RULE-COL-001"
                rule_citations = [CITATIONS["POIREL_COLISTIN"], CITATIONS["CLSI_M100"]]
            else:
                # Absence of mcr NEVER implies colistin susceptibility due to chromosomal mgrB/pmrAB/phoPQ mutations
                status = "Indeterminate"
                rationale = (
                    "No mcr gene detected. However, colistin susceptibility cannot be inferred from gene absence alone "
                    "because chromosomal regulatory mutations (mgrB, pmrAB, phoPQ) are common and require phenotypic AST."
                )
                evidence_list = ["Zero plasmid mcr detected"]
                rule_id = "RULE-INDET-001"
                rule_citations = [CITATIONS["POIREL_COLISTIN"]]

        # Strict invariant assertion
        assert status in ["Resistance predicted", "Susceptibility predicted", "Indeterminate"], (
            f"Invalid status '{status}' generated for antibiotic '{drug_name}'"
        )

        interpretations.append({
            "antibiotic": drug_name,
            "drug_class": drug_class,
            "status": status,
            "rationale": rationale,
            "evidence": evidence_list,
            "rule_id": rule_id,
            "citations": rule_citations,
        })

    return interpretations
