# Baseline report — integrity package verification (2026-10-28)

## Phase 1 — package identity
- File: `ESG-Greenwashing-Detection-System-INTEGRITY-2026-10-27.zip`, found in `/mnt/user-data/outputs/`.
- SHA-256 matches the reported value `e261cbe249e889861d60af578dc5a00f112ec181e0b505c9a2c156719fb7597d`.
- Extracted to a separate working copy. The original archive was not modified.
- Compared with the GENERAL package it was built from:
  - Added: `assurance_classifier.py`, `extraction_quality.py`, `source_dedupe.py`, `tests/test_source_integrity.py`, the integrity report and two run logs.
  - Changed: `feature_builder.py`, `online_evidence_matcher.py`, `validation/CHANGE_LOG_2026-10-27.md`.
  - Removed: none.
  - Dangerous-looking entries: only a standard `.gitignore`. No secrets, databases, `data/`, `output/`, `.venv` or `.git`.
- The package is not an Apple-only patch and does not roll back earlier fixes.

## Phase 1 — baseline tests (sandbox: Linux, no network, no Streamlit, real NLP/PDF/web packages absent)
| Run | Ran | Passed | Failures | Errors (missing package) | Skipped |
|---|---|---|---|---|---|
| No optional packages | 255 | 222 | 0 | 32 | 1 |
| With sandbox stubs (ddgs, pymupdf, plotly) | 290 | 275 | 0 | 14 | 1 |

The new `test_source_integrity` module uses no mocks. It injects the similarity function (`cos_sim`) as a seam, so the real embedding model is not exercised. Stubs are sandbox-only and not in the package.

## Phase 2 — verification of the reported integrity changes
| Claim in the integrity report | Verified? | Finding |
|---|---|---|
| Deduplication groups copies and keeps URLs | Yes, in unit tests | Works on synthetic copies. Not tested on real documents. |
| Extraction quality runs before the comparability gate in the matcher | Yes | Malformed text becomes `low_quality_extraction`. |
| Copies count once toward independent support | Yes | `independent_support_count` = 1 for two copies. |
| Feature builder excludes duplicates and malformed text | Yes | Covered by a test. |
| Assurance classifier integrated into the pipeline | **No** | No production caller. Only tests import it. The report says "standalone" and this is accurate, but it is not integrated. |
| Dashboard counts reflect independent evidence | **No (defect, fixed)** | `app.py` summed every match, including copies, into the "Evidence" metric and the matched-pairs count. |
| NLI runs only on non-duplicate pairs | **No (open)** | `contradiction_detector.py` still receives copies, so NLI runs twice on the same text. Feature scoring excludes them, but NLI cost and counts are duplicated. Not changed (see below). |

## Changes made in Phase 2
- `app.py`: both match counts (dashboard "Evidence" metric and `matched_pairs`) now count only representative matches (`is_duplicate_of` is None). Matches are still displayed; only the counts change. Backup: `app_before_count_fix.py`.
- `tests/test_dashboard_counts.py` (new, 2 structural tests). Both fail on the unfixed `app.py` and pass on the fixed one.

Post-change runs: 257 run / 0 failures / 32 errors / 1 skip (no stubs); 292 run / 0 failures / 14 errors / 1 skip (with stubs). No new errors.

## Deliberately not done in this round (needs the Windows environment or a separate phase)
- **Phase 3 (assurance integration):** not started. Wiring the classifier into the gate changes comparability decisions and needs real assurance statements to test against. Doing it without those risks unsupported exclusions.
- **NLI on duplicates:** not changed. Skipping copies in `contradiction_detector` changes NLI completion counts that `app.py` uses for stage status, and that path can only be exercised in the full app.
- **Phases 4–7 (live collection, pipeline trace, database and timeline integrity, accuracy evaluation, Windows and Streamlit runs):** not performed. Live network access, the real packages and Streamlit are unavailable here. No live company analysis was run. No database or saved analysis was present or touched.
- **`PIPELINE_TRACE.md`, `EVIDENCE_GAPS.md`, `ACCURACY_EVALUATION.md`:** not written. There is no reviewed labelled dataset, so accuracy remains unvalidated.
