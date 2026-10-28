"""Regression: assurance records are classified from source text, carried through the real
extraction, matching and saving path, and never change matching, NLI or risk results.

SYNTHETIC fixtures only. No network, no model download. The matcher is run with an injected
fake similarity function.
"""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

import assurance_classifier as ac
import online_claim_extractor as oce
import online_evidence_matcher as matcher
from timeline_analyzer import compare_measurement_compatibility

NOT_PROOF = ac.NOT_PROOF_OF_CLAIM_TRUTH
NOT_INDEPENDENCE = ac.NOT_PROOF_OF_INDEPENDENCE

APEX_STATEMENT_TEXT = (
    "INDEPENDENT ASSURANCE STATEMENT\n"
    "Apex Companies, LLC (Apex) was engaged by Acme Inc. (Acme) to conduct a limited "
    "assurance engagement over Scope 2 emissions data for fiscal year 2024.\n"
    "Apex Companies, LLC signed this statement on April 15th, 2026.\n"
    "Our Conclusion\n"
    "Based on our limited assurance procedures, the Scope 2 greenhouse gas emissions "
    "assertions shown above are materially correct.\n"
    "Apex Companies, LLC Page 2 of 2"
)

DELOITTE_TEXT = (
    "1.11 Independent accountant’s review report\n"
    "Deloitte & Touche LLP\n"
    "To the Board of Directors of Microsoft Corporation\n"
    "We have reviewed management of Microsoft Corporation’s assertion that the specified "
    "environmental information in Section 1 of the Fact Sheet for the fiscal year ended "
    "June 30, 2024 is presented in accordance with the reporting criteria.\n"
    "Further, information relating to periods prior to the year-ended June 30, 2024 or "
    "forward-looking statements, targets, goals, and progress against goals, was not "
    "subject to our review and we do not express a conclusion or any form of assurance "
    "on such information.\n"
    "Based on our review, we are not aware of any material modifications to management’s "
    "assertion in order for it to be fairly stated.\n"
    "May 29, 2025"
)


class AssuranceClassificationUnitTests(unittest.TestCase):
    def _record(self, text, **kwargs):
        options = {"provider": "Apex Companies, LLC", "source_url": "https://acme.example/report.pdf"}
        options.update(kwargs)
        return ac.build_assurance_record(text, **options)

    # --- verified / limited / reasonable -------------------------------------------------
    def test_limited_assurance_is_verified_with_provider_url_scope_metric_and_period(self):
        record = self._record(
            "Apex performed a limited assurance engagement over Scope 2 electricity for fiscal year 2023. "
            "Scope 1 and 3 emissions are not subject to our review."
        )
        self.assertEqual(record["status"], ac.STATUS_VERIFIED)
        self.assertEqual(record["assurance_level"], ac.LEVEL_LIMITED)
        self.assertEqual(record["assurance_type"], ac.LIMITED_ASSURANCE)
        self.assertEqual(record["provider"], "Apex Companies, LLC")
        self.assertEqual(record["source_url"], "https://acme.example/report.pdf")
        self.assertEqual(record["scopes_covered"], ["Scope 2"])
        self.assertEqual(record["scopes_excluded"], ["Scope 1", "Scope 3"])
        self.assertEqual(record["metrics_covered"], ["electricity"])
        self.assertEqual(record["reporting_period"], "2023")
        self.assertEqual(record["missing_fields"], [])

    def test_reasonable_assurance_is_verified_at_reasonable_level(self):
        record = self._record("Our auditor provided reasonable assurance over Scope 1 and 2 for fiscal year 2024.")
        self.assertEqual(record["status"], ac.STATUS_VERIFIED)
        self.assertEqual(record["assurance_level"], ac.LEVEL_REASONABLE)
        self.assertEqual(record["scopes_covered"], ["Scope 1", "Scope 2"])

    # --- unverified ----------------------------------------------------------------------
    def test_limited_review_without_assurance_level_is_unverified_not_limited(self):
        record = self._record("Apex performed a limited review of the Scope 1 emissions data for fiscal year 2024.")
        self.assertEqual(record["assurance_type"], ac.LIMITED_REVIEW)
        self.assertEqual(record["assurance_level"], ac.LEVEL_UNKNOWN)
        self.assertEqual(record["status"], ac.STATUS_UNVERIFIED)

    def test_reviewer_without_stated_type_is_unverified_and_level_unknown(self):
        record = self._record("Trinity Consultants reviewed the Scope 1 emissions data.")
        self.assertEqual(record["assurance_type"], ac.REVIEW_UNSPECIFIED)
        self.assertEqual(record["status"], ac.STATUS_UNVERIFIED)
        self.assertEqual(record["assurance_level"], ac.LEVEL_UNKNOWN)

    def test_agreed_upon_procedures_is_not_reported_as_an_assurance_level(self):
        record = self._record("Apex performed agreed-upon procedures over Scope 1 emissions for fiscal year 2024.")
        self.assertEqual(record["assurance_type"], ac.AGREED_UPON_PROCEDURES)
        self.assertEqual(record["assurance_level"], ac.LEVEL_NOT_ASSURANCE)
        self.assertEqual(record["status"], ac.STATUS_UNVERIFIED)

    def test_deloitte_style_review_report_stays_unverified_with_no_invented_scope(self):
        record = self._record(DELOITTE_TEXT, provider="Deloitte & Touche LLP",
                              stated_period_text="fiscal year ended June 30, 2024")
        self.assertEqual(record["status"], ac.STATUS_UNVERIFIED)
        self.assertEqual(record["assurance_level"], ac.LEVEL_UNKNOWN)
        self.assertEqual(record["scopes_covered"], [])
        self.assertEqual(record["scopes_excluded"], [])
        self.assertEqual(record["reporting_period"], "2024")
        self.assertEqual(record["reporting_period_text"], "fiscal year ended June 30, 2024")

    # --- ambiguous -----------------------------------------------------------------------
    def test_conflicting_assurance_types_are_ambiguous_with_no_single_type(self):
        record = self._record("Limited assurance over Scope 1; reasonable assurance over Scope 2.")
        self.assertEqual(record["status"], ac.STATUS_AMBIGUOUS)
        self.assertEqual(record["assurance_type"], ac.UNKNOWN)
        self.assertEqual(record["assurance_level"], ac.LEVEL_UNKNOWN)

    def test_conflicting_fiscal_years_leave_period_unknown_without_inventing_one(self):
        record = self._record(
            "Apex performed a limited assurance engagement over Scope 2 for fiscal year 2023 "
            "and for fiscal year 2024."
        )
        self.assertIsNone(record["reporting_period"])
        self.assertIn("reporting_period", record["missing_fields"])
        self.assertIn("More than one fiscal year", record["rationale"])
        self.assertEqual(record["status"], ac.STATUS_VERIFIED)

    # --- missing -------------------------------------------------------------------------
    def test_empty_or_none_text_is_missing_not_inferred(self):
        for text in ("", "   ", None):
            record = self._record(text)
            self.assertEqual(record["status"], ac.STATUS_MISSING, repr(text))
            self.assertEqual(record["assurance_type"], ac.UNKNOWN)
            self.assertIn("scope", record["missing_fields"])

    def test_missing_provider_or_source_url_is_missing_and_recorded_as_null(self):
        record = self._record("Apex performed a limited assurance engagement over Scope 2.", provider="", source_url="  ")
        self.assertEqual(record["status"], ac.STATUS_MISSING)
        self.assertIsNone(record["provider"])
        self.assertIsNone(record["source_url"])
        self.assertIn("provider", record["missing_fields"])
        self.assertIn("source_url", record["missing_fields"])
        self.assertEqual(record["assurance_type"], ac.LIMITED_ASSURANCE)

    def test_company_authored_statement_is_not_assurance_and_gets_no_scope(self):
        record = self._record("Acme reports Scope 1 emissions fell 8% in fiscal year 2024.", provider="", source_url="")
        self.assertEqual(record["status"], ac.STATUS_NOT_ASSURANCE)
        self.assertEqual(record["scopes_covered"], [])
        self.assertEqual(record["metrics_covered"], [])

    # --- malformed -----------------------------------------------------------------------
    def test_non_string_inputs_are_malformed_and_nothing_is_inferred(self):
        for value in (12345, ["limited assurance"], {"text": "limited assurance"}, b"limited assurance"):
            record = self._record(value)
            self.assertEqual(record["status"], ac.STATUS_MALFORMED, repr(value))
            self.assertEqual(record["assurance_type"], ac.UNKNOWN)
            self.assertEqual(record["scopes_covered"], [])

    def test_non_string_provider_and_url_are_recorded_as_null(self):
        record = self._record("Apex performed a limited assurance engagement over Scope 2.",
                              provider=["Apex"], source_url={"u": 1})
        self.assertIsNone(record["provider"])
        self.assertIsNone(record["source_url"])

    # --- negation, targets, scopes ------------------------------------------------------
    def test_negated_assurance_phrase_is_not_counted_as_a_stated_type(self):
        record = self._record("Apex did not provide reasonable assurance over Scope 1 emissions.")
        self.assertNotEqual(record["assurance_type"], ac.REASONABLE_ASSURANCE)
        self.assertEqual(record["status"], ac.STATUS_NOT_ASSURANCE)

    def test_target_years_are_not_reporting_periods(self):
        record = self._record("Apex performed a limited assurance review of Scope 2 emissions. Targets for 2030 are not subject to our review.")
        self.assertIsNone(record["reporting_period"])
        self.assertNotIn("2030", str(record["reporting_period"]))

    def test_bare_scope_mention_without_assurance_language_is_not_covered(self):
        record = self._record(
            "Apex performed a limited assurance engagement over Scope 2 emissions for fiscal year 2024. "
            "Acme set a Scope 1 target for 2030."
        )
        self.assertEqual(record["scopes_covered"], ["Scope 2"])

    def test_scope_excluded_in_one_clause_is_not_covered_by_the_assurance_clause(self):
        record = self._record(
            "Apex performed a limited assurance engagement over Scope 2 emissions for fiscal year 2024. "
            "Scope 1 emissions are excluded from the assurance engagement."
        )
        self.assertEqual(record["scopes_covered"], ["Scope 2"])
        self.assertEqual(record["scopes_excluded"], ["Scope 1"])
        self.assertTrue(ac.assurance_supports_scope(ac.classify_assurance(
            "Apex performed a limited assurance engagement over Scope 2 emissions for fiscal year 2024. "
            "Scope 1 emissions are excluded from the assurance engagement."), [2]))

    def test_partial_scope_does_not_support_full_claim(self):
        classification = ac.classify_assurance(
            "Apex performed a limited assurance engagement over Scope 2 for fiscal year 2024. "
            "Scope 3 emissions are not subject to our review."
        )
        self.assertFalse(ac.assurance_supports_scope(classification, [1, 2, 3]))
        self.assertFalse(ac.assurance_supports_scope(classification, [3]))

    # --- record contract -----------------------------------------------------------------
    def test_every_record_carries_both_non_proof_limitations(self):
        for text in ("", "limited assurance over Scope 2", "Trinity reviewed the data.", 5):
            record = self._record(text)
            self.assertEqual(record["limitations"], [NOT_PROOF, NOT_INDEPENDENCE])

    def test_provider_and_url_are_recorded_verbatim_not_inferred_from_text(self):
        record = self._record(
            "Apex performed a limited assurance engagement over Scope 2 for fiscal year 2024.",
            provider="", source_url="https://acme.example/report.pdf",
        )
        self.assertIsNone(record["provider"])
        self.assertEqual(record["source_url"], "https://acme.example/report.pdf")
        self.assertNotIn("Apex", str(record["provider"]))

    def test_no_record_claims_assurance_proves_truth_or_independence(self):
        record = self._record("Apex performed a reasonable assurance engagement over Scope 2 emissions for fiscal year 2024.")
        self.assertEqual(record["status"], ac.STATUS_VERIFIED)
        self.assertIn(NOT_PROOF, record["limitations"])
        self.assertIn(NOT_INDEPENDENCE, record["limitations"])


class AssuranceSummaryTests(unittest.TestCase):
    def test_older_saved_record_without_assurance_is_not_assessed(self):
        self.assertEqual(ac.summarize_assurance_record(None), "Not assessed (no assurance record stored)")

    def test_malformed_stored_value_is_reported_as_malformed(self):
        self.assertEqual(ac.summarize_assurance_record("limited"), "Malformed assurance record")
        self.assertEqual(ac.summarize_assurance_record({"status": "something_else"}), "Malformed assurance record")

    def test_verified_summary_states_level_provider_scope_and_period(self):
        record = ac.build_assurance_record(
            "Apex performed a limited assurance engagement over Scope 2 for fiscal year 2024.",
            provider="Apex Companies, LLC", source_url="https://acme.example/report.pdf")
        self.assertEqual(
            ac.summarize_assurance_record(record),
            "Limited assurance by Apex Companies, LLC (covers Scope 2; period 2024)",
        )

    def test_unverified_summary_does_not_claim_a_level(self):
        record = ac.build_assurance_record("Trinity Consultants reviewed the data.",
                                           provider="Trinity Consultants", source_url="https://x.example/a")
        self.assertIn("assurance level not stated", ac.summarize_assurance_record(record))
        self.assertNotIn("Limited", ac.summarize_assurance_record(record))


class ProductionExtractionIntegrationTests(unittest.TestCase):
    def test_embedded_assurance_statement_items_carry_a_verified_record_from_the_section(self):
        document = {
            "status": "success", "title": "Acme Environmental Report",
            "source_domain": "www.acme.example", "source_type": "Official company source",
            "source_url": "https://www.acme.example/report.pdf",
            "final_url": "https://www.acme.example/report.pdf",
            "text": APEX_STATEMENT_TEXT,
        }
        items = oce.extract_embedded_assurance_statements(document, "Acme")
        self.assertGreaterEqual(len(items), 1)
        for item in items:
            record = item["assurance"]
            self.assertEqual(record["status"], ac.STATUS_VERIFIED)
            self.assertEqual(record["assurance_level"], ac.LEVEL_LIMITED)
            self.assertEqual(record["provider"], "Apex Companies, LLC")
            self.assertEqual(record["source_url"], "https://www.acme.example/report.pdf")
            self.assertEqual(record["scopes_covered"], ["Scope 2"])
            self.assertEqual(record["reporting_period"], "2024")
            self.assertEqual(record["scopes_excluded"], [])
            self.assertEqual(record["limitations"], [NOT_PROOF, NOT_INDEPENDENCE])

    def test_deloitte_review_item_keeps_existing_flags_and_adds_unverified_record(self):
        import app  # noqa: F401  (confirms the real app module imports with the change)

        document = {
            "status": "success", "title": "2025 Microsoft Environmental Data Fact Sheet",
            "source_type": "Official company source", "source_domain": "cdn-dynmedia-1.microsoft.com",
            "source_url": "https://cdn-dynmedia-1.microsoft.com/fact-sheet.pdf",
            "final_url": "https://cdn-dynmedia-1.microsoft.com/fact-sheet.pdf",
            "text": DELOITTE_TEXT + "\nThe emissions data is in our environmental report.",
        }
        items = [i for i in oce.extract_embedded_assurance_statements(document, "Microsoft")
                 if i.get("assurance_report")]
        self.assertGreaterEqual(len(items), 1)
        record = items[0]["assurance"]
        self.assertTrue(items[0]["assurance_report"])
        self.assertEqual(items[0]["covered_fiscal_period"], "fiscal year ended June 30, 2024")
        self.assertEqual(record["status"], ac.STATUS_UNVERIFIED)
        self.assertEqual(record["provider"], "Deloitte & Touche LLP")
        self.assertEqual(record["source_url"], "https://cdn-dynmedia-1.microsoft.com/fact-sheet.pdf")
        self.assertEqual(record["reporting_period_text"], "fiscal year ended June 30, 2024")
        self.assertEqual(record["assurance_level"], ac.LEVEL_UNKNOWN)

    def test_company_authored_text_gets_no_assurance_record(self):
        document = {
            "status": "success", "source_url": "https://www.acme.example/report.pdf",
            "text": "Acme reduced Scope 1 emissions by 8% in fiscal year 2024.",
        }
        self.assertEqual(oce.extract_embedded_assurance_statements(document, "Acme"), [])


class FakeModel:
    def encode(self, texts, **kwargs):
        return np.ones((len(texts), 3))


def _fixed_cos_sim(score):
    def cos(claim_embeddings, evidence_embeddings):
        return np.full((len(claim_embeddings), len(evidence_embeddings)), score)
    return cos


CLAIM = "Acme reports that Scope 2 emissions decreased by 40% in fiscal year 2024 under the GHG Protocol."
EVIDENCE_STATEMENT = (
    "Apex performed a limited assurance engagement over Scope 2 emissions for fiscal year 2024 "
    "and found them materially correct."
)


class PipelineMatchingIntegrationTests(unittest.TestCase):
    def _evidence(self, with_assurance=True):
        document = {
            "status": "success", "source_domain": "www.acme.example", "source_type": "Official company source",
            "source_url": "https://www.acme.example/report.pdf",
            "final_url": "https://www.acme.example/report.pdf", "title": "Acme Environmental Report",
            "text": APEX_STATEMENT_TEXT,
        }
        items = oce.extract_embedded_assurance_statements(document, "Acme")
        if not with_assurance:
            for item in items:
                item.pop("assurance", None)
                item.pop("assurance_report", None)
        return items

    def test_assurance_metadata_reaches_match_records_without_changing_similarity(self):
        with_assurance = self._evidence(True)
        without_assurance = self._evidence(False)
        cos = _fixed_cos_sim(0.83)
        matched = matcher.match_online_evidence([CLAIM], with_assurance, FakeModel(), cos_sim=cos)
        plain = matcher.match_online_evidence([CLAIM], without_assurance, FakeModel(), cos_sim=cos)
        self.assertTrue(matched)
        match_with = matched[0]["matches"][0]
        match_without = plain[0]["matches"][0]
        self.assertEqual(match_with["similarity"], match_without["similarity"])
        self.assertEqual(match_with["assurance"]["status"], ac.STATUS_VERIFIED)
        self.assertIsNone(match_without.get("assurance"))

    def test_app_claim_rows_show_the_assurance_summary_from_the_real_match_shape(self):
        import app

        analysis = {
            "company": "Acme",
            "company_claims": [{"statement": CLAIM}],
            "matching_results": [{
                "claim": CLAIM,
                "evidence_status": "relevant_match",
                "matches": [{
                    "matched_evidence": EVIDENCE_STATEMENT,
                    "source_url": "https://www.acme.example/report.pdf",
                    "source_title": "Acme report",
                    "similarity": 0.83,
                    "assurance": ac.build_assurance_record(
                        EVIDENCE_STATEMENT, provider="Apex Companies, LLC",
                        source_url="https://www.acme.example/report.pdf"),
                }],
            }],
            "features": [],
            "nli_results": [],
        }
        rows, _, _ = app.dashboard_claim_rows(analysis)
        self.assertEqual(rows[0]["assurance"], "Limited assurance by Apex Companies, LLC (covers Scope 2; period 2024)")
        self.assertEqual(rows[0]["similarity"], 0.83)

    def test_older_saved_match_without_assurance_key_shows_not_assessed(self):
        import app

        analysis = {
            "company": "Acme",
            "company_claims": [{"statement": CLAIM}],
            "matching_results": [{"claim": CLAIM, "evidence_status": "relevant_match",
                                  "matches": [{"matched_evidence": EVIDENCE_STATEMENT,
                                               "source_url": "https://x.example/a"}]}],
            "features": [], "nli_results": [],
        }
        rows, _, _ = app.dashboard_claim_rows(analysis)
        self.assertEqual(rows[0]["assurance"], "Not assessed (no assurance record stored)")

    def test_assurance_metadata_does_not_change_risk_features(self):
        from feature_builder import build_features_from_results

        matches = matcher.match_online_evidence(
            [CLAIM], self._evidence(True), FakeModel(), cos_sim=_fixed_cos_sim(0.83))
        with_meta = copy.deepcopy(matches)
        without_meta = copy.deepcopy(matches)
        for result in without_meta:
            for match in result["matches"]:
                match.pop("assurance", None)
        features_with = build_features_from_results(with_meta, [])
        features_without = build_features_from_results(without_meta, [])
        pd.testing.assert_frame_equal(
            pd.DataFrame(features_with), pd.DataFrame(features_without))

    def test_assurance_record_is_persisted_in_saved_analysis_json_and_reloads(self):
        import app

        matches = matcher.match_online_evidence(
            [CLAIM], self._evidence(True), FakeModel(), cos_sim=_fixed_cos_sim(0.83))
        analysis = {
            "company": "Acme Persist Co",
            "collection": {"documents": []},
            "company_claims": [{"statement": CLAIM}],
            "matching_results": matches,
            "nli_results": [],
            "features": [],
            "timeline_records": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            analyses_dir = Path(temp_dir)
            with patch.object(app, "ANALYSES_DIR", analyses_dir), \
                    patch.object(app, "save_timeline_records", return_value=0):
                app.persist_analysis(analysis)
            saved_path = Path(analysis["analysis_path"])
            with saved_path.open(encoding="utf-8") as file:
                saved = json.load(file)
        saved_match = saved["matching_results"][0]["matches"][0]
        self.assertEqual(saved_match["assurance"]["status"], ac.STATUS_VERIFIED)
        self.assertEqual(saved_match["assurance"]["provider"], "Apex Companies, LLC")
        self.assertEqual(saved_match["assurance"]["source_url"], "https://www.acme.example/report.pdf")
        self.assertEqual(saved_match["assurance"]["scopes_covered"], ["Scope 2"])
        self.assertEqual(
            saved["matching_results"][0]["matches"][0]["similarity"],
            matches[0]["matches"][0]["similarity"],
        )

    def test_older_saved_analysis_without_assurance_still_loads_and_renders(self):
        import app

        older = {
            "company": "Old Co", "analysis_id": "older", "company_claims": [{"statement": CLAIM}],
            "matching_results": [{"claim": CLAIM, "evidence_status": "relevant_match",
                                  "matches": [{"matched_evidence": EVIDENCE_STATEMENT,
                                               "source_url": "https://x.example/a"}]}],
            "features": [], "nli_results": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            Path(temp_dir, "old_co_older.json").write_text(json.dumps(older), encoding="utf-8")
            with patch.object(app, "ANALYSES_DIR", Path(temp_dir)):
                loaded, load_errors = app.load_saved_analyses()
        self.assertEqual(load_errors, [])
        self.assertEqual(len(loaded), 1)
        rows, _, _ = app.dashboard_claim_rows(loaded[0])
        self.assertEqual(rows[0]["assurance"], "Not assessed (no assurance record stored)")


class AssuranceEligibilityGateTests(unittest.TestCase):
    URL = "https://acme.example/environment/report.pdf"
    CLAIM = (
        "Acme reported gross Scope 2 emissions decreased by 10% compared with "
        "the 2019 baseline for global operations under the GHG Protocol in "
        "fiscal year 2024."
    )
    REVIEWED_TEXT = (
        "Apex performed a limited assurance engagement over Scope 2 emissions "
        "for fiscal year 2024. The reviewed data stated: " + CLAIM
    )
    ATTRIBUTION = (
        "Explicit assurance-section heading and named issuer in the source text."
    )

    def _metadata(self, text=None, **overrides):
        record = ac.build_assurance_record(
            text or self.REVIEWED_TEXT,
            provider="Apex Companies, LLC",
            source_url=self.URL,
        )
        metadata = {
            "assurance": record,
            "publisher": "Apex Companies, LLC",
            "source_type": (
                "Independent assurance statement embedded in a company-hosted report"
            ),
            "source_role": "independent_third_party_source",
            "source_url": self.URL,
            "original_source_url": self.URL,
            "attribution_basis": self.ATTRIBUTION,
        }
        metadata.update(overrides)
        return metadata

    def test_explicit_relevant_assurance_can_pass_the_assurance_gate(self):
        status, _ = compare_measurement_compatibility(
            self.CLAIM,
            self.CLAIM,
            self._metadata(),
        )
        self.assertEqual(status, "COMPATIBLE")

    def test_assurance_without_baseline_coverage_is_inconclusive(self):
        text = (
            "Apex performed a limited assurance engagement over Scope 2 "
            "emissions for fiscal year 2024. The reviewed data stated: "
            "Acme reported gross Scope 2 emissions decreased by 10% for "
            "global operations under the GHG Protocol in fiscal year 2024."
        )
        status, reason = compare_measurement_compatibility(
            self.CLAIM,
            text,
            self._metadata(text),
        )
        self.assertEqual(status, "INCONCLUSIVE")
        self.assertIn("baseline", reason.lower())

    def test_explicit_baseline_exclusion_is_not_overridden_by_a_baseline_mention(self):
        text = (
            "Apex performed a limited assurance engagement over Scope 2 "
            "emissions for fiscal year 2024. The 2019 baseline was not "
            "subject to our review."
        )
        status, reason = compare_measurement_compatibility(
            self.CLAIM,
            text,
            self._metadata(text),
        )
        self.assertEqual(status, "INCONCLUSIVE")
        self.assertIn("excluded", reason.lower())

    def test_missing_assurance_scope_metric_or_period_is_inconclusive(self):
        incomplete_records = [
            "Apex performed a limited assurance engagement over emissions "
            "for fiscal year 2024.",
            "Apex performed a limited assurance engagement over Scope 2 "
            "for fiscal year 2024.",
            "Apex performed a limited assurance engagement over Scope 2 emissions.",
        ]
        for text in incomplete_records:
            with self.subTest(text=text):
                status, _ = compare_measurement_compatibility(
                    self.CLAIM,
                    text,
                    self._metadata(text),
                )
                self.assertEqual(status, "INCONCLUSIVE")

    def test_assurance_excluding_the_claimed_scope_is_incompatible(self):
        text = (
            "Apex performed a limited assurance engagement over Scope 2 "
            "emissions for fiscal year 2024. Scope 1 emissions are not "
            "subject to our review."
        )
        claim = (
            "Acme reported Scope 1 emissions decreased by 10% in fiscal "
            "year 2024."
        )
        status, reason = compare_measurement_compatibility(
            claim,
            text,
            self._metadata(text),
        )
        self.assertEqual(status, "INCOMPATIBLE")
        self.assertIn("excludes", reason.lower())

    def test_provider_name_without_explicit_source_attribution_is_inconclusive(self):
        status, reason = compare_measurement_compatibility(
            self.CLAIM,
            self.CLAIM,
            self._metadata(attribution_basis=""),
        )
        self.assertEqual(status, "INCONCLUSIVE")
        self.assertIn("attribution", reason.lower())

    def test_accountant_review_without_assurance_level_is_not_scoring_evidence(self):
        report = ac.build_assurance_record(
            DELOITTE_TEXT,
            provider="Deloitte & Touche LLP",
            source_url=self.URL,
            stated_period_text="fiscal year ended June 30, 2024",
        )
        self.assertEqual(report["status"], ac.STATUS_UNVERIFIED)
        metadata = self._metadata(
            assurance=report,
            publisher="Deloitte & Touche LLP",
        )
        status, reason = compare_measurement_compatibility(
            self.CLAIM,
            self.CLAIM,
            metadata,
        )
        self.assertEqual(status, "INCONCLUSIVE")
        self.assertIn("unverified", reason.lower())

    def test_legacy_ambiguous_neutral_record_cannot_reach_risk_or_ui(self):
        import app
        from feature_builder import build_features_from_results
        from risk_predictor import predict_risk_from_features

        claim = (
            "Acme retained the environmental attributes of its projects, "
            "benefiting local communities."
        )
        evidence = (
            "Review of Acme information systems for collection, aggregation, "
            "analysis and internal verification of environmental data."
        )
        metadata = self._metadata(
            assurance={
                "status": "ambiguous",
                "provider": "Apex Companies, LLC",
                "source_url": self.URL,
                "assurance_type": "unknown",
                "assurance_level": "unknown",
                "scopes_covered": [],
                "scopes_excluded": ["Scope 1", "Scope 2", "Scope 3"],
                "metrics_covered": ["emissions", "carbon"],
                "reporting_period": "2025",
                "missing_fields": [],
            },
        )
        match = {
            **metadata,
            "matched_evidence": evidence,
            "similarity": 0.5541,
            "match_label": "potentially_relevant",
            "comparability_status": "NOT_QUANTITATIVE",
            "quality_status": "USABLE",
        }
        duplicate = {
            **match,
            "source_url": "https://syndicated.example/report",
            "is_duplicate_of": self.URL,
        }
        matching = [{"claim": claim, "matches": [duplicate, match]}]
        nli = [{
            "claim": claim,
            "evidence": evidence,
            "source_url": self.URL,
            "nli_result": "NEUTRAL",
            "scoring_eligible": True,
        }]

        features = build_features_from_results(matching, nli)
        prediction = predict_risk_from_features(features).iloc[0]
        self.assertEqual(features.iloc[0]["evidence_available"], 0)
        self.assertEqual(prediction["risk_score_status"], "NOT_PREDICTED")
        self.assertEqual(prediction["demonstration_risk_category"], "NOT_PREDICTED")
        self.assertTrue(pd.isna(prediction["risk_score"]))

        analysis = {
            "company": "Acme",
            "company_claims": [{"statement": claim}],
            "matching_results": matching,
            "nli_results": nli,
            "features": [{
                "claim_id": 1,
                "claim": claim,
                "risk_score": 49.082,
                "demonstration_risk_category": "MEDIUM",
            }],
            "risk_explanations": [{
                "claim_id": 1,
                "claim": claim,
                "risk_score": 49.082,
                "demonstration_risk_category": "MEDIUM",
            }],
        }
        current = app.current_analysis_risk_predictions(analysis)
        self.assertIsNotNone(current)
        self.assertEqual(current.iloc[0]["demonstration_risk_category"], "NOT_PREDICTED")
        rows, _, _ = app.dashboard_claim_rows(analysis)
        self.assertEqual(rows[0]["risk_category"], "NOT_PREDICTED")
        self.assertEqual(rows[0]["nli"], "UNREVIEWED")
        self.assertEqual(rows[0]["evidence_status"], "candidates_found_but_inconclusive")
        self.assertEqual(rows[0]["source_url"], self.URL)

    def test_inconclusive_assurance_is_not_counted_as_independent_support(self):
        claim = (
            "Acme reported Scope 2 emissions decreased by 10% in fiscal year 2024."
        )
        evidence = (
            "Acme reports that Scope 2 emissions decreased by 10% in fiscal "
            "year 2024 in its sustainability report."
        )
        metadata = self._metadata(
            assurance={
                "status": "ambiguous",
                "provider": "Apex Companies, LLC",
                "source_url": self.URL,
                "assurance_type": "unknown",
                "assurance_level": "unknown",
                "scopes_covered": [],
                "scopes_excluded": [],
                "metrics_covered": ["emissions"],
                "reporting_period": "2024",
                "missing_fields": [],
            },
        )
        result = matcher.match_online_evidence(
            [claim],
            [{
                **metadata,
                "statement": evidence,
            }],
            FakeModel(),
            cos_sim=_fixed_cos_sim(0.83),
        )[0]
        self.assertEqual(result["matches"][0]["comparability_status"], "INCONCLUSIVE")
        self.assertEqual(result["independent_support_count"], 0)
        self.assertEqual(result["evidence_status"], "candidates_found_but_inconclusive")

    def test_non_assurance_qualitative_evidence_remains_a_candidate(self):
        claim = "Acme reports that its restoration projects benefit local communities."
        evidence = (
            "Acme's restoration projects provide environmental benefits to "
            "local communities."
        )
        matching = matcher.match_online_evidence(
            [claim],
            [{
                "statement": evidence,
                "source_url": "https://research.example/acme-restoration",
                "publisher": "Independent Research",
                "source_role": "external_source",
            }],
            FakeModel(),
            cos_sim=_fixed_cos_sim(0.83),
        )
        self.assertEqual(
            matching[0]["matches"][0]["comparability_status"],
            "NOT_QUANTITATIVE",
        )
        self.assertEqual(
            matching[0]["matches"][0]["match_label"],
            "potentially_relevant",
        )


if __name__ == "__main__":
    unittest.main()
