# What still requires people, real data, or ground truth

Status as of 2026-10-27. Nothing below has been completed. None of it was fabricated.

## Requires real human reviewers
1. **Two independent reviewers** must label real claim–evidence pairs. Templates in `evaluation/` are header-only. No labels exist.
2. **One adjudicator** who is neither reviewer must resolve disagreements. Nobody has been identified.
3. Reviewers need the annotation guide in `WINDOWS_HUMAN_REVIEW_RUNBOOK.md` and `evaluation/REVIEWER_GUIDE.md`. A dedicated `HUMAN_REVIEW_PROTOCOL.md` has not yet been written.

## Requires the user's machine and real data
4. The saved analyses and `data\greenwashing_risk.db`. These are gitignored and were not in the ZIP. Real-company pipeline tracing is impossible without them.
5. Live collection (`ddgs` search, HTTP fetches) and NLI model download. Both need internet access on Windows.
6. Windows execution of the blocked test modules (see WINDOWS_VALIDATION_COMMANDS.md, section C).
7. Confirmation that Streamlit starts and serves the app (section E).

## Requires independent ground truth (does not exist in the project)
8. **Company-level greenwashing labels.** The project documents this as NOT AVAILABLE (RESEARCH_QUALITY_AUDIT.md:62). Pair-level labels cannot establish it. Any company-level accuracy claim is blocked until a defensible, independently sourced dataset is identified and its provenance checked.
9. **Risk calibration.** Requires real probabilities. The current heuristic produces a 0–100 score, not a calibrated probability, so calibration is not evaluable.

## Decisions for the user
10. Whether the saved analyses may leave your machine. Default: no.
11. Choice of companies: source availability, industry spread, and claim diversity. Ten companies is not automatically a sufficient sample.
12. Whether to commit the working-copy fixes to Git, once the project is under version control. The ZIP has no `.git` folder.
