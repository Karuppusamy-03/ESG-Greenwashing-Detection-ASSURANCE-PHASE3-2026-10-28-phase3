"""Regression: NLI stage status and counts are accurate (pure function, SYNTHETIC records)."""

import pathlib
import unittest

import nli_status as ns


def _evaluated(**extra):
    return {"nli_result": "ENTAILMENT", "scoring_eligible": True, "compatibility_status": "COMPATIBLE", **extra}


def _gate_skipped():
    return {"nli_result": "UNAVAILABLE", "scoring_eligible": False,
            "compatibility_status": "INCONCLUSIVE", "nli_failed": False}


def _model_failed():
    return {"nli_result": "UNAVAILABLE", "scoring_eligible": False, "nli_failed": True,
            "compatibility_status": "COMPATIBLE"}


DUPLICATE = {"nli_result": "NOT_EVALUATED", "scoring_eligible": False, "compatibility_status": "DUPLICATE_COPY"}
MALFORMED = {"nli_result": "NOT_EVALUATED", "scoring_eligible": False, "compatibility_status": "MALFORMED_EXTRACTION"}


class StatusTests(unittest.TestCase):
    def test_no_records_is_not_available(self):
        self.assertEqual(ns.summarize_nli_outcomes([])["status"], "NOT AVAILABLE")

    def test_all_excluded_is_not_completed_and_says_nothing_was_eligible(self):
        result = ns.summarize_nli_outcomes([DUPLICATE, MALFORMED])
        self.assertEqual(result["status"], "NOT AVAILABLE")
        self.assertIn("No eligible evidence pairs for NLI evaluation", result["message"])
        self.assertEqual(result["counts"]["evaluated"], 0)

    def test_all_eligible_evaluated_with_copies_says_both_facts(self):
        result = ns.summarize_nli_outcomes([_evaluated(), DUPLICATE])
        self.assertEqual(result["status"], "COMPLETED")
        self.assertIn("All 1 eligible evidence pair(s) were evaluated", result["message"])
        self.assertIn("1 duplicate copies", result["message"])
        self.assertEqual(result["counts"]["excluded_duplicate"], 1)

    def test_gate_skips_only_is_partial_not_completed(self):
        result = ns.summarize_nli_outcomes([_gate_skipped()])
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["counts"]["gate_skipped"], 1)
        self.assertEqual(result["counts"]["evaluated"], 0)

    def test_model_failure_only_is_failed_not_a_contradiction(self):
        result = ns.summarize_nli_outcomes([_model_failed(), _model_failed()])
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["counts"]["model_failed"], 2)
        self.assertEqual(result["counts"]["evaluated"], 0)
        self.assertIn("No pair was classified as support or contradiction", result["message"])

    def test_mixed_outcomes_are_partial_with_each_count(self):
        result = ns.summarize_nli_outcomes([_evaluated(), _gate_skipped(), _model_failed(), DUPLICATE, MALFORMED])
        self.assertEqual(result["status"], "PARTIAL")
        counts = result["counts"]
        self.assertEqual(counts["total_records"], 5)
        self.assertEqual(counts["eligible_candidates"], 3)
        self.assertEqual(counts["evaluated"], 1)
        self.assertEqual(counts["gate_skipped"], 1)
        self.assertEqual(counts["model_failed"], 1)
        self.assertEqual(counts["excluded_duplicate"], 1)
        self.assertEqual(counts["excluded_quality"], 1)

    def test_excluded_records_never_count_as_evaluated(self):
        result = ns.summarize_nli_outcomes([DUPLICATE, MALFORMED, _evaluated()])
        self.assertEqual(result["counts"]["evaluated"], 1)

    def test_unrecognised_model_output_is_counted_as_failed_not_evaluated(self):
        malformed_output = {"nli_result": "UNAVAILABLE", "nli_failed": True, "scoring_eligible": False}
        result = ns.summarize_nli_outcomes([malformed_output])
        self.assertEqual(result["counts"]["model_failed"], 1)
        self.assertEqual(result["counts"]["evaluated"], 0)

    def test_potentially_related_evaluated_pairs_are_reported_separately(self):
        result = ns.summarize_nli_outcomes([_evaluated(source_relation="potentially_related"), _evaluated()])
        self.assertEqual(result["counts"]["potentially_related_evaluated"], 1)


class AppWiringTests(unittest.TestCase):
    def test_app_stores_the_summary_and_uses_its_status(self):
        source = (pathlib.Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8-sig")
        self.assertIn('analysis["nli_summary"] = nli_summary', source)
        self.assertIn('nli_summary["status"]', source)
        self.assertNotIn('"All matched evidence pairs received eligible NLI classifications."', source)


if __name__ == "__main__":
    unittest.main()
