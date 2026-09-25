"""Export a source-and-question-only packet for independent gold review."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data/indexes/rag_corpus_manifest.json"
WORKSHEET = ROOT / "agent_docs/RAG_GENERAL_ASSOCIATION_GOLD_INDEPENDENT_REVIEW_WORKSHEET.json"
OUTPUT = ROOT / "agent_docs/RAG_GOLD_21_SOURCE_BLINDED_PACKET.json"


def main() -> None:
    corpus_bytes = CORPUS.read_bytes()
    corpus = json.loads(corpus_bytes)
    worksheet = json.loads(WORKSHEET.read_text(encoding="utf-8"))
    sources = corpus["snapshots"]["document"]["sources"]
    pmids = worksheet["source_universe"]
    by_pmid = {source["pmid"]: source for source in sources}
    if len(pmids) != len(set(pmids)) or set(pmids) != set(by_pmid):
        raise ValueError("Worksheet source universe differs from active corpus")
    cases = worksheet["cases"]
    if len(cases) != len({case["id"] for case in cases}):
        raise ValueError("Duplicate review case ID")
    packet = {
        "schema_version": 1,
        "status": "blinded_human_first_pass_packet",
        "corpus_manifest_sha256": hashlib.sha256(corpus_bytes).hexdigest(),
        "source_count": len(pmids),
        "case_count": len(cases),
        "instructions": (
            "Read the linked PubMed abstracts. For every case, independently assign "
            "source-level grades 0/1/2, evidence spans and a bounded answer in the "
            "separate blank worksheet. Do not inspect assistant or AI judgments, "
            "appraisals, retrieval rankings or benchmark results until the first "
            "pass is saved. Grade 2 directly answers the exact exposure/outcome; "
            "grade 1 is limited context; unlisted sources are grade 0. "
            "No adequate direct source means no grade 2 and a null answer."
        ),
        "sources": [
            {
                "pmid": pmid,
                "title": by_pmid[pmid]["title"],
                "journal": by_pmid[pmid]["publication"],
                "published_on": by_pmid[pmid]["published_on"],
                "doi": by_pmid[pmid]["doi"],
                "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            }
            for pmid in pmids
        ],
        "cases": [{"id": case["id"], "query": case["query"]} for case in cases],
    }
    OUTPUT.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(pmids)} sources and {len(cases)} unlabeled cases to {OUTPUT}")


if __name__ == "__main__":
    main()
