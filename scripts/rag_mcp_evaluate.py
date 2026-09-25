"""Evaluate the local MCP transport, tools, boundaries and warm latency."""

from __future__ import annotations

import asyncio
import json
import math
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from rag_support_integration import CASES

ROOT = Path(__file__).resolve().parents[1]


def _summary(values: list[float]) -> dict:
    ordered = sorted(values)
    return {"calls": len(values), "median_ms": round(statistics.median(values), 2),
            "p95_ms": round(ordered[math.ceil(.95 * len(ordered)) - 1], 2)}


async def main() -> None:
    corpus = json.loads((ROOT / "data/indexes/rag_corpus_manifest.json").read_text())
    catalog = json.loads((ROOT / "agent_docs/RAG_21_SOURCE_CLAIM_SUPPORT_CATALOG.json").read_text())
    passages = {item["chunk_id"]: item["exact_text"]
                for item in corpus["snapshots"]["hierarchical"]["passages"]}
    sources = {item["pmid"]: item for item in corpus["snapshots"]["hierarchical"]["sources"]}
    assertions = {item["claim_id"]: item for item in catalog["assertions"]}
    checks = defaultdict(int)
    latencies: dict[str, list[float]] = defaultdict(list)
    server = StdioServerParameters(command=sys.executable,
                                   args=[str(ROOT / "scripts/rag_mcp_server.py")], cwd=ROOT)
    start = time.perf_counter()
    async with Client(server, raise_exceptions=True) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        if names != {"search_evidence", "get_paper", "compare_retrieval",
                     "list_curated_claims", "get_curated_claim"}:
            raise AssertionError("MCP tool inventory differs from the five-tool contract")
        if any(not tool.annotations or not tool.annotations.read_only_hint
               or tool.annotations.open_world_hint is not False for tool in tools.tools):
            raise AssertionError("A tool lacks read-only/closed-corpus annotations")
        checks["tool_schema"] += 1

        async def call(name: str, arguments: dict, *, expected_error: bool = False) -> dict:
            began = time.perf_counter()
            result = await client.call_tool(name, arguments)
            elapsed = (time.perf_counter() - began) * 1000
            if expected_error:
                if not result.is_error:
                    raise AssertionError(f"Invalid {name} input was accepted")
                checks["invalid_input_rejected"] += 1
                return {}
            if result.is_error or not isinstance(result.structured_content, dict):
                raise AssertionError(f"{name} failed its structured MCP contract")
            latencies[name].append(elapsed)
            return result.structured_content

        claims = await call("list_curated_claims", {})  # Includes first tool/corpus load.
        cold_ms = latencies["list_curated_claims"].pop()
        if set(claims["claim_ids"]) != set(assertions):
            raise AssertionError("Catalog inventory differs from MCP result")
        checks["catalog_inventory"] += 1

        for pmid in corpus["source_pmids"]:
            paper = await call("get_paper", {"pmid": pmid})
            if (not paper["found"] or paper["abstract"] != sources[pmid]["abstract"]
                    or paper["bounded_use"] != corpus["source_review"][pmid]["bounded_use"]):
                raise AssertionError(f"Paper metadata differs for PMID {pmid}")
            checks["paper_exact"] += 1
        absent = await call("get_paper", {"pmid": "99999999"})
        if absent["found"]:
            raise AssertionError("Unknown paper was exposed")
        checks["unknown_paper"] += 1

        for _, question, claim_id, expected_pmid in CASES:
            curated = await call("get_curated_claim", {"claim_id": claim_id})
            if expected_pmid:
                assertion = assertions[claim_id]
                if (curated["support_status"] != "curated_assertion_available"
                        or len(curated["curated_passages"]) != 1
                        or curated["curated_passages"][0]["pmid"] != expected_pmid
                        or curated["curated_passages"][0]["exact_matched_text"]
                        != passages[assertion["chunk_id"]]):
                    raise AssertionError(f"Curated claim mismatch: {claim_id}")
                checks["curated_positive"] += 1
            else:
                if curated["curated_passages"] or curated["support_status"] != "no_curated_assertion":
                    raise AssertionError(f"Unsupported claim received evidence: {claim_id}")
                checks["curated_negative"] += 1

            search = await call("search_evidence", {"question": question, "limit": 5})
            if search["support_status"] != "not_evaluated_for_the_question":
                raise AssertionError("Exploratory search implied claim support")
            for match in search["matches"]:
                if (match["exact_matched_text"] != passages[match["chunk_id"]]
                        or match["bounded_use"]
                        != corpus["source_review"][match["pmid"]]["bounded_use"]):
                    raise AssertionError("Search passage or bounded use differs from corpus")
            checks["search_exact"] += 1
            if expected_pmid and expected_pmid in [row["pmid"] for row in search["matches"]]:
                checks["direct_source_in_search_top5"] += 1

        for _, question, _, _ in CASES[:5]:
            result = await call("compare_retrieval", {"question": question, "limit": 5})
            if (result["document"]["strategy"] != "document"
                    or result["hierarchical"]["strategy"] != "hierarchical"
                    or result["document"]["support_status"] != "not_evaluated_for_the_question"
                    or result["hierarchical"]["support_status"] != "not_evaluated_for_the_question"):
                raise AssertionError("Comparison mislabeled retrieval support")
            checks["comparison"] += 1

        await call("search_evidence", {"question": "x"}, expected_error=True)
        await call("search_evidence", {"question": "ADHD later substance use?", "limit": 6},
                   expected_error=True)
        await call("get_paper", {"pmid": "../secret"}, expected_error=True)
        await call("get_curated_claim", {"claim_id": "../secret"}, expected_error=True)

    print(json.dumps({"transport": "stdio", "tool_count": len(names),
                      "checks": dict(checks), "first_corpus_load_ms": round(cold_ms, 2),
                      "warm_latency": {name: _summary(values) for name, values in latencies.items()
                                       if values},
                      "total_elapsed_ms": round((time.perf_counter() - start) * 1000, 2)},
                     sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
