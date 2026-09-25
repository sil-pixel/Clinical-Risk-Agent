"""Build both versioned Qdrant collections from reviewed public PubMed sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import date
from pathlib import Path

from clinical_risk_agent.rag.corpus import source_rejection_reasons
from clinical_risk_agent.rag.index import BM25Index, CorpusSnapshot
from clinical_risk_agent.rag.ingestion import (
    fetch_approved_pubmed_sources,
    load_approved_sources,
)
from clinical_risk_agent.rag.medcpt import MedCPTEncoder
from clinical_risk_agent.rag.pubmed import PubMedClient
from clinical_risk_agent.rag.qdrant_index import QdrantScientificIndex


def _collection_name(strategy: str, version: str) -> str:
    return f"scientific_{strategy}_{version.replace('-', '_')}"


def _system_trust_fetch(url: str) -> bytes:
    """Use the host's trusted CA store without disabling TLS verification."""
    return subprocess.run(
        ["curl", "-fsSL", "--max-time", "30", "-A", "ClinicalRiskResearch/0.1", url],
        check=True, capture_output=True,
    ).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--query-model", type=Path, required=True)
    parser.add_argument("--query-sha256", required=True)
    parser.add_argument("--article-model", type=Path, required=True)
    parser.add_argument("--article-sha256", required=True)
    parser.add_argument(
        "--qdrant-path", type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "indexes" / "qdrant",
    )
    args = parser.parse_args()
    from qdrant_client import QdrantClient

    today = date.today()
    approved = load_approved_sources(args.manifest, today=today)
    reviewed_manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    sources = fetch_approved_pubmed_sources(
        approved, today=today, client=PubMedClient(fetch=_system_trust_fetch)
    )
    rejected = {
        source.pmid: source_rejection_reasons(source, today=today)
        for source in sources if source_rejection_reasons(source, today=today)
    }
    if rejected:
        raise ValueError(f"Some approved sources failed admission: {rejected}")
    encoder = MedCPTEncoder.from_local(
        args.query_model, args.article_model,
        query_sha256=args.query_sha256, article_sha256=args.article_sha256,
    )
    snapshots = {
        strategy: CorpusSnapshot.build(
            sources, strategy=strategy, today=today,
            count_tokens=encoder.count_article_tokens,
        ) for strategy in ("document", "hierarchical")
    }
    path = args.qdrant_path.resolve()
    allowed = (Path(__file__).resolve().parents[1] / "data" / "indexes").resolve()
    if path != allowed and allowed not in path.parents:
        raise ValueError("Local Qdrant path must be inside data/indexes")
    client = QdrantClient(path=str(path))
    try:
        names = {strategy: _collection_name(strategy, snapshot.version)
                 for strategy, snapshot in snapshots.items()}
        if any(client.collection_exists(name) for name in names.values()):
            raise ValueError("A versioned collection already exists; no overwrite attempted")
        for strategy, snapshot in snapshots.items():
            lexical = BM25Index(snapshot)
            QdrantScientificIndex(
                client, names[strategy], encoder, lexical
            ).build(snapshot, today=today)
    finally:
        client.close()
    # Only public publication content is serialized. The BM25 index is rebuilt
    # deterministically from these immutable passages, never from runtime queries.
    manifest = {
        "schema_version": 1,
        "built_on": today.isoformat(),
        "source_pmids": [item.pmid for item in approved],
        "source_manifest": str(args.manifest.resolve()),
        "purpose": reviewed_manifest.get("purpose"),
        "source_review": {
            item["pmid"]: {
                "reviewer": item["reviewer"],
                "reviewed_on": item["reviewed_on"],
                "release_status": item.get("release_status", "unspecified"),
                "bounded_use": item.get("bounded_use"),
                "appraisal_assessor": item.get("appraisal_assessor", "unspecified"),
            } for item in reviewed_manifest["sources"]
        },
        "bounded_use_enforcement": "provenance_only_not_query_enforced",
        "query_model_sha256": args.query_sha256,
        "article_model_sha256": args.article_sha256,
        "collections": names,
        "snapshots": {
            strategy: {
                "corpus_version": snapshot.version,
                "index_version": f"bm25-{snapshot.version}",
                "sources": [asdict(source) for source in snapshot.sources],
                "passages": [asdict(passage) for passage in snapshot.passages],
            } for strategy, snapshot in snapshots.items()
        },
    }
    output = allowed / "rag_corpus_manifest.json"
    if output.exists():
        previous_bytes = output.read_bytes()
        previous = json.loads(previous_bytes)
        previous_hash = hashlib.sha256(previous_bytes).hexdigest()[:12]
        archive = allowed / (
            f"rag_corpus_manifest_{len(previous['source_pmids'])}_source_"
            f"{previous_hash}.json"
        )
        if archive.exists() and archive.read_bytes() != previous_bytes:
            raise ValueError("Existing corpus-manifest archive does not match the current manifest")
        if not archive.exists():
            archive.write_bytes(previous_bytes)
    output.write_text(json.dumps(manifest, indent=2, default=date.isoformat), encoding="utf-8")
    print(f"Indexed {len(sources)} reviewed publications into {names}")
    print(f"Public-corpus manifest: {output}")


if __name__ == "__main__":
    main()
