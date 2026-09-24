"""Scientific-publication retrieval components."""

from .corpus import ScientificSource, SourceSection, eligible_source
from .chunking import Passage, chunk_source

__all__ = ["Passage", "ScientificSource", "SourceSection", "chunk_source", "eligible_source"]
