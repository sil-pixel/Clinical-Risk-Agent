"""Typed failures raised when LLM drafts break their output contracts."""


class ResponseIntegrityError(ValueError):
    """A provider draft failed deterministic post-generation validation."""


class EvidenceAbstention(ValueError):
    """The generator cannot answer the question from the retrieved passages."""
