"""Convert a pinned, trusted MedCPT weight file to local safetensors once."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_dir", type=Path)
    parser.add_argument("--source-sha256", required=True)
    args = parser.parse_args()
    source = args.model_dir / "pytorch_model.bin"
    target = args.model_dir / "model.safetensors"
    if target.exists():
        raise FileExistsError(f"Refusing to overwrite {target}")
    observed = sha256(source)
    if observed != args.source_sha256:
        raise ValueError(f"Source model checksum mismatch: {observed}")

    import torch
    from safetensors.torch import save_file

    weights = torch.load(source, map_location="cpu", weights_only=True)
    if not isinstance(weights, dict) or not weights:
        raise ValueError("Expected a nonempty weight dictionary")
    if not all(isinstance(key, str) and isinstance(value, torch.Tensor)
               for key, value in weights.items()):
        raise ValueError("Checkpoint contains unexpected objects")
    save_file({key: value.contiguous() for key, value in weights.items()}, target)
    print(f"Source SHA-256: {observed}")
    print(f"Safetensors SHA-256: {sha256(target)}")


if __name__ == "__main__":
    main()
