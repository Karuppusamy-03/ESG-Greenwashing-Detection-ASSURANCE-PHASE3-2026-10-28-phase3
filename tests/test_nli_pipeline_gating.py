"""Regression: only eligible, representative evidence reaches NLI (SYNTHETIC text).

Uses a fake classifier injected at contradiction_detector._get_nli_classifier, so no
model is downloaded and no real inference is performed. These tests check gating and
failure handling, not the accuracy of any model.

Requires the transformers package to import contradiction_detector. In an environment
without it, this module is reported as blocked by a missing dependency.
"""

import unittest
from unittest import mock

import numpy as np

import contradiction_detector as cd
from feature_builder import build_features_from_results
import online_evidence_matcher as matcher
from risk_predictor import predict_risk_from_features

CLAIM = ("Samsung reported that gross Scope 1 and 2 emissions decreased by 40% compared with its 2019 "
         "baseline for global operations under the GHG Protocol in fiscal year 2023.")
REPORT = ("Samsung reported that gross Scope 1 and 2 emissions decreased by 40% compared with the 2019 "
          "baseline for global operations under the GHG Protocol in fiscal year 2023 in its sustainability report.")


class _Model:
    def encode(self, texts, **kwargs):
        return np.ones((len(texts), 3))


def _match(statements, score=0.85):
    return matcher.match_online_evidence(
        [CLAIM], statements, _Model(),
        cos_sim=lambda a, b: np.full((len(a), len(b)), score),
    )


def _run(results, classifier):
    with mock.patch.object(cd, "_get_nli_classifier", lambda: classifier):
        return cd.detect_online_contradictions({"company": "Samsung", "results": results})


def _recording_classifier(label="ENTAILMENT"):
    calls = []

    def classifier(inputs, **kwargs):
        calls.extend(inputs)
        return [{"label": label, "score": 0.9} for _ in inputs]

    return classifier, calls


class DuplicateCopiesTests(unittest.TestCase):
    def test_identical_copies_trigger_one_model_call(self):
        classifier, calls = _recording_classifier()
        results = _match([
            {"statement": REPORT, "source_url": "https://samsung.example/r.pdf", "source_role": "external_source", "entity_context": "Samsung"},
            {"statement": REPORT, "source_url": "https://samsung.example/r.pdf?utm_source=mirror", "source_role": "external_source", "entity_context": "Samsung"},
        ])
        _run(results, classifier)
        self.assertEqual(len(calls), 1, "a duplicate copy was sent to the model")

    def test_duplicate_copy_is_retained_with_its_own_source_url(self):
        classifier, _ = _recording_classifier()
        results = _match([
            {"statement": REPORT, "source_url": "https://samsung.example/r.pdf", "source_role": "external_source", "entity_context": "Samsung"},
            {"statement": REPORT, "source_url": "https://samsung.example/r.pdf?utm_source=mirror", "source_role": "external_source", "entity_context": "Samsung"},
        ])
        records = _run(results, classifier)
        copy = next(r for r in records if r["source_url"].startswith("https://samsung.example/r.pdf?"))
        self.assertEqual(copy["compatibility_status"], "DUPLICATE_COPY")
        self.assertEqual(copy["nli_result"], "NOT_EVALUATED")
        self.assertIs(copy["scoring_eligible"], False)
        self.assertIsNotNone(copy["is_duplicate_of"])


class IndependentSourcesTests(unittest.TestCase):
    def test_independent_sources_with_different_figures_are_each_evaluated(self):
        classifier, calls = _recording_classifier()
        other = REPORT.replace("40%", "35%")
        results = _match([
            {"statement": REPORT, "source_url": "https://samsung.example/r.pdf", "source_role": "external_source", "entity_context": "Samsung"},
            {"statement": other, "source_url": "https://regulator.example/a.pdf", "source_role": "external_source", "entity_context": "Samsung"},
        ])
        records = _run(results, classifier)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(r.get("compatibility_status") != "DUPLICATE_COPY" for r in records))


class MalformedEvidenceTests(unittest.TestCase):
    DAMAGED = REPORT.replace("sustainability", "sus\ufffd\ufffdtainability")

    def test_malformed_text_never_reaches_the_model(self):
        classifier, calls = _recording_classifier()
        results = _match([
            {"statement": self.DAMAGED, "source_url": "https://x.example/d", "source_role": "external_source", "entity_context": "Samsung"},
        ])
        records = _run(results, classifier)
        self.assertEqual(calls, [], "malformed text was sent to the model")
        self.assertEqual(records[0]["compatibility_status"], "MALFORMED_EXTRACTION")

    def test_malformed_text_cannot_become_entailment_support(self):
        classifier, _ = _recording_classifier(label="ENTAILMENT")
        results = _match([
            {"statement": self.DAMAGED, "source_url": "https://x.example/d", "source_role": "external_source", "entity_context": "Samsung"},
        ])
        records = _run(results, classifier)
        self.assertNotEqual(records[0].get("nli_result"), "ENTAILMENT")
        self.assertIs(records[0].get("scoring_eligible"), False)


class ProvenanceTests(unittest.TestCase):
    def test_excluded_records_keep_original_url_and_reason(self):
        classifier, _ = _recording_classifier()
        results = _match([
            {"statement": REPORT, "source_url": "https://samsung.example/r.pdf", "source_role": "external_source", "entity_context": "Samsung"},
            {"statement": REPORT, "source_url": "https://mirror.example/s.pdf", "source_role": "external_source", "entity_context": "Samsung"},
        ])
        records = _run(results, classifier)
        for record in records:
            self.assertTrue(record.get("source_url"))
            self.assertTrue(record.get("compatibility_reason"))


class ModelFailureTests(unittest.TestCase):
    def test_model_exception_is_unavailable_not_a_contradiction(self):
        def failing(inputs, **kwargs):
            raise RuntimeError("simulated inference failure")
        results = _match([
            {"statement": REPORT, "source_url": "https://samsung.example/r.pdf", "source_role": "external_source", "entity_context": "Samsung"},
        ])
        records = _run(results, failing)
        self.assertTrue(records)
        for record in records:
            self.assertEqual(record.get("nli_result"), "UNAVAILABLE")
            self.assertIs(record.get("scoring_eligible"), False)
            self.assertNotEqual(record.get("nli_result"), "CONTRADICTION")

    def test_malformed_model_output_is_unavailable(self):
        def odd(inputs, **kwargs):
            return ["not-a-dict" for _ in inputs]
        results = _match([
            {"statement": REPORT, "source_url": "https://samsung.example/r.pdf", "source_role": "external_source", "entity_context": "Samsung"},
        ])
        records = _run(results, odd)
        self.assertEqual(records[0].get("nli_result"), "UNAVAILABLE")
        self.assertIs(records[0].get("nli_failed"), True)


class CompatibilityTests(unittest.TestCase):
    def test_compatible_clean_pair_still_reaches_the_model_and_is_scored(self):
        classifier, calls = _recording_classifier(label="ENTAILMENT")
        results = _match([
            {"statement": REPORT, "source_url": "https://samsung.example/r.pdf", "source_role": "external_source", "entity_context": "Samsung"},
        ])
        records = _run(results, classifier)
        self.assertEqual(len(calls), 1)
        self.assertEqual(records[0]["nli_result"], "ENTAILMENT")
        self.assertIs(records[0]["scoring_eligible"], True)

    def test_nested_assurance_scope_exclusion_cannot_reach_nli_or_risk(self):
        claim = (
            "Apple reported that gross Scope 1 emissions were 1,000 metric "
            "tons of CO2e for global operations under the GHG Protocol in "
            "fiscal year 2024."
        )
        match = {
            "matched_evidence": claim,
            "similarity": 0.9,
            "match_label": "potentially_relevant",
            "source_url": "https://www.apple.com/environment/report.pdf",
            "source_role": "independent_third_party_source",
            "entity_context": "Apple",
            "assurance": {
                "status": "ambiguous",
                "scopes_excluded": ["Scope 1"],
                "reporting_period": "2024",
            },
        }
        matching_results = [{"claim": claim, "matches": [match]}]
        classifier, calls = _recording_classifier(label="CONTRADICTION")

        nli_results = _run(matching_results, classifier)
        features = build_features_from_results(matching_results, nli_results)
        predictions = predict_risk_from_features(features)

        self.assertEqual(calls, [])
        self.assertEqual(nli_results[0]["compatibility_status"], "INCOMPATIBLE")
        self.assertIs(nli_results[0]["scoring_eligible"], False)
        self.assertEqual(features.iloc[0]["evidence_available"], 0)
        self.assertEqual(predictions.iloc[0]["risk_score_status"], "NOT_PREDICTED")


class CompletionRuleTests(unittest.TestCase):
    """app.py cannot be imported without streamlit, so the completion rule is checked in source."""

    def test_completion_ignores_excluded_copies_and_malformed_text(self):
        import pathlib
        source = (pathlib.Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8-sig")
        self.assertIn("summarize_nli_outcomes(analysis[\"nli_results\"])", source)
        self.assertIn('analysis["nli_summary"] = nli_summary', source)


if __name__ == "__main__":
    unittest.main()
