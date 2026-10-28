"""Regression tests: missing, invalid and partial NLI/similarity inputs must not
become risk evidence. Every input here is SYNTHETIC and tests software logic only.
They are not evidence of real-world detection accuracy.
"""

import math
import unittest

import pandas as pd

import risk_predictor as rp


def _row(**overrides):
    row = dict(
        claim_id="synthetic-claim",
        evidence_available=1,
        similarity=0.9,
        nli_entailment=0,
        nli_contradiction=0,
        nli_neutral=0,
        nli_coverage_complete=1,
    )
    row.update(overrides)
    return row


class AsFloatTests(unittest.TestCase):
    def test_default_is_none_not_zero(self):
        self.assertIsNone(rp._as_float(None))
        self.assertIsNone(rp._as_float(float("nan")))
        self.assertIsNone(rp._as_float(""))

    def test_missing_and_invalid_values_return_none(self):
        for value in (None, "", "   ", "abc", float("inf"), float("-inf"), pd.NA, pd.NaT):
            with self.subTest(value=value):
                self.assertIsNone(rp._as_float(value))

    def test_genuine_zero_is_preserved_as_zero(self):
        for value in (0, 0.0, "0", "0.0", 0.5):
            with self.subTest(value=value):
                result = rp._as_float(value)
                self.assertIsNotNone(result)
                self.assertEqual(result, float(value))

    def test_explicit_default_still_honoured(self):
        self.assertEqual(rp._as_float(None, 7.0), 7.0)


class HeuristicMissingValueTests(unittest.TestCase):
    def assertUnassessed(self, row):
        self.assertIsNone(rp._heuristic_risk_score(row))

    def test_missing_similarity_is_unassessed_not_zero(self):
        for value in (None, float("nan"), "", "abc"):
            with self.subTest(similarity=value):
                self.assertUnassessed(_row(similarity=value))

    def test_one_missing_nli_count_is_unassessed(self):
        for column in ("nli_entailment", "nli_contradiction", "nli_neutral"):
            with self.subTest(column=column):
                self.assertUnassessed(_row(**{column: float("nan")}))
                self.assertUnassessed(_row(**{column: None}))

    def test_all_nli_missing_is_unassessed(self):
        self.assertUnassessed(_row(nli_entailment=None, nli_contradiction=None, nli_neutral=None))

    def test_insufficient_nli_coverage_is_unassessed(self):
        self.assertUnassessed(_row(nli_coverage_complete=0, nli_contradiction=1))

    def test_no_evidence_is_unassessed(self):
        self.assertUnassessed(_row(evidence_available=0))

    def test_genuine_zero_counts_still_score(self):
        score = rp._heuristic_risk_score(_row())
        self.assertIsNotNone(score)
        self.assertEqual(score, 10.0)

    def test_valid_contradiction_still_scores_high(self):
        score = rp._heuristic_risk_score(_row(nli_contradiction=1))
        self.assertIsNotNone(score)
        self.assertGreaterEqual(score, 72.0)

    def test_valid_entailment_still_scores_low(self):
        score = rp._heuristic_risk_score(_row(nli_entailment=1, similarity=0.9))
        self.assertIsNotNone(score)
        self.assertLessEqual(score, 30.0)

    def test_similarity_is_clamped_for_valid_out_of_range_values(self):
        high = rp._heuristic_risk_score(_row(similarity=5.0))
        at_one = rp._heuristic_risk_score(_row(similarity=1.0))
        self.assertEqual(high, at_one)


class PredictFrameMissingValueTests(unittest.TestCase):
    def test_frame_with_missing_similarity_has_no_score(self):
        frame = pd.DataFrame([_row(similarity=None)])
        result = rp.predict_risk_from_features(frame).iloc[0]
        self.assertTrue(pd.isna(result["risk_score"]))
        self.assertTrue(result["risk_unavailable_reason"])

    def test_frame_with_one_missing_count_has_no_score(self):
        frame = pd.DataFrame([_row(nli_neutral=float("nan"))])
        result = rp.predict_risk_from_features(frame).iloc[0]
        self.assertTrue(pd.isna(result["risk_score"]))

    def test_frame_with_genuine_zeros_scores(self):
        frame = pd.DataFrame([_row()])
        result = rp.predict_risk_from_features(frame).iloc[0]
        self.assertFalse(pd.isna(result["risk_score"]))
        self.assertEqual(float(result["risk_score"]), 10.0)


if __name__ == "__main__":
    unittest.main()
