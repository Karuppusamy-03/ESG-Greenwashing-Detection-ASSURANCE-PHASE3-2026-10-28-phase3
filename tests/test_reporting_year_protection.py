"""Regression tests: publication dates, future target years and historical
baseline years must not be treated as actual reporting years.

All sentences are SYNTHETIC. These tests check timeline logic only, not whether
any real company's disclosure is correct.
"""

import unittest

import timeline_analyzer as ta


def _records(sentence):
    years = ta._explicit_reporting_years(sentence)
    return ta._measurement_records(sentence, years or [])


def _by_value(records):
    return {round(r["value"], 2): r for r in records if r.get("value") is not None}


class FutureTargetYearTests(unittest.TestCase):
    def test_future_value_in_mixed_sentence_is_not_a_reporting_year(self):
        records = _by_value(_records(
            "We cut Scope 1 emissions to 800 t CO2e in 2024, on track for 500 t by 2030."
        ))
        forecast = records[500.0]
        self.assertEqual(forecast["performance_type"], "Target")
        self.assertIsNone(forecast["reporting_year"])
        self.assertEqual(forecast["target_year"], 2030)

    def test_actual_reported_value_keeps_its_real_year(self):
        records = _by_value(_records(
            "We cut Scope 1 emissions to 800 t CO2e in 2024, on track for 500 t by 2030."
        ))
        actual = records[800.0]
        self.assertEqual(actual["performance_type"], "Reported result")
        self.assertEqual(actual["reporting_year"], "2024")

    def test_forecast_with_no_keyword_is_not_attributed_to_past_year(self):
        records = _by_value(_records(
            "Emissions were 1,200 tonnes in 2023, expected to drop to 900 tonnes by 2026."
        ))
        self.assertEqual(records[900.0]["performance_type"], "Target")
        self.assertNotEqual(records[900.0]["reporting_year"], "2023")
        self.assertEqual(records[1200.0]["reporting_year"], "2023")

    def test_keyword_target_with_future_year_is_still_a_target(self):
        records = _by_value(_records(
            "We targeted 100% renewable electricity by 2030 and reported 45% in 2023."
        ))
        self.assertEqual(records[100.0]["performance_type"], "Target")
        self.assertIsNone(records[100.0]["reporting_year"])
        self.assertEqual(records[45.0]["performance_type"], "Reported result")
        self.assertEqual(records[45.0]["reporting_year"], "2023")

    def test_target_only_sentence_has_no_reporting_year(self):
        records = _records("Our 2030 target is net zero; we will report progress.")
        for record in records:
            self.assertIsNone(record["reporting_year"])

    def test_pure_target_sentence_still_marked_target(self):
        records = _records("We aim to cut Scope 1 emissions by 50% by 2030.")
        self.assertTrue(records)
        self.assertTrue(all(r["performance_type"] == "Target" for r in records))
        self.assertTrue(all(r["target_year"] == 2030 for r in records))


class AchievedAndBaselineYearTests(unittest.TestCase):
    def test_achieved_by_past_year_is_not_turned_into_a_forecast(self):
        records = _records("Renewable share reached 45% by 2023.")
        for record in records:
            self.assertEqual(record["performance_type"], "Reported result")

    def test_historical_baseline_year_is_not_the_reporting_year(self):
        records = _by_value(_records(
            "Emissions fell 12% versus the 2019 baseline in 2024."
        ))
        self.assertEqual(records[12.0]["reporting_year"], "2024")

    def test_comparison_only_year_gives_no_reporting_year(self):
        # "compared with 2019" is the only year: it is a baseline, not a report.
        self.assertIsNone(ta._explicit_reporting_years(
            "Emissions fell 12% compared with 2019."
        ))

    def test_publication_style_year_is_only_used_when_it_is_the_sole_year(self):
        # A sentence that mentions a report year alongside a baseline should use
        # the report year; the baseline must not win.
        years = ta._explicit_reporting_years(
            "Emissions fell 10% from 2019 to 2024."
        )
        self.assertEqual([m.group(0) for m in years], ["2024"])


class ValidReportingPeriodTests(unittest.TestCase):
    def test_single_reporting_year_is_used(self):
        records = _records("We cut emissions 10% in 2024.")
        self.assertEqual(_by_value(records)[10.0]["reporting_year"], "2024")

    def test_two_reported_years_in_one_sentence_yield_no_guessed_year(self):
        # Existing conservative rule: when a sentence names more than one
        # reporting year, no year is chosen rather than guessing which value
        # belongs to which year. Behaviour is unchanged; this pins it.
        self.assertIsNone(ta._explicit_reporting_years(
            "Scope 2 emissions were 2,000 t CO2e in 2022 and 1,500 t in 2023."
        ))


class InsufficientTimelineTests(unittest.TestCase):
    def test_sentence_with_no_year_has_no_reporting_year(self):
        records = _records("We reduced emissions by 10% recently.")
        for record in records:
            self.assertIsNone(record["reporting_year"])

    def test_ambiguous_multiple_target_years_yield_no_year(self):
        # Two different target years make the sentence ambiguous; it must not
        # guess a reporting year.
        self.assertIsNone(ta._explicit_reporting_years(
            "We target 50% by 2030 and 80% by 2040."
        ))


if __name__ == "__main__":
    unittest.main()
