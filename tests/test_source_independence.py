"""Regression: independent evidence is preserved; duplicates need a same-document signal.

SYNTHETIC fixtures with realistic structure. They test the production grouping and matching
functions directly (no mocks of the logic under review). They are not evidence about any
real organisation's publications.
"""

import unittest

import numpy as np

import online_evidence_matcher as matcher
import source_dedupe as sd

FIGURE = "Acme Industries reported Scope 1 emissions of 1,000 tonnes in 2023 under the GHG Protocol."
SITE_REPORT = ("Acme Industries reported Scope 1 emissions of 1,000 tonnes in 2023 under the GHG Protocol "
               "in its 2023 sustainability report.")


def _group(*items):
    return sd.group_candidates([dict(item) for item in items])


class SameDocumentTests(unittest.TestCase):
    def test_same_document_through_tracking_url_variants_is_one_document(self):
        a, b = _group(
            {"statement": SITE_REPORT, "source_url": "https://acme.example/report-2023.pdf"},
            {"statement": SITE_REPORT, "source_url": "http://www.acme.example/report-2023.pdf/?utm_source=news#p4"},
        )
        self.assertEqual(b["source_relation"], "duplicate")
        self.assertEqual(b["is_duplicate_of"], a["duplicate_group_id"])

    def test_exact_copy_on_the_same_site_is_a_duplicate(self):
        a, b = _group(
            {"statement": SITE_REPORT, "source_url": "https://acme.example/en/report-2023.pdf"},
            {"statement": SITE_REPORT, "source_url": "https://acme.example/ko/report-2023.pdf"},
        )
        self.assertEqual(b["source_relation"], "duplicate")
        self.assertEqual(b["duplicate_method"], "exact_content_same_site")


class IndependentSourceTests(unittest.TestCase):
    def test_two_independent_organisations_with_identical_figures_are_both_kept(self):
        a, b = _group(
            {"statement": FIGURE, "source_url": "https://acme.example/report-2023.pdf"},
            {"statement": FIGURE, "source_url": "https://regulator.example/filings/acme-2023.pdf"},
        )
        self.assertIsNone(a["is_duplicate_of"])
        self.assertIsNone(b["is_duplicate_of"], "identical figures alone must not merge sources")
        self.assertEqual(b["source_relation"], "potentially_related")
        self.assertNotEqual(a["duplicate_group_id"], b["duplicate_group_id"])

    def test_two_separate_reports_from_one_organisation_are_not_merged(self):
        annual = FIGURE + " This is the annual report."
        sustainability = FIGURE + " This is the sustainability report."
        a, b = _group(
            {"statement": annual, "source_url": "https://acme.example/annual-2023.pdf"},
            {"statement": sustainability, "source_url": "https://acme.example/sustainability-2023.pdf"},
        )
        self.assertIsNone(b["is_duplicate_of"])
        self.assertNotEqual(a["duplicate_group_id"], b["duplicate_group_id"])

    def test_similar_text_with_different_figures_is_not_related(self):
        a, b = _group(
            {"statement": FIGURE, "source_url": "https://acme.example/r.pdf"},
            {"statement": FIGURE.replace("1,000", "1,250"), "source_url": "https://regulator.example/r.pdf"},
        )
        self.assertEqual(b["source_relation"], "representative")
        self.assertIsNone(b["potentially_related_to"])

    def test_same_figures_with_a_different_reporting_year_are_not_related(self):
        a, b = _group(
            {"statement": FIGURE, "source_url": "https://acme.example/r.pdf"},
            {"statement": FIGURE.replace("2023", "2024"), "source_url": "https://regulator.example/r.pdf"},
        )
        self.assertEqual(b["source_relation"], "representative")
        self.assertIsNone(b["is_duplicate_of"])


class ProvenanceLinkTests(unittest.TestCase):
    def test_syndicated_copy_is_a_duplicate_only_with_an_explicit_provenance_link(self):
        original = "https://acme.example/press/2023-emissions"
        a, b = _group(
            {"statement": FIGURE, "source_url": original},
            {"statement": FIGURE, "source_url": "https://newswire.example/acme-emissions",
             "original_source_url": original},
        )
        self.assertEqual(b["source_relation"], "duplicate")
        self.assertEqual(b["duplicate_method"], "original_source_link")

    def test_two_copies_sharing_one_original_are_one_source(self):
        original = "https://acme.example/press/2023-emissions"
        a, b, c = _group(
            {"statement": FIGURE, "source_url": original},
            {"statement": FIGURE, "source_url": "https://site-one.example/a", "original_source_url": original},
            {"statement": FIGURE, "source_url": "https://site-two.example/b", "original_source_url": original},
        )
        self.assertEqual(b["is_duplicate_of"], a["duplicate_group_id"])
        self.assertEqual(c["is_duplicate_of"], a["duplicate_group_id"])

    def test_provenance_fields_survive_grouping(self):
        original = "https://acme.example/press/2023-emissions"
        items = _group(
            {"statement": FIGURE, "source_url": original, "publisher": "Acme Industries"},
            {"statement": FIGURE, "source_url": "https://newswire.example/x", "original_source_url": original,
             "publisher": "Newswire"},
        )
        self.assertEqual(items[1]["source_url"], "https://newswire.example/x")
        self.assertEqual(items[1]["original_source_url"], original)
        self.assertEqual(items[1]["publisher"], "Newswire")
        self.assertTrue(items[1]["canonical_url"])


class MatcherLevelTests(unittest.TestCase):
    CLAIM = ("Acme reported that gross Scope 1 emissions decreased by 10% compared with its 2019 baseline "
             "for global operations under the GHG Protocol in fiscal year 2023.")
    EVIDENCE = ("Acme reported that gross Scope 1 emissions decreased by 10% compared with the 2019 baseline "
                "for global operations under the GHG Protocol in fiscal year 2023 in its sustainability report.")

    class _Model:
        def encode(self, texts, **kwargs):
            return np.ones((len(texts), 3))

    def _run(self, statements):
        return matcher.match_online_evidence(
            [self.CLAIM], statements, self._Model(),
            cos_sim=lambda a, b: np.full((len(a), len(b)), 0.85),
        )[0]

    def test_independent_sources_both_reach_matching_and_are_flagged_uncertain(self):
        result = self._run([
            {"statement": self.EVIDENCE, "source_url": "https://acme.example/r.pdf", "source_role": "external_source"},
            {"statement": self.EVIDENCE, "source_url": "https://regulator.example/a.pdf", "source_role": "external_source"},
        ])
        self.assertEqual(len(result["matches"]), 2)
        self.assertEqual(result["independent_support_count"], 2)
        self.assertEqual(result["potentially_related_count"], 1)
        urls = {m["source_url"] for m in result["matches"]}
        self.assertEqual(urls, {"https://acme.example/r.pdf", "https://regulator.example/a.pdf"})


if __name__ == "__main__":
    unittest.main()
