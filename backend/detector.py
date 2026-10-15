"""Detection engine interface for NCBI AMRFinderPlus with explicit precomputed demo mode.

Strict operational requirements:
- Inspects executable availability, version, supported options, and database presence.
- Uses safe subprocess calls with argument lists, explicit timeouts, and captured streams (no shell=True).
- Retains relevant raw tool evidence alongside normalized findings.
- If live AMRFinderPlus or its database is unavailable, returns a clear 'UNAVAILABLE' status.
- Never fabricates detections or silently substitutes demo fixtures during live analysis.
- Precomputed demonstration fixtures are permitted ONLY when demo mode is explicitly requested.
"""

import json
import os
import shutil
import subprocess
import tempfile
from typing import Any


class DetectionEngineUnavailableError(RuntimeError):
    """Raised when live AMRFinderPlus is required but not installed or database is missing."""
    pass


def verify_amrfinder_engine() -> dict[str, Any]:
    """
    Check if NCBI AMRFinderPlus executable and compatible database are available.
    Inspects version and supported CLI options via --help rather than guessing.

    Returns:
        dict containing:
            - is_available (bool)
            - executable_path (str | None)
            - engine_version (str | None)
            - database_version (str | None)
            - supported_options (list[str])
            - status_message (str)
    """
    amrfinder_path = shutil.which("amrfinder")
    if not amrfinder_path:
        return {
            "is_available": False,
            "executable_path": None,
            "engine_version": None,
            "database_version": None,
            "supported_options": [],
            "status_message": (
                "NCBI AMRFinderPlus executable ('amrfinder') was not found on system PATH."
            ),
        }

    # Inspect version
    try:
        ver_proc = subprocess.run(
            [amrfinder_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        engine_ver = ver_proc.stdout.strip() or ver_proc.stderr.strip() or "Unknown"
    except Exception as exc:
        return {
            "is_available": False,
            "executable_path": amrfinder_path,
            "engine_version": None,
            "database_version": None,
            "supported_options": [],
            "status_message": f"Failed to execute 'amrfinder --version': {str(exc)}",
        }

    # Inspect supported CLI flags via --help
    supported_options: list[str] = []
    try:
        help_proc = subprocess.run(
            [amrfinder_path, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        help_text = help_proc.stdout + " " + help_proc.stderr
        for opt in ["--nucleotide", "-n", "--organism", "-O", "--output", "-o", "--database_version"]:
            if opt in help_text:
                supported_options.append(opt)
    except Exception:
        pass

    # Verify database initialization
    try:
        db_proc = subprocess.run(
            [amrfinder_path, "--database_version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        db_ver = db_proc.stdout.strip() if db_proc.returncode == 0 and db_proc.stdout.strip() else None
    except Exception:
        db_ver = None

    if not db_ver:
        return {
            "is_available": False,
            "executable_path": amrfinder_path,
            "engine_version": engine_ver,
            "database_version": None,
            "supported_options": supported_options,
            "status_message": (
                "AMRFinderPlus executable was found, but the required AMRFinder database is missing or uninitialized. "
                "Run 'amrfinder -u' to install or update the database."
            ),
        }

    return {
        "is_available": True,
        "executable_path": amrfinder_path,
        "engine_version": engine_ver,
        "database_version": db_ver,
        "supported_options": supported_options,
        "status_message": f"Live AMRFinderPlus {engine_ver} verified with database {db_ver}.",
    }


def _parse_amrfinder_tsv(tsv_path: str) -> list[dict[str, Any]]:
    """
    Parse AMRFinderPlus standard TSV output into normalized detection dicts
    while preserving raw evidence fields.
    """
    detections: list[dict[str, Any]] = []
    if not os.path.exists(tsv_path):
        return detections

    with open(tsv_path, "r", encoding="utf-8", errors="replace") as f:
        header = None
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if header is None:
                header = [h.strip() for h in parts]
                continue
            row = dict(zip(header, parts))

            # Parse numeric percentages safely
            try:
                ident_val = float(row.get("% Identity to reference sequence", 100.0) or 100.0)
            except (ValueError, TypeError):
                ident_val = 0.0

            try:
                cov_val = float(row.get("% Coverage of reference sequence", 100.0) or 100.0)
            except (ValueError, TypeError):
                cov_val = 0.0

            gene_sym = row.get("Gene symbol") or row.get("Element symbol", "Unknown")
            seq_name = row.get("Contig id") or row.get("Sequence name", "Unknown")

            detections.append({
                "gene_symbol": gene_sym,
                "sequence_name": seq_name,
                "scope": row.get("Scope", "core"),
                "element_type": row.get("Element type", "AMR"),
                "element_subtype": row.get("Element subtype", "AMR"),
                "class": row.get("Class", "UNKNOWN"),
                "subclass": row.get("Subclass", "UNKNOWN"),
                "method": row.get("Method", "BLASTX"),
                "identity": round(ident_val, 2),
                "coverage": round(cov_val, 2),
                "phenotype": row.get("Subclass", ""),
                "raw_evidence": {
                    "raw_row": row,
                    "target_length": row.get("Target length"),
                    "reference_length": row.get("Reference sequence length"),
                    "start": row.get("Start"),
                    "stop": row.get("Stop"),
                    "strand": row.get("Strand"),
                    "accession": row.get("Accession of closest sequence"),
                }
            })
    return detections


def run_detection(
    fasta_path: str,
    sha256_hash: str,
    organism: str | None = None,
    is_demo: bool = False,
    demo_id: str | None = None,
    demo_fixtures_dir: str | None = None,
) -> dict[str, Any]:
    """
    Run AMR detection.

    Behavior:
    1. If is_demo is True:
       Loads the precomputed reference fixture explicitly. Fixtures are clearly labeled
       as precomputed and never presented as live analysis.
    2. If is_demo is False (live analysis):
       Verifies AMRFinderPlus executable, database, and supported options.
       If unavailable, returns a structured status='UNAVAILABLE' dictionary.
       NEVER silently substitutes precomputed fixtures during live analysis.

    Returns:
        dict containing:
            - status (str): 'SUCCESS', 'UNAVAILABLE', or 'FAILED'
            - is_live (bool)
            - engine (str)
            - engine_version (str | None)
            - database_version (str | None)
            - mode_label (str)
            - detections (list[dict])
            - error (str | None)
    """
    # -------------------------------------------------------------
    # Explicit Demo Mode
    # -------------------------------------------------------------
    if is_demo:
        if demo_fixtures_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            demo_fixtures_dir = os.path.join(base_dir, "data", "demo")

        catalog_path = os.path.join(demo_fixtures_dir, "catalog.json")
        if not os.path.exists(catalog_path):
            return {
                "status": "FAILED",
                "is_live": False,
                "engine": "Precomputed Demonstration Fixture",
                "engine_version": None,
                "database_version": None,
                "mode_label": "Precomputed Demonstration Fixture",
                "detections": [],
                "error": f"Demo catalog not found at {catalog_path}",
            }

        with open(catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)

        filename = os.path.basename(fasta_path)
        matched_entry = None

        for entry in catalog.get("fixtures", []):
            if (
                (demo_id and entry.get("id") == demo_id)
                or entry.get("sha256") == sha256_hash
                or entry.get("filename") == filename
            ):
                matched_entry = entry
                break

        if not matched_entry:
            return {
                "status": "FAILED",
                "is_live": False,
                "engine": "Precomputed Demonstration Fixture",
                "engine_version": None,
                "database_version": None,
                "mode_label": "Precomputed Demonstration Fixture",
                "detections": [],
                "error": (
                    f"Sample (ID: {demo_id or 'N/A'}, file: {filename}) does not match any registered demo fixture."
                ),
            }

        fixture_json_path = os.path.join(demo_fixtures_dir, matched_entry["fixture_file"])
        if not os.path.exists(fixture_json_path):
            return {
                "status": "FAILED",
                "is_live": False,
                "engine": "Precomputed Demonstration Fixture",
                "engine_version": None,
                "database_version": None,
                "mode_label": "Precomputed Demonstration Fixture",
                "detections": [],
                "error": f"Fixture file not found: {fixture_json_path}",
            }

        with open(fixture_json_path, "r", encoding="utf-8") as f:
            fixture_data = json.load(f)

        # Standardize detections to ensure raw_evidence, contig_id, and sequence_name exist
        normalized_detections = []
        raw_dets = fixture_data.get("detections") or fixture_data.get("detected_evidence") or []
        for d in raw_dets:
            d_copy = dict(d)
            seq_name = d_copy.get("sequence_name") or d_copy.get("contig_id") or "contig_01"
            d_copy["sequence_name"] = seq_name
            d_copy["contig_id"] = seq_name
            d_copy["start"] = d_copy.get("start", 0)
            d_copy["stop"] = d_copy.get("stop", 0)
            d_copy["strand"] = d_copy.get("strand", "+")
            if "raw_evidence" not in d_copy:
                d_copy["raw_evidence"] = {
                    "source": "precomputed_reference_fixture",
                    "fixture_sample_id": matched_entry.get("id"),
                    "start": d_copy["start"],
                    "stop": d_copy["stop"],
                    "strand": d_copy["strand"],
                }
            normalized_detections.append(d_copy)

        return {
            "status": "SUCCESS",
            "is_live": False,
            "engine": "Precomputed Demonstration Fixture",
            "engine_version": fixture_data.get(
                "engine_version", "NCBI AMRFinderPlus v3.12.0 (Precomputed Reference)"
            ),
            "database_version": fixture_data.get(
                "database_version", "NCBI AMRFinder DB 2024-05-02.1"
            ),
            "mode_label": "Precomputed Demonstration Fixture (Demo Mode)",
            "detections": normalized_detections,
            "error": None,
            "fixture_id": matched_entry.get("id"),
        }

    # -------------------------------------------------------------
    # Live Analysis Path (Strictly Verified, No Silent Fallback)
    # -------------------------------------------------------------
    engine_status = verify_amrfinder_engine()

    if not engine_status["is_available"]:
        return {
            "status": "UNAVAILABLE",
            "is_live": False,
            "engine": "NCBI AMRFinderPlus",
            "engine_version": engine_status.get("engine_version"),
            "database_version": engine_status.get("database_version"),
            "mode_label": "Live Detection Engine Unavailable",
            "detections": [],
            "error": engine_status["status_message"],
        }

    exec_path = engine_status["executable_path"]
    supported_opts = set(engine_status.get("supported_options", []))

    # Build safe command argument list
    with tempfile.NamedTemporaryFile(suffix=".amrfinder.tsv", delete=False) as tmp_out:
        output_tsv = tmp_out.name

    cmd = [exec_path]
    if "--nucleotide" in supported_opts:
        cmd.extend(["--nucleotide", fasta_path])
    elif "-n" in supported_opts:
        cmd.extend(["-n", fasta_path])
    else:
        cmd.extend(["--nucleotide", fasta_path])

    if "--output" in supported_opts:
        cmd.extend(["--output", output_tsv])
    elif "-o" in supported_opts:
        cmd.extend(["-o", output_tsv])
    else:
        cmd.extend(["--output", output_tsv])

    if organism and ("--organism" in supported_opts or "-O" in supported_opts):
        # Format organism: e.g. 'Klebsiella pneumoniae' -> 'Klebsiella_pneumoniae'
        org_clean = organism.strip().replace(" ", "_")
        cmd.extend(["--organism", org_clean])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if proc.returncode != 0:
            err_details = proc.stderr.strip() or proc.stdout.strip() or f"Exit code {proc.returncode}"
            return {
                "status": "FAILED",
                "is_live": True,
                "engine": "NCBI AMRFinderPlus (Live)",
                "engine_version": engine_status["engine_version"],
                "database_version": engine_status["database_version"],
                "mode_label": "Live AMRFinderPlus Engine Execution",
                "detections": [],
                "error": f"AMRFinderPlus execution failed: {err_details}",
            }

        detections = _parse_amrfinder_tsv(output_tsv)
        return {
            "status": "SUCCESS",
            "is_live": True,
            "engine": "NCBI AMRFinderPlus (Live)",
            "engine_version": engine_status["engine_version"],
            "database_version": engine_status["database_version"],
            "mode_label": "Live AMRFinderPlus Engine Execution",
            "detections": detections,
            "error": None,
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "FAILED",
            "is_live": True,
            "engine": "NCBI AMRFinderPlus (Live)",
            "engine_version": engine_status["engine_version"],
            "database_version": engine_status["database_version"],
            "mode_label": "Live AMRFinderPlus Engine Execution",
            "detections": [],
            "error": "AMRFinderPlus execution timed out (exceeded 300 seconds).",
        }
    except Exception as exc:
        return {
            "status": "FAILED",
            "is_live": True,
            "engine": "NCBI AMRFinderPlus (Live)",
            "engine_version": engine_status["engine_version"],
            "database_version": engine_status["database_version"],
            "mode_label": "Live AMRFinderPlus Engine Execution",
            "detections": [],
            "error": f"Failed to execute AMRFinderPlus: {str(exc)}",
        }
    finally:
        if os.path.exists(output_tsv):
            try:
                os.remove(output_tsv)
            except OSError:
                pass
