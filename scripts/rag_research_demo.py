"""Ask the local research-only RAG MCP tool one public/synthetic question."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters

from clinical_risk_agent.rag.answering import CURATED_QUESTIONS

ROOT = Path(__file__).resolve().parents[1]


async def ask(question: str) -> dict:
    """Run a bounded research question through the local MCP server."""
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(ROOT / "scripts/rag_mcp_server.py")],
        cwd=ROOT,
    )
    async with Client(server, raise_exceptions=True) as client:
        result = await client.call_tool("answer_research_question", {"question": question})
        if result.is_error or not isinstance(result.structured_content, dict):
            raise RuntimeError("Research RAG tool is unavailable")
        return result.structured_content


def main() -> None:
    """Run the command-line workflow: Ask the local research-only RAG MCP tool one public/synthetic question."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question", help="A public or synthetic research question")
    parser.add_argument("--list-questions", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print the structured result")
    args = parser.parse_args()
    if args.list_questions:
        for item in CURATED_QUESTIONS:
            print(item.question)
        return
    question = args.question or input("Research question (no patient data): ")
    result = asyncio.run(ask(question))
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(result["answer"])
    print(result["limitation"])
    for citation in result["citations"]:
        print(f"\n[{citation['citation_id']}] {citation['title']} (PMID {citation['pmid']})")
        print(f"Matched text: {citation['exact_matched_text']}")
        print(f"Bounded use: {citation['bounded_use']}")
    if result["related_unverified_passages"]:
        print("\nRelated but unverified passages:")
        for match in result["related_unverified_passages"]:
            print(f"- PMID {match['pmid']}: {match['title']}")


if __name__ == "__main__":
    main()
