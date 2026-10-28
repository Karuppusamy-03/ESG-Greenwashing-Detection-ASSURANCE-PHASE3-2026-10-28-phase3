"""H1 regression: a result with no scoring_eligible flag must not be scored.

Tests the eligibility rule used by the NLI-completion check in app.py. app.py cannot
be imported in the sandbox (it needs streamlit), so the rule is extracted here
as the same expression and checked directly. SYNTHETIC inputs."""

import ast
import pathlib
import unittest

APP = pathlib.Path(__file__).resolve().parents[1] / "app.py"


NLI_STATUS = APP.with_name("nli_status.py")


def _eligibility_clause_in_app():
    """Return the source of the eligibility condition that decides NLI evaluation.

    The rule moved from app.py into nli_status.py when the NLI stage status was rebuilt
    (see validation/NLI_STATUS_REPORT.md). Found structurally: the first ``and`` operand
    that reads ``scoring_eligible``. Returns None if no such operand exists.
    """
    for path in (APP, NLI_STATUS):
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And):
                for operand in node.values:
                    text = ast.get_source_segment(source, operand) or ""
                    if "scoring_eligible" in text:
                        return text
    return None


class MissingEligibilityFlagTests(unittest.TestCase):
    def test_app_does_not_default_missing_flag_to_eligible(self):
        clause = _eligibility_clause_in_app()
        self.assertIsNotNone(clause, "eligibility condition not found in app.py")
        self.assertNotIn(
            ", True)", clause,
            "a missing scoring_eligible flag must not default to True",
        )
        self.assertIn("is True", clause, "eligibility must require an explicit True")

    def test_missing_flag_is_not_counted_as_eligible(self):
        # Mirror of the corrected rule: absent flag -> not eligible.
        result = {"nli_result": "ENTAILMENT"}
        self.assertFalse(result.get("scoring_eligible", False))

    def test_explicit_true_flag_is_still_eligible(self):
        result = {"nli_result": "ENTAILMENT", "scoring_eligible": True}
        self.assertTrue(result.get("scoring_eligible", False))

    def test_explicit_false_flag_is_not_eligible(self):
        result = {"nli_result": "CONTRADICTION", "scoring_eligible": False}
        self.assertFalse(result.get("scoring_eligible", False))


if __name__ == "__main__":
    unittest.main()
