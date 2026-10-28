"""Regression tests for source deduplication, extraction quality, assurance scope and
their integration with the matcher and feature builder.

ALL inputs are SYNTHETIC. They test software logic only. They are not evidence about any
real company, source or document.
"""

import unittest

import numpy as np

import assurance_classifier as ac
import extraction_quality as eq
import online_evidence_matcher as matcher
import online_claim_extractor as oce
import source_dedupe as sd


class UrlNormalisationTests(unittest.TestCase):
    def test_scheme_www_tracking_fragment_and_trailing_slash_are_ignored(self):
        self.assertEqual(
            sd.normalize_url("http://www.Acme.example/report/?utm_source=x#p3"),
            sd.normalize_url("https://acme.example/report"),
        )

    def test_different_paths_remain_different(self):
        self.assertNotEqual(
            sd.normalize_url("https://acme.example/2023-report.pdf"),
            sd.normalize_url("https://acme.example/2024-report.pdf"),
        )

    def test_non_tracking_query_parameters_are_kept(self):
        self.assertNotEqual(
            sd.normalize_url("https://acme.example/r?year=2023"),
            sd.normalize_url("https://acme.example/r?year=2024"),
        )


class NearDuplicateTests(unittest.TestCase):
    BASE = "Acme reported Scope 1 emissions of 1,000 tonnes in 2023 under the GHG Protocol."

    def test_formatting_only_variant_is_a_near_duplicate(self):
        variant = "  " + self.BASE.upper().replace(" ", "  ") + "  "
        ok, score = sd.near_duplicate(self.BASE, variant)
        self.assertTrue(ok, f"score={score}")

    def test_one_word_change_in_a_short_sentence_is_not_merged(self):
        # Conservative by design: a changed word in a short sentence is not treated as the same text.
        ok, _ = sd.near_duplicate(self.BASE, self.BASE.replace("reported", "disclosed"))
        self.assertFalse(ok)

    def test_different_reporting_year_is_never_merged(self):
        ok, _ = sd.near_duplicate(self.BASE, self.BASE.replace("2023", "2024"))
        self.assertFalse(ok)

    def test_revised_figure_is_never_merged(self):
        ok, _ = sd.near_duplicate(self.BASE, self.BASE.replace("1,000", "1,100"))
        self.assertFalse(ok)

    def test_separate_assurance_statements_with_different_numbers_are_not_merged(self):
        a = "Deloitte performed a limited review of Scope 2 electricity of 500 MWh for 2023."
        b = "Deloitte performed a limited review of Scope 2 electricity of 620 MWh for 2023."
        self.assertFalse(sd.near_duplicate(a, b)[0])


class GroupingTests(unittest.TestCase):
    TEXT = "Acme reported gross Scope 1 emissions of 1,000 tonnes in 2023."

    def test_exact_copies_on_the_same_site_are_duplicates(self):
        items = [
            {"statement": self.TEXT, "source_url": "https://acme.example/r.pdf"},
            {"statement": self.TEXT, "source_url": "https://acme.example/mirror/r.pdf"},
        ]
        sd.group_candidates(items)
        self.assertEqual(items[1]["source_relation"], "duplicate")
        self.assertEqual(items[1]["duplicate_method"], "exact_content_same_site")
        self.assertTrue(sd.is_representative(items[0]))
        self.assertFalse(sd.is_representative(items[1]))

    def test_identical_text_on_different_sites_is_not_auto_merged(self):
        # Identical wording on another site does not establish a shared source.
        items = [
            {"statement": self.TEXT, "source_url": "https://acme.example/r.pdf"},
            {"statement": self.TEXT, "source_url": "https://mirror.example/acme-2023.pdf"},
        ]
        sd.group_candidates(items)
        self.assertNotEqual(items[0]["duplicate_group_id"], items[1]["duplicate_group_id"])
        self.assertEqual(items[1]["source_relation"], "potentially_related")
        self.assertIsNone(items[1]["is_duplicate_of"])
        self.assertTrue(sd.is_representative(items[1]))

    def test_different_figure_is_a_separate_group(self):
        items = [
            {"statement": self.TEXT, "source_url": "https://acme.example/r.pdf"},
            {"statement": self.TEXT.replace("1,000", "900"), "source_url": "https://acme.example/r.pdf"},
        ]
        sd.group_candidates(items)
        self.assertNotEqual(items[0]["duplicate_group_id"], items[1]["duplicate_group_id"])


class ExtractionQualityTests(unittest.TestCase):
    def test_concatenated_heading_is_malformed(self):
        status, _ = eq.assess_statement_quality(
            "SustainabilityReportEnvironmentalPerformanceClimateChangeGHGEmissionsOverview2023")
        self.assertEqual(status, eq.MALFORMED)

    def test_table_dot_leader_fragment_is_malformed(self):
        status, _ = eq.assess_statement_quality("Scope 1 . . . . . 1,234 . . 2023 . . ..... page 14 of 62")
        self.assertEqual(status, eq.MALFORMED)

    def test_broken_encoding_is_malformed(self):
        status, _ = eq.assess_statement_quality("Emissions \ufffd\ufffd fell 10% in 2024.")
        self.assertEqual(status, eq.MALFORMED)

    def test_truncated_sentence_is_incomplete(self):
        status, _ = eq.assess_statement_quality("Scope 1 emissions fell 10% in 2024 compared with")
        self.assertEqual(status, eq.INCOMPLETE)

    def test_pure_number_fragment_is_incomplete(self):
        status, _ = eq.assess_statement_quality("1,234 2,345 3,456 4,567 5,678")
        self.assertEqual(status, eq.INCOMPLETE)

    def test_complete_sentence_with_figure_is_usable(self):
        status, _ = eq.assess_statement_quality("Scope 1 emissions fell 10% in 2024 compared with 2019.")
        self.assertEqual(status, eq.USABLE)

    def test_hyphenation_break_is_kept_usable_with_a_note(self):
        status, reasons = eq.assess_statement_quality(
            "Renewable electricity was 45% in 2024 and emis- sions fell 8% overall.")
        self.assertEqual(status, eq.USABLE)
        self.assertTrue(any("hyphenation" in r for r in reasons))

    def test_original_text_is_never_modified(self):
        original = "Renewable electricity was 45% in 2024 and emis- sions fell 8% overall."
        eq.assess_statement_quality(original)
        self.assertEqual(original, "Renewable electricity was 45% in 2024 and emis- sions fell 8% overall.")


class ClaimExtractionPunctuationTests(unittest.TestCase):
    def test_comma_before_wrapped_line_is_preserved(self):
        source_text = (
            "Apple retains the projects' environmental attributes, "
            "benefiting the community,\n"
            "our company, and the environment."
        )
        document = {
            "status": "success",
            "title": "Apple Environmental Progress Report",
            "source_url": "https://www.apple.com/environment/report.pdf",
            "final_url": "https://www.apple.com/environment/report.pdf",
            "source_domain": "www.apple.com",
            "source_type": "Official company source",
            "text": source_text,
        }

        statements = oce.extract_environmental_statements(document)

        self.assertIn(
            "Apple retains the projects' environmental attributes, "
            "benefiting the community, our company, and the environment.",
            [item["statement"] for item in statements],
        )


class AssuranceClassificationTests(unittest.TestCase):
    def test_limited_assurance_with_scope_exclusion(self):
        r = ac.classify_assurance(
            "Deloitte performed a limited assurance engagement over Scope 2 electricity for fiscal year 2023. "
            "Scope 1 and 3 emissions are not subject to our review.")
        self.assertEqual(r["assurance_type"], ac.LIMITED_ASSURANCE)
        self.assertEqual(r["scopes_covered"], ["Scope 2"])
        self.assertEqual(r["scopes_excluded"], ["Scope 1", "Scope 3"])
        self.assertEqual(r["period"], "2023")

    def test_reviewer_without_stated_type_is_not_assurance(self):
        r = ac.classify_assurance("Trinity Consultants reviewed the report.")
        self.assertEqual(r["assurance_type"], ac.REVIEW_UNSPECIFIED)

    def test_reasonable_assurance_is_recognised_as_its_own_type(self):
        r = ac.classify_assurance("Our auditor provided reasonable assurance over Scope 1 and 2 for 2024.")
        self.assertEqual(r["assurance_type"], ac.REASONABLE_ASSURANCE)

    def test_conflicting_types_are_not_forced_into_one(self):
        r = ac.classify_assurance("Limited assurance over Scope 1; reasonable assurance over Scope 2.")
        self.assertEqual(r["assurance_type"], ac.UNKNOWN)
        self.assertEqual(r["status"], "ambiguous_assurance_type")

    def test_empty_text_is_unknown_not_inferred(self):
        self.assertEqual(ac.classify_assurance("")["assurance_type"], ac.UNKNOWN)

    def test_partial_scope_does_not_support_the_whole_claim(self):
        r = ac.classify_assurance(
            "Deloitte performed a limited assurance engagement over Scope 2 electricity for fiscal year 2023. "
            "Scope 1 and 3 emissions are not subject to our review.")
        self.assertTrue(ac.assurance_supports_scope(r, [2]))
        self.assertFalse(ac.assurance_supports_scope(r, [1, 2, 3]))


class MatcherIntegrityTests(unittest.TestCase):
    CLAIM = ("Samsung reported that gross Scope 1 and 2 emissions decreased by 40% compared with its 2019 "
             "baseline for global operations under the GHG Protocol in fiscal year 2023.")
    EVIDENCE = ("Samsung reported that gross Scope 1 and 2 emissions decreased by 40% compared with the 2019 "
                "baseline for global operations under the GHG Protocol in fiscal year 2023 in its sustainability report.")

    class _Model:
        def encode(self, texts, **kwargs):
            return np.ones((len(texts), 3))

    def _run(self, statements, score=0.8):
        return matcher.match_online_evidence(
            [self.CLAIM], statements, self._Model(),
            cos_sim=lambda a, b: np.full((len(a), len(b)), score),
        )[0]

    def test_same_document_at_one_url_counts_once(self):
        result = self._run([
            {"statement": self.EVIDENCE, "source_url": "https://samsung.example/r.pdf", "source_role": "external_source"},
            {"statement": self.EVIDENCE, "source_url": "https://samsung.example/r.pdf?utm_source=x", "source_role": "external_source"},
        ])
        self.assertEqual(result["independent_support_count"], 1)

    def test_identical_text_on_two_sites_is_two_documents_with_uncertain_relation(self):
        result = self._run([
            {"statement": self.EVIDENCE, "source_url": "https://samsung.example/r.pdf", "source_role": "external_source"},
            {"statement": self.EVIDENCE, "source_url": "https://mirror.example/s.pdf", "source_role": "external_source"},
        ])
        self.assertEqual(result["independent_support_count"], 2)
        self.assertEqual(result["potentially_related_count"], 1)

    def test_two_distinct_sources_count_as_two(self):
        result = self._run([
            {"statement": self.EVIDENCE, "source_url": "https://samsung.example/r.pdf", "source_role": "external_source"},
            {"statement": self.EVIDENCE.replace("sustainability report", "annual report"),
             "source_url": "https://other.example/a.pdf", "source_role": "external_source"},
        ])
        self.assertEqual(result["independent_support_count"], 2)

    def test_malformed_text_is_never_supporting_evidence(self):
        result = self._run([{
            "statement": "SustainabilityReportEnvironmentalPerformanceClimateChangeGHGEmissionsOverview2023",
            "source_url": "https://x.example/a", "source_role": "external_source",
        }])
        self.assertEqual(result["evidence_status"], "candidates_found_low_quality_extraction")
        self.assertEqual(result["independent_support_count"], 0)

    def test_compatible_pair_still_passes_as_support(self):
        result = self._run([{
            "statement": self.EVIDENCE, "source_url": "https://samsung.example/r.pdf", "source_role": "external_source",
        }])
        self.assertEqual(result["evidence_status"], "potentially_relevant_evidence_found")


class FeatureExclusionTests(unittest.TestCase):
    def test_duplicate_copy_does_not_reach_feature_construction(self):
        import feature_builder
        claim = "Acme reported Scope 1 emissions of 1,000 tonnes in 2023."
        matches = [{"claim": claim, "matches": [
            {"matched_evidence": claim, "similarity": 0.8, "match_label": "potentially_relevant",
             "comparability_status": "COMPATIBLE", "quality_status": "USABLE",
             "source_url": "https://a.example/r", "scoring_eligible": True,
             "is_duplicate_of": None, "duplicate_group_id": "grp-1"},
            {"matched_evidence": claim, "similarity": 0.8, "match_label": "potentially_relevant",
             "comparability_status": "COMPATIBLE", "quality_status": "USABLE",
             "source_url": "https://mirror.example/r", "scoring_eligible": True,
             "is_duplicate_of": "grp-1", "duplicate_group_id": "grp-1"},
        ]}]
        nli = [{"claim": claim, "evidence": claim, "source_url": "https://a.example/r",
                "nli_result": "ENTAILMENT", "scoring_eligible": True}]
        features = feature_builder.build_features_from_results(matches, nli)
        rows = features.to_dict("records") if hasattr(features, "to_dict") else features
        self.assertLessEqual(sum(1 for row in rows if row.get("evidence_available") == 1), 1)


if __name__ == "__main__":
    unittest.main()
