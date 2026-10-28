"""Regression: homonym checks use one mechanism for every company (SYNTHETIC text).

Apple expectations were checked against the original web_search function before the
refactor (0 differences over 9 sentences). Shell is included to show the mechanism is
configuration-driven, not Apple-specific. No test here uses real search results.
"""

import unittest

from company_disambiguation import is_ambiguous_company_mention


class AppleHomonymTests(unittest.TestCase):
    def test_fruit_context_without_company_context_is_ambiguous(self):
        self.assertTrue(is_ambiguous_company_mention("Apple", "Apple harvest in the orchard this autumn."))
        self.assertTrue(is_ambiguous_company_mention("Apple", "Canned apple juice recipe for kids."))
        self.assertTrue(is_ambiguous_company_mention("Apple", "Students playing a quiz about apple fruit facts."))

    def test_company_context_clears_the_homonym_check(self):
        self.assertFalse(is_ambiguous_company_mention("Apple", "Apple Inc. reported record iPhone sales."))
        self.assertFalse(is_ambiguous_company_mention("Apple", "Apple's corporate supplier operations in Cupertino."))
        self.assertFalse(is_ambiguous_company_mention("Apple", "The iPad and Apple Watch release."))
        self.assertFalse(is_ambiguous_company_mention("Apple", "Apple announced new facilities for renewable energy."))

    def test_no_food_context_is_not_flagged(self):
        self.assertFalse(is_ambiguous_company_mention("Apple", "fresh apple pie with cinnamon"))

    def test_other_companies_are_not_affected_by_apple_rules(self):
        self.assertFalse(is_ambiguous_company_mention("Samsung", "Samsung apple juice ad."))


class ShellHomonymTests(unittest.TestCase):
    """The same mechanism, with a different configuration entry."""

    def test_seashell_context_is_ambiguous_for_shell(self):
        self.assertTrue(is_ambiguous_company_mention("Shell", "Collected a shell on the beach at dawn."))
        # "seashell" is a different word and is not the company name token.
        self.assertFalse(is_ambiguous_company_mention("Shell", "Collected a seashell on the beach at dawn."))

    def test_energy_company_context_clears_the_check(self):
        self.assertFalse(is_ambiguous_company_mention("Shell", "Shell plc reported lower refinery emissions on the beach project."))
        self.assertFalse(is_ambiguous_company_mention("Shell", "Shell's oil operations reduced methane in 2023."))

    def test_unconfigured_company_is_never_flagged(self):
        self.assertFalse(is_ambiguous_company_mention("Tesla", "Tesla harvest in the orchard."))


if __name__ == "__main__":
    unittest.main()
