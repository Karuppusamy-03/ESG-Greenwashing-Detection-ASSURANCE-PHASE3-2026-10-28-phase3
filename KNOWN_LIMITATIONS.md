# Known limitations

## Evaluation and validity

- **No empirical validation.** No human-reviewed labels exist in this project. No accuracy, precision, recall, F1, or agreement has been measured.
- **Heuristic score.** The weights and cutoffs in `risk_predictor.py` (class cutoff 50; categories LOW below 35, MEDIUM 35–70, HIGH from 70) are not justified by data.
- **Six-row model.** `risk_model.py` trains on six hand-written rows for demonstration. Its output is not used for scoring and must not be presented as validated.
- **Scores are not calibrated.** Neither the heuristic score nor NLI confidence is a probability.
- **Synthetic fixtures are software tests only.** They are not evidence about real companies.

## Pipeline

- **Partial NLI coverage is not scored (D2, fixed by policy).** A claim is assessed only when every eligible matched pair has a completed NLI result. This is conservative: claims with some unassessed evidence are left unscored, so the output has more `NOT_PREDICTED` rows than before.
- **Assurance evidence requires explicit eligibility.** Assurance records must be unambiguous and verified, explicitly attributed to the record's issuer and URL, and match the claim's covered scope, metric, reporting period, and any stated baseline. Explicit exclusions are applied before NLI and feature building. Missing information leaves the pair inconclusive; it is retained for review, not used as support or contradiction. Ordinary evidence without assurance metadata follows the existing comparability rules.
- **Legacy analyses are not rewritten.** The app rebuilds risk features from saved matching and NLI records using current eligibility rules when it can. It does this in memory and shows a notice when the displayed risk category differs; it also displays a non-duplicate representative and marks candidates inconclusive when assurance eligibility is not established. It never overwrites the saved analysis or database. Direct inspection of an older JSON file may still show its original pre-gate feature, score, or explanation.
- **Similarity is textual only.** High similarity does not show that evidence supports a claim. The score uses the maximum similarity over eligible matches.
- **NLI model load failure stops the stage.** If `cross-encoder/nli-deberta-v3-small` cannot be loaded, `contradiction_detector` raises a `RuntimeError`. Pairs are marked `UNAVAILABLE` only when the model runs and returns an unusable output for that pair.
- **Company disambiguation is lexical.** `Delta Electronics` is accepted as Delta. Subsidiary relationships are not checked against any corporate registry.
- **Source independence is attribution-based.** A different domain does not prove independence.
- **Measurement compatibility is conservative.** Missing period, scope, unit, or boundary data makes a pair inconclusive. Valid evidence can be excluded this way.

## Engineering verification (2026-10-28)

- Assurance eligibility is checked before a candidate can influence NLI, features, or heuristic risk. A third-party provider name by itself does not establish source attribution or independence.
- The saved Apple analysis in this workspace contains 1,561 claim candidates, 1,325 with candidate matches, and 236 without matches. Its original saved feature/explanation reports one MEDIUM score (49.082) from a neutral NLI row attached to an ambiguous assurance record with no covered scopes. Rebuilding features from the saved evidence with the current gate yields no eligible evidence for that claim and `NOT_PREDICTED`; the on-disk analysis is preserved.
- Recalculating the full saved Apple analysis with current rules yields 1,561 `NOT_PREDICTED` rows and zero displayed scored rows. Candidate evidence statuses are now distinguished as weak-only, unmatched, incompatible, inconclusive, or low quality; these are candidate classifications, not evidence that the underlying corporate claim is true or false.
- The complete software suite passed (484 passed, 1 skipped, 69 subtests); Python compilation succeeded. Streamlit started and its health endpoint returned HTTP 200 on port 8766. The saved analysis, database, and both collected-document JSON files matched their pre-check SHA-256 hashes afterward.
- No empirical accuracy or calibration is established by these checks. All software tests are not a substitute for human-reviewed labels, real model validation, or broad source coverage.

## Live operation

- A live search-backend check on 2026-10-28 returned five results for an Apple independent-measurement query: two Apple-hosted company reports and three unverified pages. It returned no independently published measurement that could be accepted as evidence.
- The live search result pages were not downloaded or extracted during that check, and no real NLI inference or broad collection run was performed. Collection error paths and provenance are covered by mocked/offline tests.
- The README recommends a live check on two unseen companies, run on the user's machine.

## Environment

- The unit suite needs `transformers` and `sentence-transformers` installed (six test modules import them).
- Two data-dependent tests need the local `data/` and `output/` folders. They fail with "Missing saved fixture" without them.
- The workspace contains two existing Apple collected-document JSON files. Their hashes were verified unchanged after the test run; preserve existing local documents and databases when running the project.

## Real-data status

- This Windows workspace contains a saved Apple analysis, a SQLite database, and two collected-document JSON files. These are preserved and are not human-reviewed labels.
- No human-reviewed evaluation labels or empirical accuracy, calibration, or agreement results are available.
- The saved Apple analysis predates the current assurance gate. Its original stored MEDIUM score is retained on disk; the app recomputes display risk from its stored matching/NLI records under current eligibility rules without rewriting the analysis.
- Software tests, including synthetic fixtures, do not establish real-world model performance or broad evidence coverage.

## Human-review workflow (2026-10-27)

- The pair-review workflow has been tested only on synthetic fixtures (`tests/test_pair_review.py`). Its labels and metrics from those fixtures are software tests, not research results.
- Pair labels are evidence-level judgements. They do not establish company-level greenwashing, and one CONTRADICTING pair is not proof of greenwashing.
- Reviewer independence is enforced only by the workflow: distinct identifiers, separate packets, no model columns in packets. It cannot verify that two people did not discuss the pairs.
- Reviewers may open linked sources; the workflow cannot check what they read.
- Reviewer labels are not validated against any external ground truth.
