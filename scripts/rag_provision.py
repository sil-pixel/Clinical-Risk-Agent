"""Provision an isolated local Qdrant store for versioned public-science collections.

No collection is created until an eligible corpus and a pinned embedding model are
available: the collection vector size must match that model's actual output.
"""

from __future__ import annotations

import argparse
from pathlib import Path


def provision(path: Path) -> tuple[Path, tuple[str, ...]]:
    from qdrant_client import QdrantClient

    resolved = path.resolve()
    repository = Path(__file__).resolve().parents[1]
    allowed = (repository / "data" / "indexes").resolve()
    if resolved != allowed and allowed not in resolved.parents:
        raise ValueError("Local Qdrant path must be inside data/indexes")
    resolved.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(resolved))
    try:
        collections = tuple(sorted(item.name for item in client.get_collections().collections))
    finally:
        client.close()
    return resolved, collections


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--path", type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "indexes" / "qdrant",
    )
    args = parser.parse_args()
    path, collections = provision(args.path)
    print(f"Local Qdrant store ready: {path}")
    print(f"Scientific collections: {', '.join(collections) if collections else '(none yet)'}")


if __name__ == "__main__":
    main()
