"""Regression test: the human-review tooling must not require the NLI stack.

Runs each review module in a fresh subprocess in which torch, transformers and
other ML packages are made unimportable. This is a software-integrity check
only; it says nothing about detection accuracy.
"""

import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]

BLOCKER = r'''
import importlib, sys
BLOCKED = {"torch", "transformers", "sentence_transformers", "xgboost", "shap", "ddgs", "fitz", "plotly"}
class _Block:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in BLOCKED:
            raise ImportError("blocked heavy dependency: " + name)
        return None
sys.meta_path.insert(0, _Block())
sys.path.insert(0, %(root)r)
importlib.import_module(%(module)r)
print("OK")
'''

REVIEW_MODULES = (
    "nli_config",
    "evaluation.prepare_review_packet",
    "evaluation.pair_review",
    "evaluation.import_review_packet",
    "evaluation.evaluate",
    "evaluation.evaluate_nli",
)


class ReviewDependencyIsolationTests(unittest.TestCase):
    def test_review_modules_import_without_ml_packages(self):
        for module in REVIEW_MODULES:
            with self.subTest(module=module):
                code = BLOCKER % {"root": str(PROJECT_DIR), "module": module}
                completed = subprocess.run(
                    [sys.executable, "-c", code],
                    capture_output=True, text=True, timeout=120,
                )
                self.assertEqual(
                    completed.returncode, 0,
                    f"{module} needs an ML package:\n{completed.stderr[-800:]}",
                )
                self.assertEqual(completed.stdout.strip(), "OK")

    def test_model_name_is_readable_without_ml_packages(self):
        code = BLOCKER % {"root": str(PROJECT_DIR), "module": "nli_config"}
        code += "\nfrom nli_config import MODEL_NAME\nassert MODEL_NAME == 'cross-encoder/nli-deberta-v3-small'\n"
        completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
        self.assertEqual(completed.returncode, 0, completed.stderr[-800:])


if __name__ == "__main__":
    unittest.main()
