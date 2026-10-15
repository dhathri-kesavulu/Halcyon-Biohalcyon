# Biohalcyon Genome Firewall

> **Bacterial Genome Resistance-Evidence Analysis Prototype**  
> *A transparent, audited antimicrobial resistance (AMR) genomic interpretation backend and provenance tracking engine.*

---

##  Regulatory & Clinical Disclaimer

**RESEARCH USE ONLY.**  
Genome Firewall is a prototype developed for hackathon demonstration and exploratory bioinformatics research. It has **NOT** undergone clinical validation or regulatory clearance (FDA, CE-IVD) and **DOES NOT REPLACE** standardized clinical laboratory phenotypic Antimicrobial Susceptibility Testing (AST) such as broth microdilution, disk diffusion, or ETEST. All predictions are algorithmic interpretations of assembled genomic sequences and must never be used to direct clinical patient care or therapy selection.

---

##  Backend Architectural Principles & Guarantees

1. **Strict Tripartite Classification**:
   Every evaluated antibiotic strictly receives one of three statuses:
   - `Resistance predicted`: High-confidence detection (≥90% sequence identity, ≥80% reference coverage) of a verified resistance determinant or intrinsic resistance mechanism.
   - `Susceptibility predicted`: Permitted **only** when the organism is fully supported, assembly quality checks pass with zero warnings, the panel completely captures all known resistance mechanisms for that drug class, and zero resistance markers are detected.
   - `Indeterminate`: Assigned for uncharacterized species, assemblies with quality warnings, ambiguous/borderline sequence hits, unsupported species-drug combinations, or drugs where gene absence does not rule out resistance (e.g., Colistin or Fluoroquinolones requiring chromosomal QRDR variant calling).

2. **Absence of Evidence is NOT Evidence of Absence**:
   Missing resistance genes **never** automatically implies susceptibility. For instance, the absence of plasmid-mediated `mcr` genes does *not* imply Colistin susceptibility because chromosomal two-component regulatory mutations (`pmrA/B`, `phoP/Q`, `mgrB`) are frequent drivers of colistin resistance that cannot be ruled out from gene presence alone.

3. **Conservative Conflict & Borderline Evidence Handling**:
   - Determinants with borderline alignment metrics (identity < 90% or coverage < 80%) do not confer resistance, but prevent susceptibility prediction -> categorized as `Indeterminate` with explicit rationale.
   - Contradictory evidence (e.g. conflicting mutation calls or inhibitor claims) defaults conservatively to `Indeterminate`.

4. **Verifiable Engine & Explicit Demo Mode**:
   - Preferred live engine: **NCBI AMRFinderPlus** (`amrfinder`), utilized only if the binary, its version, supported CLI options via `--help`, and a compatible AMRFinder database are verified.
   - If the live engine or database is unavailable, live analysis returns a structured `UNAVAILABLE` execution status.
   - Precomputed demonstration fixtures are permitted **only** when demo mode is explicitly selected (`is_demo=True` or selecting a benchmark isolate from `data/demo/`). Fixtures are **never** silently substituted during live analysis.

5. **Strict Input Validation & Non-Silent Rejection**:
   `backend/genome.py` rejects empty files, whitespace-only files, malformed FASTA syntax, records with empty sequence length, and sequences with no valid nucleotide content. Ambiguous IUPAC bases are explicitly tracked and excluded from standard GC calculations; invalid input is never silently repaired.

6. **Auditable Rules with Literature Citations**:
   The rulebook (`v1.0.0`) in `backend/interpreter.py` documents explicit citations (CLSI M100:2024, EUCAST Expert Rules v3.3, NCBI AMRFinderPlus / Feldgarden et al. 2021) for every rule. No arbitrary confidence percentages or unsupported associations are used.

7. **Decoupled Backend Public Contract**:
   The frontend communicates strictly through the public API:
   ```python
   analyze_genome(
       fasta_path: str,
       sample_id: str,
       organism: str | None = None,
       is_demo: bool = False,
       demo_id: str | None = None
   ) -> dict[str, Any]
   ```

---

##  Repository Structure

```
Halcyon/
├── app.py                     # Streamlit frontend (calls backend.pipeline.analyze_genome)
├── backend/
│   ├── __init__.py            # Exposes public analyze_genome API
│   ├── pipeline.py            # Main analysis orchestrator adhering to stable schema contract
│   ├── genome.py              # Biopython FASTA parser, QC metrics, GC%, and input validation
│   ├── detector.py            # AMRFinderPlus engine verification, safe subprocess, and demo fixtures
│   ├── interpreter.py         # Auditable rulebook (v1.0.0) mapping hits to tripartite status with citations
│   └── report.py              # Provenance tracking, UTF-8 sanitized JSON, Markdown, CSV, and PDF generators
├── data/
│   └── demo/                  # Benchmark assemblies, fixtures, and catalog.json
├── tests/
│   ├── test_genome.py         # QC metrics, rejection of empty/malformed inputs, ambiguous base tests
│   ├── test_detector.py       # Engine verification, unavailable status, TSV parsing, and demo mode tests
│   ├── test_interpreter.py    # Strict 3-state output, citations, and conflict handling tests
│   ├── test_report.py         # JSON, CSV, and Markdown audit report generation tests
│   ├── test_pdf_report.py     # PDF signature, text extraction, tripartite statuses, and multi-page pagination tests
│   ├── test_pipeline.py       # End-to-end contract, unavailable fallback, and schema consistency tests
│   └── test_integration.py    # Multi-isolate benchmark and live custom upload integration tests
├── pytest.ini                 # Pytest configuration
├── requirements.txt           # Minimal core dependencies (including reportlab and pypdf)
└── README.md                  # Comprehensive backend documentation
```

---

##  Running Tests & Execution

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Full Test Suite
Run all 46 unit and integration tests across the test suites:
```bash
python -m pytest -v tests
```

### 3. Launch the Web Interface
```bash
streamlit run app.py
```

---

##  Result Schema Specification

The `analyze_genome` function returns a standardized dictionary:

```json
{
  "status": "SUCCESS",
  "errors": [],
  "warnings": [],
  "provenance": {
    "sample_id": "KP-KPC2-MDR",
    "input_sha256": "4b689...",
    "organism": "Klebsiella pneumoniae",
    "engine": "Precomputed Demonstration Fixture",
    "engine_version": "NCBI AMRFinderPlus v3.12.0 (Precomputed Reference)",
    "database_version": "NCBI AMR Database 2024-05-02.1",
    "rules_version": "1.0.0",
    "is_live": false,
    "mode_label": "Precomputed Demonstration Fixture (Demo Mode)",
    "timestamp_utc": "2026-10-15T09:45:00.000000+00:00"
  },
  "genome_metrics": {
    "sequence_count": 14,
    "total_length": 5350000,
    "gc_content_pct": 57.4,
    "ambiguous_count": 0,
    "ambiguous_pct": 0.0,
    "n50": 382142,
    "warnings": []
  },
  "detections": [
    {
      "gene_symbol": "blaKPC-2",
      "sequence_name": "contig_3",
      "scope": "core",
      "element_type": "AMR",
      "element_subtype": "BETA-LACTAM",
      "class": "BETA-LACTAM",
      "subclass": "CARBAPENEM",
      "method": "BLASTX",
      "identity": 100.0,
      "coverage": 100.0,
      "raw_evidence": { ... }
    }
  ],
  "interpretations": [
    {
      "antibiotic": "Meropenem",
      "drug_class": "Carbapenem",
      "status": "Resistance predicted",
      "rationale": "Detected high-confidence carbapenemase determinant(s): blaKPC-2.",
      "evidence": ["blaKPC-2 (contig_3, id:100.0%, cov:100.0%)"],
      "rule_id": "RULE-CARB-001",
      "citations": ["CLSI M100: 2024", "NCBI AMRFinderPlus / Feldgarden et al. 2021"]
    }
  ],
  "summary": {
    "total_antibiotics_evaluated": 19,
    "resistant_count": 16,
    "susceptible_count": 0,
    "indeterminate_count": 3
  },
  "limitations": [ ... ],
  "reports": {
    "json": "...",
    "markdown": "...",
    "csv": "..."
  },
  "disclaimer": "RESEARCH USE ONLY..."
}
```

---

##  Auditable Rules Catalog Summary (v1.0.0)

| Rule ID | Antibiotic / Drug Class | Target Determinants | Evidence Threshold | Citations | Status Assigned |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `RULE-CARB-001` | Carbapenems (Meropenem, Imipenem, Ertapenem) | `blaKPC`, `blaNDM`, `blaVIM`, `blaIMP`, `blaOXA-48` | Id ≥90%, Cov ≥80% | CLSI M100, Feldgarden et al. | `Resistance predicted` |
| `RULE-ESBL-001` | 3rd/4th Gen Cephalosporins (Ceftriaxone, Ceftazidime, Cefepime) | `blaCTX-M`, ESBL variants of `blaSHV`/`blaTEM` | Id ≥90%, Cov ≥80% | CLSI M100, Feldgarden et al. | `Resistance predicted` |
| `RULE-AMP-INTR-001`| Ampicillin | *K. pneumoniae* intrinsic chromosomal `blaSHV` | Species: *K. pneumoniae* | EUCAST Expert Rules, CLSI M100 | `Resistance predicted` |
| `RULE-MRSA-001` | Oxacillin, Cefoxitin | `mecA` / `mecC` in *Staphylococcus aureus* | Id ≥90%, Cov ≥80% | CLSI M100, Chambers & DeLeo | `Resistance predicted` |
| `RULE-FQ-001` | Fluoroquinolones (Ciprofloxacin, Levofloxacin) | `gyrA`/`parC` QRDR mutations, `qnr`, `oqxAB`, `aac(6')-Ib-cr` | Id ≥90%, Cov ≥80% | CLSI M100, Feldgarden et al. | `Resistance predicted` |
| `RULE-AG-001` | Aminoglycosides (Gentamicin, Tobramycin, Amikacin) | Aminoglycoside modifying enzymes (`aac`, `ant`, `aph`), `armA`, `rmt` | Id ≥90%, Cov ≥80% | CLSI M100, Feldgarden et al. | `Resistance predicted` |
| `RULE-TET-001` | Tetracycline | `tet(A)`, `tet(B)`, `tet(M)`, etc. | Id ≥90%, Cov ≥80% | CLSI M100, Feldgarden et al. | `Resistance predicted` |
| `RULE-SXT-001` | Trimethoprim-sulfamethoxazole | `sul1`, `sul2`, `dfrA` | Id ≥90%, Cov ≥80% | CLSI M100, Feldgarden et al. | `Resistance predicted` |
| `RULE-COL-001` | Colistin | `mcr-1` through `mcr-10` | Id ≥90%, Cov ≥80% | Poirel et al., CLSI M100 | `Resistance predicted` |
| `RULE-INTR-GN-VANCO`| Vancomycin | Gram-negative outer membrane barrier | Gram-negative taxonomy | EUCAST Expert Rules | `Resistance predicted` |
| `RULE-SUSC-001` | Selected panel drugs | Clean assembly QC, supported species, zero detected acquired determinants | Supported species + no QC warnings | CLSI M100, EUCAST Expert Rules | `Susceptibility predicted` |
| `RULE-INDET-001` | Any | Missing evidence, uncharacterized species, assembly warnings, or untested mechanisms | Insufficient or conflicting evidence | CLSI M100 | `Indeterminate` |
