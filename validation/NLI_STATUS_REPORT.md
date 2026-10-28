# Independent-source preservation and honest NLI status (2026-10-28)

## 1. Root causes
**Issue 1 — duplicate rule too broad.** `source_dedupe.group_candidates` treated two candidates as duplicates when their text was identical, or near-identical with the same numbers and years, even on different domains. The live pipeline never sets a source-relationship field (`original_source_url` is populated only in the unused `analyze_collected_evidence.py`), so nothing supported the merge. Two independent organisations publishing the same figures were therefore collapsed and excluded from NLI. Separate reports from one organisation with the same figures were also merged.

**Issue 2 — completion status misleading.** `app.py` labelled the NLI stage COMPLETED or PARTIAL from a single boolean. An all-excluded run was reported as "partial, one or more pairs unavailable", not as "no eligible pairs". Copies excluded from NLI were not described, and there were no outcome counts.

## 2. Code path (verified in the working copy)
`online_evidence_matcher` → annotates `is_duplicate_of`, `source_relation`, `potentially_related_to`, quality → `contradiction_detector.detect_online_contradictions` excludes `DUPLICATE_COPY` and `MALFORMED_EXTRACTION` before the similarity gates, records them with URL and reason → `app.py` builds the stage summary.

## 3. Changes
| File | Change |
|---|---|
| `source_dedupe.py` | Duplicates now require a same-document signal: same canonical URL with matching text, an exact copy on the same site, or an explicit provenance link (`original_source_url` shared, or pointing at the other candidate's URL). Identical text on another site, or near-identical text at a different URL, becomes `potentially_related`: kept, evaluated, and given its own group. Nothing is deleted. |
| `online_evidence_matcher.py` | Matches carry `source_relation` and `potentially_related_to`. The result gains `potentially_related_count`, the number of distinct documents whose independence is **not** established. |
| `contradiction_detector.py` | Pairs carry the relation fields for audit. |
| `nli_status.py` (new) | Pure function `summarize_nli_outcomes`: counts and an honest status. |
| `app.py` | NLI stage uses the summary; stores it as an additive `analysis["nli_summary"]`. The old `nli_completed` logic is removed. Sidebar and navigation unchanged. |
| Tests | New: `test_source_independence.py` (11), `test_nli_status.py` (9). Updated expectations that encoded the old merge: `test_source_integrity.py` (3 changed), `test_nli_pipeline_gating.py` (2 changed to same-URL variants; 1 source check). `test_scoring_eligibility_default.py` now reads the eligibility rule in `nli_status.py`, where it moved (see §6). |

## 4. How independent evidence is preserved
- Identical figures, years or wording do **not** merge candidates.
- Different reporting years, different figures and separate reports from one organisation are never related.
- Cross-site identical text is kept as two evaluated documents, flagged `potentially_related`, and counted in `potentially_related_count` rather than as confirmed independence.
- Source URL, canonical URL, publisher and provenance fields are preserved through grouping (tested).
- Syndication is treated as established only through an explicit provenance link. **The live pipeline does not yet populate that link**, so syndicated copies on different sites will currently appear as `potentially_related`, not `duplicate`. This is a known limit, not a verified syndication finding.

## 5. Meaning of each NLI outcome
| Outcome | Meaning | Counted in `evaluated`? | Stage effect |
|---|---|---|---|
| `evaluated` | Classified ENTAILMENT / CONTRADICTION / NEUTRAL, `scoring_eligible` true | yes | counts toward COMPLETED |
| `excluded_duplicate` | Same document as a representative; never sent to model | no | reported, not an error |
| `excluded_quality` | Malformed extraction; never sent to model | no | reported, not an error |
| `gate_skipped` | Stopped by similarity, entity or comparability gates | no | PARTIAL |
| `model_failed` | Model error, timeout or unrecognised output; UNAVAILABLE | no | FAILED if nothing else evaluated |
| `potentially_related_evaluated` | Evaluated, but source independence not established | yes, reported separately | none |

Stage status: **COMPLETED** only when every eligible pair was evaluated. **NOT AVAILABLE** when nothing was eligible (message: "No eligible evidence pairs for NLI evaluation…") or there were no pairs. **FAILED** when eligible pairs existed but the model returned nothing usable. **PARTIAL** otherwise. Exclusion counts are always stated in the message.

## 6. Decisions and changes to existing expectations (for your review)
- **Completion policy:** COMPLETED now means all *eligible* pairs were evaluated; excluded copies and malformed text are stated but do not count against it. Before, any unevaluated pair made the stage PARTIAL.
- **Syndication:** cross-site copies are no longer excluded. This may **increase** the number of NLI calls and displayed evidence where sites reproduce one document. That is the intended trade-off against wrongly merging independent sources.
- **Eligibility check moved:** the H1 rule ("missing `scoring_eligible` is not eligible") now lives in `nli_status.py`. Its meaning is unchanged: a record with no flag counts as zero evaluated (tested). The structural test was pointed at the new location; `app.py` no longer contains that expression.
- **Historical data:** existing saved analyses lack `nli_summary`; the field is additive and optional. No JSON or SQLite data was rewritten.

## 7. Test results (sandbox)
| Run | Ran | Passed | Failures | Blocked (dependency or startup) | Skipped |
|---|---|---|---|---|---|
| E, no optional packages | 280 | 246 | 0 | 33 | 1 |
| F, stubs + sandbox transformers stand-in | 418 | 372 | 0 | 45 | 1 |

- New tests: 20 pass. Two of the independence tests fail on the previous code for the right reason (independent organisations with identical figures were merged; matcher count was 1 instead of 2). The other previous-code errors are a missing `source_relation` field, not logic evidence.
- The 33 / 45 blocked are: `ddgs`, `pymupdf`, `transformers`, `torch`, `truststore`, `sentence_transformers`, `streamlit` missing, and the `app.py` startup guard refusing to run without Streamlit. None is a logic failure.
- `compileall`: exit 0.

**Not verified:** the real `transformers` model and its output; live collection; the Streamlit app and dashboard display; saved-analysis round trips on real data. The `transformers` stand-in is sandbox-only and not packaged. Tests of model behaviour use a fake classifier.

## 8. Remaining risks and open decisions
1. Approve the completion policy (§6).
2. Approve treating cross-site identical text as potentially related rather than duplicate.
3. Live pipeline does not record syndication links; `final_url` redirects overwrite the requested URL, so the originally requested address is lost. Recording both would need a collector change (not made here).
4. The company-statement merge in `app.py` (keyed on role and text) is a separate existing mechanism. It was not changed.
5. Stage counts appear in the stage message and in `analysis["nli_summary"]`; no new dashboard panel was added.

## 9. Windows validation
```powershell
cd "C:\path\to\ESG-Greenwashing-Detection-System-NLI-STATUS"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest tests.test_source_independence tests.test_nli_status tests.test_nli_pipeline_gating tests.test_source_integrity tests.test_scoring_eligibility_default -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -t tests -v *> validation\windows_nli_status_unittest.log
"unittest exit=$LASTEXITCODE"
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8599
```
Send back the `Ran` and `OK`/`FAILED` lines, any ERROR blocks, `pip check` output, and whether Streamlit started and the NLI stage message for one analysis.
