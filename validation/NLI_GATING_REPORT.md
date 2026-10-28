# NLI gating: duplicate and malformed evidence (2026-10-28)

## 1. Code path (before the fix)
1. `online_evidence_matcher.match_online_evidence` builds per-claim matches. It annotates each match with `is_duplicate_of`, `quality_status` and `comparability_status`, and labels malformed text `low_quality_extraction`.
2. `app.py` (about line 1511) passes **all** matching results, copies and malformed text included, to `contradiction_detector.detect_online_contradictions`.
3. The detector built a pair per match and applied only similarity, entity and comparability gates. It **recomputed** comparability from the raw text and ignored the matcher's annotations. Every surviving pair went into one batched model call.

Probes (sandbox, fake classifier):
- Two identical copies of one report produced **two model calls** on the same text.
- A malformed statement, with otherwise comparable wording, reached the model and returned `ENTAILMENT` with `scoring_eligible: True`. **This was a defect**: damaged text could count as support.

## 2. Change (minimal, reuses existing logic)
- `contradiction_detector.py`: pairs now carry `is_duplicate_of`, `duplicate_group_id`, `duplicate_method` and `quality_status`. Before the similarity gates, a pair that is a duplicate copy is recorded as `nli_result = NOT_EVALUATED`, `compatibility_status = DUPLICATE_COPY`. Malformed text is recorded as `NOT_EVALUATED` / `MALFORMED_EXTRACTION`. Both are `scoring_eligible: False`, keep their source URL and reason, and are **never sent to the model**. Quality is checked with the existing `extraction_quality.assess_statement_quality`; no second deduplication system was added. Deduplication remains `source_dedupe.group_candidates` via the matcher.
- `app.py`: NLI completion is computed over **evaluable** records, excluding `DUPLICATE_COPY` and `MALFORMED_EXTRACTION`. This is a deliberate change of meaning, explained in §4.
- Source-deduplication rules were **not** changed. Cross-domain near-copies with identical figures and years are still grouped as one syndicated source (the earlier workstream asked for this). Texts that differ in figures or years are never merged.
- Thresholds, matching logic, database schema and contents, saved-analysis format and the sidebar are unchanged.

## 3. Tests
- New `tests/test_nli_pipeline_gating.py` (10 tests): duplicates trigger one model call; the copy keeps its URL and `is_duplicate_of`; independent sources with different figures are each evaluated; malformed text never reaches the model and cannot become `ENTAILMENT`; excluded records keep URL and reason; model exception and malformed model output are `UNAVAILABLE` with `scoring_eligible: False`, never `CONTRADICTION`; a compatible clean pair is still scored; completion rule present in `app.py`.
- Against the pre-fix code, **5 of these fail** (duplicate calls, malformed leakage, completion). The other 5 pass on both versions and pin behaviour that was already correct.
- Correction to an earlier test (disclosed): `test_offline_workflows.test_risk_prediction_and_explanation_match_the_heuristic` had contradictory assertions. The unassessed row was asserted to have no explanation (`[]`), and the next assertions read `explanations[0]`. The module had never run, because it needs `transformers`. The explanation checks now run on a scored row, where they belong. Behaviour of the explainer was not changed.

## 4. Effects on counts, completion and displays
- **Pipeline completion:** before, any pair that was not evaluated made `nli_completed` false. Now duplicate copies and malformed text are excluded from the completion denominator; similarity, entity and comparability skips still count as before. This is a deliberate change and should be reviewed.
- **`nli_result_count` diagnostic:** still counts every record, including excluded copies. Its meaning is unchanged, but it now includes copies that were never evaluated.
- **Saved analyses:** the list gains records with the new values `NOT_EVALUATED`, `DUPLICATE_COPY`, `MALFORMED_EXTRACTION`. Existing readers treat unknown `nli_result` values as "not reviewed" or "unavailable". Old analyses are unchanged and not rewritten.
- **Dashboard:** excluded copies display as "NOT_EVALUATED" in per-claim views, with their source link. Dashboard counts were already fixed in Phase 2.

## 5. Test results (sandbox)
| Run | Ran | Passed | Failures | Errors (all dependency-blocked) | Skipped |
|---|---|---|---|---|---|
| E, no optional packages | 258 | 224 | 0 | 33 (ddgs 20, pymupdf 6, transformers 4, torch 1, app.py startup guard 1, plus summary line) | 1 |
| F, stubs (ddgs, pymupdf, plotly) + sandbox `transformers` stand-in | 396 | 350 | 0 | 45 (app.py startup guard 28, truststore 8, sentence_transformers 6, streamlit 1, torch 1) | 1 |

Assertion failures: 0 in both runs. `compileall`: exit 0.
The `transformers` stand-in is sandbox-only, not in the package. It replaces the model with a function that raises, so it proves nothing about inference. The fake classifier in the new tests is the only model stand-in used for behaviour.

Not verified: the real `transformers` pipeline, its output format and batch behaviour; the live application; Streamlit startup.

## 6. Remaining risks
1. **Real model output not tested.** The fake classifier returns `{"label", "score"}` dictionaries. Real pipeline output must be confirmed on Windows.
2. **Completion policy change** (§4) needs your sign-off.
3. **Cross-domain copies are excluded** from NLI as one syndicated source. If two unrelated regulators publish near-identical text with identical figures, the second is excluded. This is a policy choice; confirm it.
4. **The matcher caps matches at 3 per claim**, so copies can crowd out distinct sources before grouping.
5. **Malformed-text check runs twice** (matcher and detector) using the same function, so both agree. A future change to one must be mirrored in the other.
6. **Assurance classification is still not wired** (Phase 3, deferred).
7. **Live collection, the full app and Streamlit** have not been run.

## 7. Windows validation commands
```powershell
cd "C:\path\to\ESG-Greenwashing-Detection-System-NLI-GATING"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest tests.test_nli_pipeline_gating tests.test_offline_workflows -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -t tests -v *> validation\windows_nli_unittest.log
"unittest exit=$LASTEXITCODE"
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8599
```
Please send back the `Ran`/`OK`/`FAILED` lines, any ERROR blocks, the `pip check` output, and whether Streamlit started.
