"""Regression tests for forecast wording and reporting-year attachment (O1, O2).

All sentences are SYNTHETIC. They test timeline logic only, not whether any
company's disclosure is correct.
"""

import unittest

import timeline_analyzer as ta


def _records(sentence):
    years = ta._explicit_reporting_years(sentence)
    return ta._measurement_records(sentence, years or [])


def _value(records, value):
    matches = [r for r in records if r.get("value") is not None and round(r["value"], 2) == value]
    assert len(matches) == 1, f"expected one record for {value}, got {len(matches)}"
    return matches[0]


class ForecastOnlyClauseTests(unittest.TestCase):
    """O1: a projection must not be read as a historical measurement."""

    def test_projected_value_is_a_target_not_a_reported_result(self):
        record = _value(_records("Scope 1 emissions are projected to reach 400 t in 2026."), 400.0)
        self.assertEqual(record["performance_type"], "Target")

    def test_projected_value_does_not_take_its_forecast_year_as_reporting_year(self):
        record = _value(_records("Scope 1 emissions are projected to reach 400 t in 2026."), 400.0)
        self.assertIsNone(record["reporting_year"])

    def test_expected_value_is_a_target(self):
        record = _value(_records("Emissions are expected to fall to 400 t in 2026."), 400.0)
        self.assertEqual(record["performance_type"], "Target")
        self.assertIsNone(record["reporting_year"])


class MixedClauseTests(unittest.TestCase):
    """O1: an achieved result and a projection in one sentence are separated."""

    SENTENCE = "Scope 1 emissions reached 500 t in 2024 and are projected to reach 400 t in 2026."

    def test_achieved_value_keeps_its_reporting_year(self):
        record = _value(_records(self.SENTENCE), 500.0)
        self.assertEqual(record["performance_type"], "Reported result")
        self.assertEqual(record["reporting_year"], "2024")

    def test_projected_value_is_a_target_in_the_same_sentence(self):
        record = _value(_records(self.SENTENCE), 400.0)
        self.assertEqual(record["performance_type"], "Target")
        self.assertIsNone(record["reporting_year"])


class MultipleReportingYearTests(unittest.TestCase):
    def test_two_achieved_years_yield_no_guessed_year(self):
        # Existing conservative rule, pinned: no year is guessed when several appear.
        self.assertIsNone(ta._explicit_reporting_years(
            "Emissions were 1,200 t in 2023 and 900 t in 2024."
        ))

    def test_single_achieved_year_is_kept(self):
        record = _value(_records("Scope 1 emissions were 800 t in 2024."), 800.0)
        self.assertEqual(record["reporting_year"], "2024")


class TargetYearTests(unittest.TestCase):
    def test_future_target_year_is_not_a_reporting_year(self):
        record = _value(_records("We aim to cut emissions to 500 t by 2030."), 500.0)
        self.assertEqual(record["performance_type"], "Target")
        self.assertIsNone(record["reporting_year"])
        self.assertEqual(record["target_year"], 2030)


class PublicationDateTests(unittest.TestCase):
    def test_publication_date_is_not_used_as_reporting_year(self):
        docs = [{
            "status": "success", "title": "Report 2025", "publisher": "Co",
            "publication_date": "2025-06-01", "source_url": "https://company.example/r.pdf",
            "text": "Scope 1 emissions are projected to reach 400 t in 2026.",
        }]
        for record in ta.analyze_timeline(docs):
            self.assertNotEqual(record.get("reporting_year"), 2025)
            self.assertNotEqual(record.get("reporting_year"), "2025")


if __name__ == "__main__":
    unittest.main()
