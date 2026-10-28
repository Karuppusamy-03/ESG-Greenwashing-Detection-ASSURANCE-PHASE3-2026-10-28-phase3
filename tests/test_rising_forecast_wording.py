"""O2 regression tests: "rising to" wording is a forecast only with forward-looking
context. SYNTHETIC sentences; timeline logic only."""

import unittest

import timeline_analyzer as ta


def _records(sentence):
    return ta._measurement_records(sentence, ta._explicit_reporting_years(sentence) or [])


class PositiveForwardLookingTests(unittest.TestCase):
    def test_expected_to_rise_by_future_year_is_a_target(self):
        recs = _records("Renewable electricity is expected to rise to 60% by 2030.")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["performance_type"], "Target")
        self.assertIsNone(recs[0]["reporting_year"])
        self.assertEqual(recs[0]["target_year"], 2030)

    def test_on_track_rising_to_future_year_is_a_target(self):
        recs = _records("We are on track for renewable electricity rising to 60% in 2030.")
        self.assertEqual(recs[0]["performance_type"], "Target")
        self.assertIsNone(recs[0]["reporting_year"])
        self.assertEqual(recs[0]["target_year"], 2030)


class NegativeAchievedTests(unittest.TestCase):
    def test_rose_to_in_past_year_stays_a_reported_result(self):
        recs = _records("Renewable electricity rose to 40% in 2024.")
        self.assertEqual(recs[0]["performance_type"], "Reported result")
        self.assertEqual(recs[0]["reporting_year"], "2024")

    def test_achieved_then_rising_projection_keeps_the_achieved_value(self):
        recs = {r["value"]: r for r in _records(
            "Renewable electricity was 40% in 2024, rising to 60% in 2025."
        )}
        # Two years in one sentence: the existing conservative rule assigns no year.
        self.assertEqual(recs[40.0]["performance_type"], "Reported result")
        self.assertIsNone(recs[40.0]["reporting_year"])


class AmbiguousWordingTests(unittest.TestCase):
    def test_bare_rising_to_without_context_is_not_forced_to_forecast(self):
        recs = _records("Renewable electricity rising to 60%.")
        self.assertTrue(recs)
        self.assertEqual(recs[0]["performance_type"], "Reported result")
        self.assertIsNone(recs[0]["reporting_year"])

    def test_non_environmental_rising_is_not_a_measurement(self):
        self.assertEqual(_records("Sales rising to new highs in our operations."), [])


if __name__ == "__main__":
    unittest.main()
