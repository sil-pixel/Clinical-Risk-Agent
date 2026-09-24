"""Resolve user-supplied research PDFs to PubMed IDs without indexing PDF text."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import subprocess
import time
import urllib.parse
from pathlib import Path

from pypdf import PdfReader

DOI = re.compile(r"10\.\d{4,9}/[^\s<>;,]+", re.IGNORECASE)


def _doi_on_first_page(path: Path) -> str | None:
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    text = PdfReader(path).pages[0].extract_text() or ""
    matches = DOI.findall(text)
    if not matches:
        return None
    # A PDF can cite other publications near its header. The first DOI is a
    # candidate identity only; PubMed verification remains mandatory.
    return matches[0].rstrip(".)]}").lower()


def _pubmed_match(doi: str) -> tuple[str, ...]:
    parameters = urllib.parse.urlencode({
        "db": "pubmed", "term": f"{doi}[DOI]", "retmode": "json", "retmax": 5,
    })
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + parameters
    # macOS curl uses the machine's trusted corporate/system CA store; never
    # disable TLS verification to work around Python CA configuration.
    response = subprocess.run(
        ["curl", "-fsSL", "--max-time", "20", "-A", "ClinicalRiskResearch/0.1", url],
        check=True, capture_output=True, text=True,
    )
    payload = json.loads(response.stdout)
    return tuple(payload["esearchresult"]["idlist"])


def discover(directory: Path, *, online: bool) -> list[dict[str, object]]:
    papers = sorted(directory.glob("*.pdf"))
    if not papers:
        raise ValueError("No research PDFs found")
    matches: dict[str, tuple[str, ...]] = {}
    records = []
    for path in papers:
        doi = _doi_on_first_page(path)
        if doi and online and doi not in matches:
            matches[doi] = _pubmed_match(doi)
            time.sleep(0.4)  # Below the unauthenticated NCBI 3-requests/s limit.
        records.append({
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "candidate_doi": doi,
            "pubmed_ids": list(matches.get(doi, ())) if doi else [],
            "status": ("pubmed_candidate" if doi and matches.get(doi)
                       else "needs_manual_identifier_check"),
        })
    return records


def main() -> None:
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path,
                        default=repository / "data" / "Research Papers")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--from-existing", action="store_true",
                        help="Regenerate the draft manifest from an existing discovery inventory")
    parser.add_argument("--output", type=Path,
                        default=repository / "data" / "indexes" / "rag_pdf_discovery.json")
    parser.add_argument("--manifest-output", type=Path,
                        default=repository / "data" / "indexes" / "rag_source_manifest_draft.json")
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = (repository / "data" / "indexes").resolve()
    if allowed not in output.parents:
        raise ValueError("Discovery output must be inside data/indexes")
    if args.from_existing:
        records = json.loads(output.read_text(encoding="utf-8"))["records"]
    else:
        records = discover(args.directory, online=args.online)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not args.from_existing:
        output.write_text(json.dumps({
            "schema_version": 1,
            "pdfs_are_discovery_only": True,
            "records": records,
        }, indent=2), encoding="utf-8")
    manifest_output = args.manifest_output.resolve()
    if allowed not in manifest_output.parents:
        raise ValueError("Draft manifest output must be inside data/indexes")
    pmids = sorted({pmid for record in records for pmid in record["pubmed_ids"]})
    manifest_output.write_text(json.dumps({
        "schema_version": 1,
        "sources": [{
            "pmid": pmid,
            "topic": "",
            "study_design": "",
            "reviewer": "",
            "reviewed_on": "",
            "appraisal": {"passed": False, "score": 0.0, "rubric_version": ""},
        } for pmid in pmids],
    }, indent=2), encoding="utf-8")
    print(f"Inspected {len(records)} PDFs; PubMed matches: "
          f"{sum(item['status'] == 'pubmed_candidate' for item in records)}")
    print(f"Discovery inventory: {output}")
    print(f"Unreviewed source manifest: {manifest_output}")


if __name__ == "__main__":
    main()
