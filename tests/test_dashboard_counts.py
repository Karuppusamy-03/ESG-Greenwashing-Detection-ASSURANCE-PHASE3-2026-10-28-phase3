"""Regression: dashboard match counts must not include duplicate copies (synthetic).

Checks the source of app.py, because app.py cannot be imported without streamlit.
"""
import ast
import pathlib
import unittest

APP = pathlib.Path(__file__).resolve().parents[1] / "app.py"


class DashboardCountTests(unittest.TestCase):
    def setUp(self):
        self.source = APP.read_text(encoding="utf-8-sig")

    def test_evidence_count_excludes_duplicate_copies(self):
        self.assertIn('match.get("is_duplicate_of") is None', self.source)

    def test_no_raw_len_of_matches_is_summed_for_display(self):
        tree = ast.parse(self.source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "sum":
                text = ast.get_source_segment(self.source, node) or ""
                self.assertNotIn('len(result.get("matches")', text,
                                 "a display count still sums raw match lists")


if __name__ == "__main__":
    unittest.main()
