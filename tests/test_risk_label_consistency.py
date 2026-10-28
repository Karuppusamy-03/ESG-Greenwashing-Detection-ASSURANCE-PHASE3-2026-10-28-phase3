"""Regression: every analysis-level risk label comes from one rule (brief item 7).

Synthetic feature rows only. Not evidence about any real company.
"""

import ast
import itertools
import pathlib
import unittest

from risk_summary import NOT_PREDICTED, analysis_risk_category

APP = pathlib.Path(__file__).resolve().parents[1] / "app.py"


def _row(category):
    return {"demonstration_risk_category": category}


class SharedRuleTests(unittest.TestCase):
    def test_result_does_not_depend_on_row_order(self):
        for rows in itertools.permutations([_row("MEDIUM"), _row("HIGH"), _row("LOW")]):
            self.assertEqual(analysis_risk_category(list(rows)), "HIGH")

    def test_high_row_is_not_hidden_by_an_earlier_medium_row(self):
        # The old summary took the first predicted row, so [MEDIUM, HIGH] showed MEDIUM.
        self.assertEqual(analysis_risk_category([_row("MEDIUM"), _row("HIGH")]), "HIGH")

    def test_no_predicted_rows_gives_not_predicted(self):
        self.assertEqual(analysis_risk_category([]), NOT_PREDICTED)
        self.assertEqual(
            analysis_risk_category([_row(NOT_PREDICTED), _row(None), _row("")]),
            NOT_PREDICTED,
        )

    def test_not_predicted_rows_are_ignored_not_ranked(self):
        self.assertEqual(
            analysis_risk_category([_row(NOT_PREDICTED), _row("LOW")]), "LOW",
        )

    def test_unknown_category_values_are_not_promoted(self):
        self.assertEqual(
            analysis_risk_category([_row("CRITICAL"), _row("LOW")]), "LOW",
        )


class AppUsesOneRuleTests(unittest.TestCase):
    """app.py must not keep a second aggregation rule for the analysis-level label."""

    def setUp(self):
        self.source = APP.read_text(encoding="utf-8-sig")
        self.tree = ast.parse(self.source)

    def test_app_imports_the_shared_rule(self):
        self.assertIn("from risk_summary import analysis_risk_category", self.source)

    def test_risk_level_metric_keeps_the_existing_unavailable_text(self):
        # The dashboard metric must show "Unavailable", not the internal NOT_PREDICTED code.
        self.assertIn('risk_level = "Unavailable"', self.source)

    def test_app_has_no_first_row_risk_selection(self):
        # The replaced pattern selected the first predicted row with next(...).
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "next":
                text = ast.get_source_segment(self.source, node) or ""
                self.assertNotIn("demonstration_risk_category", text,
                                 "a first-row risk selection is still present in app.py")

    def test_app_has_no_local_max_over_risk_rows(self):
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "max":
                text = ast.get_source_segment(self.source, node) or ""
                self.assertNotIn("'HIGH': 3", text)
                self.assertNotIn('"HIGH": 3', text)


if __name__ == "__main__":
    unittest.main()
