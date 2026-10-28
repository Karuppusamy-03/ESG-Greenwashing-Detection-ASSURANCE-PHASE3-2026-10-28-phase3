# Source integrity, extraction quality and assurance scope — report (2026-10-27)

## 0. Scope and honesty
- Environment: Linux sandbox, **no network, no Windows, no Streamlit, real NLP/PDF/web packages not installed**.
- **No live source was retrieved.** Live collection, search-query quality, alias resolution in the collector, and HTML/PDF retrieval were **not tested** in this environment.
- All results below use **synthetic inputs** and test software logic. They are not evidence about any real company.
- **No labelled dataset exists.** Precision and recall are **not measured**.
- Base: the GENERAL-2026-10-27 package (latest; contains all earlier fixes). The uploaded snapshot was not used.

## 1. Diagnosis (existing code before changes)
- **Duplicate detection** (`online_evidence_matcher._dedupe_evidence_items`) only removed exact matches of URL and text. Same report at a different URL, a mirror, a tracking-parameter variant, or a near-identical copy was counted as separate support.
- **Extraction quality** had no explicit status. Concatenated headings, table dot-leaders and encoding damage could reach matching and become support if the wording was similar.
- **Assurance** handling read metadata flags supplied by the caller. Nothing classified the assurance type, the stated scope, or whether a reviewer was named without any assurance being stated.

## 2. Changes
| File | Status | Purpose |
|---|---|---|
| `source_dedupe.py` | new | URL normalisation (scheme, www, tracking parameters, fragment, trailing slash); SHA-256 content fingerprint; conservative near-duplicate test (≥0.90 shingle overlap **and** identical numbers **and** identical years); grouping annotations with method and confidence. Does not delete candidates. |
| `extraction_quality.py` | new | Status USABLE / INCOMPLETE / MALFORMED with reasons (encoding damage, concatenated headings, dot-leader fragments, page furniture, truncation, number-only fragments). Never modifies text. Hyphenation breaks are kept as usable with a note. |
| `assurance_classifier.py` | new (standalone) | Classifies only stated text: limited/reasonable assurance, agreed-upon procedures, limited review, reviewer named without a stated type (`review_unspecified`), ambiguous types, scopes covered and excluded, fiscal period. Returns UNKNOWN when not stated. `assurance_supports_scope` requires every claimed scope to be covered and none excluded. **Not yet wired into the comparability gate** (see §6). |
| `online_evidence_matcher.py` | changed | Groups the evidence pool once (on copies). Runs the quality check **before** the comparability gate; MALFORMED text is labelled `low_quality_extraction`, never supporting. Each match records quality, fingerprint, canonical URL and duplicate group. Status counts **independent support** (representative groups only). New status `candidates_found_low_quality_extraction`. Result includes `independent_support_count`. |
| `feature_builder.py` | changed | Duplicate copies and MALFORMED matches are excluded from feature construction, in addition to the existing exclusions. |
| `tests/test_source_integrity.py` | new | 29 synthetic regression tests (URL, near duplicates, grouping, quality, assurance, matcher integration, feature exclusion). |

## 3. Before and after (matcher outcomes, fixed synthetic scenarios, similarity fixed at 0.8)
| Scenario | Before: status / matches shown | After: status / matches shown / independent support |
|---|---|---|
| Copies of one report at two URLs | potentially_relevant / 2 | potentially_relevant / 2 / **1** |
| Malformed fragment only | potentially_relevant / 1 | **candidates_found_low_quality_extraction** / 1 / **0** |
| Two distinct sources | potentially_relevant / 2 | potentially_relevant / 2 / 2 |
| One clean source | potentially_relevant / 1 | potentially_relevant / 1 / 1 |

Duplicate counts (measured on the synthetic corpus only): 2 candidates, 1 group, 1 duplicate detected (method `exact_content_hash`).

## 4. Test results (sandbox)
| Run | Ran | Passed | Failures | Errors (missing package) | Skipped | Exit |
|---|---|---|---|---|---|---|
| E, no optional packages | 255 | 222 | 0 | 32 | 1 | 1 |
| F, with sandbox stubs | 290 | 275 | 0 | 14 | 1 | 1 |
No new errors compared with the previous run. Compile check: exit 0.
The 29 new tests error at import on the base package, because the new modules are absent there. That shows the modules are new, not that the behaviour gap was reproduced at logic level. The behaviour difference is shown in §3.

## 5. Remaining failure modes (not verified on real documents)
- Multi-column PDF layout, headers far from their table, and tables where units sit in a separate row: the quality check only sees the extracted string and cannot reconstruct column relationships.
- OCR or scanned pages: no OCR was tested; a scanned document with no text layer produces no statements at all.
- Duplicates across **revised** versions of the same report, or reports that are translated: the content hash and the near-duplicate test will not group these, and they should not be merged. Their relationship is not recorded.
- Near-duplicate detection is conservative by design: a one-word change in a short sentence is not grouped. Copies whose text was edited will therefore be counted separately.
- Mirrors that re-wrap text (different line breaks, hyphenation) may not hash identically; the normalisation only collapses whitespace and case.
- Only up to 3 matches per claim are kept, so duplicates can crowd out distinct sources before grouping is applied.

## 6. Not done in this round
- **Assurance is not wired into the gate.** `assurance_classifier` is standalone. The gate still reads caller-supplied metadata (`assurance_report`, `scope_exclusions`). Wiring requires deciding how a classified assurance feeds the existing scope check, and tests against real assurance statements.
- **Workstream A (live evidence collection, aliases, query generation, PDF/HTML retrieval, robots and rate limits):** not changed and not tested here. No company was analysed live.
- **Workstream D (reviewer independence beyond scope):** publisher, author, reviewer and supplier distinctions are not modelled in the data model.
- **Workstream G (Windows and Streamlit):** not run. Commands are below.
- **Risk-status consistency across database and saved analyses:** the display rule was unified earlier; end-to-end persistence was not verified. No database or saved analysis was in the sandbox, and none was touched.
- **Backward compatibility with historical analyses:** not verified against real data.
- **Precision, recall and error categories on a reviewed dataset:** not produced. No reviewed set exists.
- **Cross-company suite:** the earlier suite was not extended in this round.

## 7. Preservation
Upload and the GENERAL package were not modified. Work was done on a separate copy. No database, saved analysis, collected document, or `data/` or `output/` folder was created or touched. No thresholds changed (0.55 strong, 0.35 weak, 0.90 near duplicate is new and conservative).
