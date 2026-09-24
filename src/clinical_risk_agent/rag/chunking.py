"""Document and section-aware parent/child passage representations."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass

from .corpus import ScientificSource


SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z\d])")
WORD_TOKEN = re.compile(r"\b\w+(?:[-']\w+)*\b")


@dataclass(frozen=True, slots=True)
class Passage:
    source_id: str
    parent_id: str
    chunk_id: str
    strategy: str
    section: str
    locator: str
    exact_text: str
    parent_text: str
    title: str

    @property
    def embedding_pair(self) -> tuple[str, str]:
        return self.title, self.exact_text


def approximate_tokens(text: str) -> int:
    """Fixture-only approximation; production indexing passes the model tokenizer."""
    return len(WORD_TOKEN.findall(text))


def _stable_id(*parts: str) -> str:
    raw = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:24]


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in SENTENCE_BOUNDARY.split(" ".join(text.split())) if item.strip()]


def _split_long_sentence(
    sentence: str, max_tokens: int, count_tokens: Callable[[str], int]
) -> list[str]:
    if count_tokens(sentence) <= max_tokens:
        return [sentence]
    words = sentence.split()
    pieces: list[str] = []
    current: list[str] = []
    for word in words:
        proposal = " ".join((*current, word))
        if current and count_tokens(proposal) > max_tokens:
            pieces.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


def _child_texts(
    text: str,
    *,
    max_tokens: int,
    overlap_tokens: int,
    count_tokens: Callable[[str], int],
) -> tuple[str, ...]:
    sentences = [piece for sentence in _sentences(text)
                 for piece in _split_long_sentence(sentence, max_tokens, count_tokens)]
    if not sentences:
        return ()
    chunks: list[str] = []
    start = 0
    while start < len(sentences):
        end = start + 1
        while end < len(sentences) and count_tokens(" ".join(sentences[start:end + 1])) <= max_tokens:
            end += 1
        chunks.append(" ".join(sentences[start:end]))
        if end == len(sentences):
            break
        if overlap_tokens <= 0:
            start = end
            continue
        overlap_start = end
        if count_tokens(sentences[end - 1]) <= overlap_tokens:
            overlap_start = end - 1
            while (overlap_start > start + 1
                   and count_tokens(" ".join(sentences[overlap_start - 1:end]))
                   <= overlap_tokens):
                overlap_start -= 1
        start = overlap_start if overlap_start > start else end
    return tuple(chunks)


def chunk_source(
    source: ScientificSource,
    *,
    strategy: str,
    count_tokens: Callable[[str], int] = approximate_tokens,
) -> tuple[Passage, ...]:
    if strategy not in {"document", "hierarchical"}:
        raise ValueError("Unsupported chunking strategy")
    sections = []
    if source.abstract.strip():
        sections.append(("abstract", "abstract", source.abstract))
    sections.extend((section.name, section.locator, section.text)
                    for section in source.full_text_sections)
    result: list[Passage] = []
    for section_name, locator, parent_text in sections:
        parent_id = _stable_id(source.source_id, section_name, locator, parent_text)
        if strategy == "document":
            texts = (" ".join(parent_text.split()),)
        else:
            texts = _child_texts(
                parent_text,
                max_tokens=300,
                overlap_tokens=35 if section_name != "abstract" else 30,
                count_tokens=count_tokens,
            )
        for index, exact_text in enumerate(texts):
            result.append(Passage(
                source_id=source.source_id,
                parent_id=parent_id,
                chunk_id=_stable_id(parent_id, str(index), exact_text),
                strategy=strategy,
                section=section_name,
                locator=f"{locator}:{index + 1}",
                exact_text=exact_text,
                parent_text=parent_text,
                title=source.title,
            ))
    return tuple(result)
