# ESG Greenwashing Detection System — Windows setup, run, and interpretation

## Status (read first)
Windows verification on 2026-10-28, using Python 3.13.5: the complete test suite passed (484 passed, 1 skipped), `compileall` succeeded, and Streamlit returned HTTP 200 on port 8766. A live search query ran, but returned no eligible independent measurement; no live source page was downloaded for evidence extraction and no real NLI inference was run. This confirms tested software behavior, not scientific accuracy or real-world evidence coverage. No human-reviewed labels or accuracy metrics are available.

## What the app does
It collects public documents about a company, extracts environmental claims, searches for candidate independent evidence, classifies claim–evidence pairs with an NLI model, builds features, produces an **experimental heuristic** score, and saves results to a local SQLite database. It is a research and demonstration tool. It is **not** a validated greenwashing detector or a compliance system.

## Requirements
- Windows 10 or 11, PowerShell 5.1 or later.
- Python 3.11, 3.12 or 3.13 from python.org (tick "Add python.exe to PATH" or use the `py` launcher).
- Internet access for web search and for the first download of the NLI model (`cross-encoder/nli-deberta-v3-small`).
- Several GB free: torch and transformers are large.

## Install (PowerShell, from the project folder)
```powershell
cd "C:\path\to\ESG-Greenwashing-Detection-System-main"
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pytest
```
If `py -3.13` is not found, use `py -3.12` or `py -3.11`. If torch is slow or fails, install the CPU build first from pytorch.org, then re-run the `requirements.txt` line. Record the result with:
```powershell
.\.venv\Scripts\python.exe -m pip freeze > validation\pip_freeze_windows.txt
```

## Run the app
```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Open the URL it prints (usually http://localhost:8501). Stop with Ctrl+C.

If a package is missing, the app now stops with a message naming the missing packages and the install command, instead of a long traceback.

## Validate the install
```powershell
# check only, no installs
powershell -ExecutionPolicy Bypass -File .\WINDOWS_VALIDATION.ps1
# install requirements first, then check
powershell -ExecutionPolicy Bypass -File .\WINDOWS_VALIDATION.ps1 -InstallDependencies
# also run the internet-dependent live tests
powershell -ExecutionPolicy Bypass -File .\WINDOWS_VALIDATION.ps1 -IncludeLiveTests
```
Results go to `validation\results_<timestamp>\`. Read `SUMMARY.txt` first. Each step is PASS only if its command exited 0. `BLOCKED-PARTIAL` means no assertion failed but some test modules could not import a missing package; check `unittest.log`. Nothing is marked PASS by assumption.

## Your data
The app writes to `data\greenwashing_risk.db` and `output\`. These local files are gitignored. If a database, saved analysis, or collected document already exists, preserve it and back up `data\` and `output\` before running new analyses. The app creates the database only if it is missing and never drops or deletes tables.

## Interpreting results
- **Score (0–100):** a transparent heuristic on similarity and NLI counts. It is experimental. It is not a probability of greenwashing and has not been validated against labelled data.
- **Unassessed / NOT_PREDICTED:** no eligible evidence matched, assurance scope or attribution was insufficient, or NLI did not complete for all eligible evidence. This is **not** evidence of greenwashing and **not** a low score.
- **Company report vs third-party assurance vs regulatory or independently published evidence:** these are different source roles. A report's hosting domain and an assurance provider's name alone do not prove source independence, claim coverage, reliability, or truth.
- **Timeline:** values with an explicit reporting year are reported results. Future values are typed as targets or forecasts and do not take their forecast year as a reporting year. Publication dates are never reporting years.
- **Forecast wording:** "projected to …", "expected to …", "on track for …" are forecasts. A bare "rising to 60%" with no context is not classified as a forecast.

## Troubleshooting
- **"The ESG app cannot start because these packages are not installed"** — run the install command above in the project's `.venv`.
- **`py` is not recognized** — install Python from python.org and tick "Add python.exe to PATH", or use the full path to python.exe.
- **Execution of WINDOWS_VALIDATION.ps1 is blocked** — use `powershell -ExecutionPolicy Bypass -File .\WINDOWS_VALIDATION.ps1`.
- **torch install fails or is very slow** — install the CPU wheel from pytorch.org first.
- **NLI model download fails** — check internet access. Without the model, NLI results are UNAVAILABLE and affected claims are unassessed. The app reports the load error; it does not invent results.
- **Web search returns nothing or is blocked** — the diagnostics panel records the failure. A failed search is not "no greenwashing".
- **Port 8501 in use** — add `--server.port 8600`.
- **Tests report "Failed to import test module"** — a required package is missing from `.venv`. Re-run the install command.

## Known limitations
- The forecast phrase list is intentionally short. Real report wording may need more phrases, each with tests.
- Two-year sentences without forward-looking wording assign no reporting year (conservative, by design).
- The evidence thresholds (0.55 strong, 0.35 weak) are retrieval thresholds, not truth thresholds.
- There is no independent labelled dataset in the project, so no accuracy, calibration, or company-level performance is claimed.
