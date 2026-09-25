"""Exercise the local MCP tools through the official in-process client."""

from __future__ import annotations

import asyncio
import argparse
import json
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from rag_mcp_server import mcp


async def main(*, stdio: bool = False) -> None:
    server = (StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).with_name("rag_mcp_server.py"))],
        cwd=Path(__file__).resolve().parents[1],
    ) if stdio else mcp)
    async with Client(server, raise_exceptions=True) as client:
        listed = await client.list_tools()
        names = {tool.name for tool in listed.tools}
        expected = {"search_evidence", "get_paper", "compare_retrieval",
                    "list_curated_claims", "get_curated_claim"}
        if names != expected:
            raise AssertionError(f"Unexpected MCP tools: {names}")
        if any(not tool.annotations or not tool.annotations.read_only_hint
               for tool in listed.tools):
            raise AssertionError("A tool lacks a read-only annotation")

        async def call(name: str, arguments: dict) -> dict:
            result = await client.call_tool(name, arguments)
            if result.is_error or not isinstance(result.structured_content, dict):
                raise AssertionError(f"MCP tool failed: {name}: {result}")
            return result.structured_content

        paper = await call("get_paper", {"pmid": "21382538"})
        if not paper["found"] or "ADHD" not in paper["abstract"]:
            raise AssertionError("Paper lookup failed")
        absent = await call("get_paper", {"pmid": "99999999"})
        if absent["found"]:
            raise AssertionError("Unknown PMID was exposed")
        claims = await call("list_curated_claims", {})
        if len(claims["claim_ids"]) != 5:
            raise AssertionError("Curated catalog changed")
        claim = await call("get_curated_claim", {
            "claim_id": "childhood_adhd_later_abuse_dependence"})
        if claim["support_status"] != "curated_assertion_available":
            raise AssertionError("Curated claim unavailable")
        no_claim = await call("get_curated_claim", {"claim_id": "cybervictimization_later_diagnosed_sud"})
        if no_claim["curated_passages"]:
            raise AssertionError("Unsupported claim received a passage")
        question = "Is childhood ADHD associated with later substance abuse or dependence?"
        search = await call("search_evidence", {"question": question, "limit": 3})
        if (search["support_status"] != "not_evaluated_for_the_question"
                or search["match_status"] != "matches_found"
                or not search["matches"] or len(search["matches"]) > 3):
            raise AssertionError("Exploratory search response is invalid")
        comparison = await call("compare_retrieval", {"question": question, "limit": 2})
        if (comparison["document"]["strategy"] != "document"
                or comparison["hierarchical"]["strategy"] != "hierarchical"
                or len(comparison["document"]["matches"]) > 2):
            raise AssertionError("Comparison response is invalid")
        print(json.dumps({"transport": "stdio" if stdio else "in_process",
                          "tools": sorted(names), "paper": paper["pmid"],
                          "curated_claims": len(claims["claim_ids"]),
                          "search_first_pmid": search["matches"][0]["pmid"],
                          "comparison_document_count": len(comparison["document"]["matches"]),
                          "comparison_hierarchical_count": len(comparison["hierarchical"]["matches"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stdio", action="store_true")
    asyncio.run(main(stdio=parser.parse_args().stdio))
