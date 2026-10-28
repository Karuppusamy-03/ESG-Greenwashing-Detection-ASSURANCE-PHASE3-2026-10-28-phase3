# Windows PowerShell validation commands (run on your machine)

These steps could not be run in the Linux sandbox. Each lists what success looks like. Report any output that differs.

Work only in the project folder. Do not delete `data\`, `output\`, or any run folder containing `final_labels.csv`. Copy the project folder before starting if you want a safety net.

## A. Environment (once)

```powershell
cd "C:\path\to\ESG-Greenwashing-Detection-System-main"
py -3.13 --version        # or -3.12 / -3.11
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pytest
```
Success: pip finishes without an error. torch is large and may take a long time.

## B. Full offline test suite (software integrity, synthetic data)

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -t tests 2>&1 | Tee-Object -FilePath validation\windows_unittest.log
```
Expected: **0 errors, 0 failures**, with the skip count reported. Send back the final `Ran N tests` line and any `ERROR:` or `FAIL:` lines. A pass here proves software logic only, not detection accuracy.

Optional, with pytest:
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## C. Previously blocked modules (the main reason to run on Windows)

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_pair_review.ProducerConsumerIntegrationTests -v
.\.venv\Scripts\python.exe -m unittest tests.test_offline_workflows -v
.\.venv\Scripts\python.exe -m unittest tests.test_risk_heuristics -v
.\.venv\Scripts\python.exe -m unittest tests.test_nli_unavailable_scoring -v
.\.venv\Scripts\python.exe -m unittest tests.test_web_search -v
.\.venv\Scripts\python.exe -m unittest tests.test_risk_visualization -v
```
Key result: `test_app_shaped_analysis_round_trips_into_packets` exercises the real matcher and NLI detector, and it has not run anywhere yet. Send its output. `test_offline_workflows` includes the Fix 2 assertion updated in this session, which has not been executed.

## D. Compile and import check

```powershell
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe -c "import nli_config, contradiction_detector, risk_predictor, timeline_analyzer; print('imports ok')"
```

## E. Streamlit app startup (does not change any data)

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```
Success: the terminal prints a local URL (usually http://localhost:8501) and the page opens. Stop with Ctrl+C. Report any traceback. Do not run any company analysis yet.

## F. Database and saved-file integrity (read-only snapshot)

Before any analysis, record file hashes so changes are visible later:
```powershell
Get-ChildItem -Recurse -File data, output -ErrorAction SilentlyContinue | Get-FileHash -Algorithm SHA256 | Export-Csv validation\integrity_before.csv -NoTypeInformation
```
If `data\` does not exist yet, that is expected; report it. Keep the file. Run the same command after each later step and compare with `Compare-Object`.

## G. Review workflow on real saved analyses (requires real analyses from step E)

Start with an inspection (read-only):
```powershell
.\.venv\Scripts\python.exe -m evaluation.pair_review inspect --analysis "output\<your-analysis>.json"
```
Success: JSON with `ready_for_packets`. If `false`, report the `rejections` field. Do not force packets.

Then make packets (only when `ready_for_packets` is true). Use real reviewer names or IDs, not placeholders:
```powershell
.\.venv\Scripts\python.exe -m evaluation.pair_review make-packets --analysis "output\<your-analysis>.json" --out-dir "output\review_runs\<run-name>" --reviewer-a "<reviewer-A-id>" --reviewer-b "<reviewer-B-id>"
```
Reviewers each fill only their own packet. Labels go into the `reviewer_N_label` and `reviewer_N_notes` columns. Neither reviewer may open the other's packet, and neither may see model predictions. Validate each return:
```powershell
.\.venv\Scripts\python.exe -m evaluation.pair_review validate --packet "<packet-A.csv>" --returned "<returned-A.csv>"
.\.venv\Scripts\python.exe -m evaluation.pair_review validate --packet "<packet-B.csv>" --returned "<returned-B.csv>"
```
Reconcile, adjudicate, finalize, and evaluate follow the existing runbook sections 5.5 to 5.8 (`WINDOWS_HUMAN_REVIEW_RUNBOOK.md`). Use an adjudicator who is neither reviewer. Do not run `evaluate` as a result until the runbook's sample gate is met (at least 10 companies, with genuine adjudicated labels). A run on fewer labels is a pipeline check, not a performance result.

## H. Save the results

```powershell
git status   # only if this folder is a git clone; otherwise skip
Get-ChildItem -Recurse -File data, output -ErrorAction SilentlyContinue | Get-FileHash -Algorithm SHA256 | Export-Csv validation\integrity_after.csv -NoTypeInformation
Compare-Object (Import-Csv validation\integrity_before.csv) (Import-Csv validation\integrity_after.csv) -Property Hash, Path
```
An empty result from `Compare-Object` means no existing file changed. Send back the output.
