"""Regression: the matcher keeps every candidate for review, but must not present a
comparability-rejected candidate as potentially relevant support.

Uses an injected fake similarity model. SYNTHETIC text only. No network, no model download.
"""

import unittest

import numpy as np

import online_evidence_matcher as matcher

CLAIM = (
    "Apple reports that gross greenhouse gas emissions across Scopes 1, 2, and 3 "
    "decreased by more than 60% compared with its 2015 baseline, excluding offsets."
)
SUPPLIER = (
    "Our supplier energy-efficiency program avoided 1.2 million metric tons of CO2e in 2023."
)


def _run(score):
    """Run the matcher with a fixed similarity score, injected as cos_sim."""
    def fixed_cos_sim(claim_embeddings, evidence_embeddings):
        return np.full((len(claim_embeddings), len(evidence_embeddings)), score)

    class _Model:
        def encode(self, texts, **kwargs):
            return np.ones((len(texts), 3))

    return matcher.match_online_evidence(
        [CLAIM],
        [{"statement": SUPPLIER, "source_url": "https://supplier.example/report.pdf",
          "source_title": "Synthetic supplier report", "source_role": "external_source"}],
        _Model(),
        cos_sim=fixed_cos_sim,
    )


class ProductionShapeTests(unittest.TestCase):
    """The pipeline passes claims as plain strings; this must never crash."""

    def test_string_claims_do_not_raise(self):
        result = _run(0.8)
        self.assertEqual(result[0]["claim"], CLAIM)


class IncompatibleCandidateStatusTests(unittest.TestCase):
    def test_candidate_is_kept_for_review_with_its_source_link(self):
        result = _run(0.8)[0]
        self.assertEqual(len(result["matches"]), 1)
        self.assertEqual(result["matches"][0]["source_url"], "https://supplier.example/report.pdf")

    def test_comparability_rejected_candidate_is_not_potentially_relevant_support(self):
        result = _run(0.8)[0]
        self.assertNotEqual(result["evidence_status"], "potentially_relevant_evidence_found")
        self.assertEqual(result["matches"][0]["comparability_status"], "INCOMPATIBLE")
        self.assertIn("avoided", result["matches"][0]["comparability_reason"].lower())

    def test_match_label_reflects_comparability_not_similarity_alone(self):
        match = _run(0.8)[0]["matches"][0]
        self.assertNotEqual(match["match_label"], "potentially_relevant")


if __name__ == "__main__":
    unittest.main()


class IncompatibleNeverScoresTests(unittest.TestCase):
    """A comparability-rejected candidate must not feed feature construction."""

    def test_feature_builder_excludes_incompatible_candidates(self):
        import feature_builder
        matches = _run(0.8)
        self.assertEqual(matches[0]["claim"], CLAIM)
        nli = [{
            "claim": CLAIM, "evidence": SUPPLIER,
            "source_url": "https://supplier.example/report.pdf",
            "nli_result": "CONTRADICTION", "scoring_eligible": True,
        }]
        features = feature_builder.build_features_from_results(matches, nli)
        rows = features.to_dict("records") if hasattr(features, "to_dict") else features
        counted = [row for row in rows if row.get("similarity") is not None
                   and row.get("evidence_available") == 1]
        self.assertEqual(
            counted, [],
            "an INCOMPATIBLE candidate was counted as scoring evidence",
        )


class MaterialScenarioStatusTests(unittest.TestCase):
    """Scenarios B and E: a material-content claim must not be presented as supported
    by an emissions figure. SYNTHETIC sentences with the structure of the Apple claims."""

    def _status(self, claim, evidence):
        def fixed(a, b):
            return np.full((len(a), len(b)), 0.8)
        class _M:
            def encode(self, texts, **k):
                return np.ones((len(texts), 3))
        result = matcher.match_online_evidence(
            [claim],
            [{"statement": evidence, "source_url": "https://synthetic.example/x",
              "source_role": "external_source"}],
            _M(),
            cos_sim=fixed,
        )[0]
        return result["evidence_status"], result["matches"][0]["comparability_status"]

    def test_scenario_b_rare_earth_claim_not_supported_by_carbon_figure(self):
        status, comparability = self._status(
            "99% of the rare earth elements in the magnets of our products are recycled.",
            "Total Scope 3 emissions fell 25% compared with 2015.",
        )
        self.assertNotEqual(status, "potentially_relevant_evidence_found")
        self.assertEqual(comparability, "INCOMPATIBLE")

    def test_scenario_e_recycled_materials_not_supported_by_emissions_total(self):
        status, comparability = self._status(
            "We increased the use of recycled materials across our products.",
            "Total emissions across our operations were 1.5 million metric tons in 2023.",
        )
        self.assertNotEqual(status, "potentially_relevant_evidence_found")
        self.assertEqual(comparability, "INCOMPATIBLE")
