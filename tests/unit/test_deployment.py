import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
# Files and directories the backend reads at startup or on its first requests.
RUNTIME_PATHS = (
    "src", "model_artifacts", "data/indexes/models", "data/indexes/qdrant",
    "data/indexes/rag_corpus_manifest.json", "data/monitoring/drift_reference.json",
    "agent_docs/RAG_21_SOURCE_CLAIM_SUPPORT_CATALOG.json",
    "agent_docs/RAG_MEDCPT_ENCODER_PIN.json",
    "agent_docs/INTENT_ROUTER_UTTERANCES.json",
    "agent_docs/INTENT_ROUTER_CALIBRATION.json",
)


class ModalImageTests(unittest.TestCase):
    """Check the Modal image ships every path the backend needs to start."""

    def test_image_ships_runtime_paths(self):
        """Verify each runtime path appears as a LOCAL_ROOT source in modal_app.py."""
        tree = ast.parse((ROOT / "deployment/modal_app.py").read_text(encoding="utf-8"))
        shipped = {
            node.right.value for node in ast.walk(tree)
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div)
            and isinstance(node.left, ast.Name) and node.left.id == "LOCAL_ROOT"
            and isinstance(node.right, ast.Constant)
        }
        self.assertEqual(sorted(set(RUNTIME_PATHS) - shipped), [])
