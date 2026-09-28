"""Keep project-owned Python classes and functions documented without importing them."""

import ast
from pathlib import Path
import unittest


class DocumentationTests(unittest.TestCase):
    """Check that every named Python definition has a non-empty summary docstring."""

    def test_python_classes_and_functions_have_descriptions(self):
        """Verify docstring coverage across runtime code, scripts, deployment and tests."""
        root = Path(__file__).resolve().parents[2]
        missing = []
        for directory in ("src", "scripts", "deployment", "tests"):
            for path in sorted((root / directory).rglob("*.py")):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not (ast.get_docstring(node) or "").strip():
                            missing.append(f"{path.relative_to(root)}:{node.lineno} {node.name}")
        self.assertEqual(missing, [], "Missing descriptions:\n" + "\n".join(missing))
