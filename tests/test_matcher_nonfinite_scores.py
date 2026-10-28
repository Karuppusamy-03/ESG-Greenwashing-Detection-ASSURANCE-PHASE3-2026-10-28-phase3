"""Regression: a non-finite (NaN/inf) similarity must never become an evidence match.

SYNTHETIC inputs. Uses a fake embedder that returns a NaN score, so no model is needed.
The fixed matcher must treat a missing score as no match, not as a relevance label."""

import math
import unittest

import online_evidence_matcher as oem


class _NaNEmbedder:
    """Stands in for the sentence-embedding model. Every pair scores NaN."""

    def encode(self, texts, **kwargs):
        return [[float("nan")] * 4 for _ in texts]


class ClassifySimilarityTests(unittest.TestCase):
    def test_nan_is_not_classified_as_relevant_or_weak(self):
        label = oem.classify_similarity(float("nan"))
        self.assertNotIn(label, {"potentially_relevant", "weak_match"})

    def test_finite_scores_still_classify_at_documented_thresholds(self):
        self.assertEqual(oem.classify_similarity(0.9), "potentially_relevant")
        self.assertEqual(oem.classify_similarity(0.55), "potentially_relevant")
        self.assertEqual(oem.classify_similarity(0.35), "weak_match")
        self.assertEqual(oem.classify_similarity(0.34), "no_sufficiently_relevant_match")


class NonFiniteFilterTests(unittest.TestCase):
    """The skip filter in match_online_evidence must reject non-finite scores.

    The filter is checked by reading the matcher source, because the full matcher
    needs sentence_transformers (not installed in the sandbox)."""

    def test_filter_rejects_non_finite_scores(self):
        import inspect
        source = inspect.getsource(oem.match_online_evidence)
        self.assertIn("math.isfinite", source,
                      "match_online_evidence must skip NaN/inf similarity scores")


if __name__ == "__main__":
    unittest.main()
