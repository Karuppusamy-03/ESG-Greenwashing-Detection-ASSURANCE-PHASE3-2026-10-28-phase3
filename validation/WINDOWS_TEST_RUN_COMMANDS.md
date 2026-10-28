# Windows PowerShell — run the full validation and send back results

Run from the project folder. Do not run any company analysis or delete data.

```powershell
cd "C:\path\to\ESG-Greenwashing-Detection-System-main"
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pip freeze | Out-File validation\windows_pip_freeze.txt -Encoding utf8
```
Record: `validation\windows_pip_freeze.txt`. Note any install error verbatim; do not continue past a failed install without sending it.

**1. Compile check**
```powershell
.\.venv\Scripts\python.exe -m compileall -q . ; "compileall exit=$LASTEXITCODE"
```

**2. Full suite via unittest (main result)**
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -t tests -v *> validation\windows_unittest_full.log
"unittest exit=$LASTEXITCODE"
Select-String -Path validation\windows_unittest_full.log -Pattern "^Ran |^OK|^FAILED"
```

**3. Full suite via pytest (cross-check)**
```powershell
.\.venv\Scripts\python.exe -m pytest -q *> validation\windows_pytest.log
"pytest exit=$LASTEXITCODE"
```

**4. Live workflow test (opt-in, needs internet)**
```powershell
$env:ESG_LIVE_TESTS = "1"
.\.venv\Scripts\python.exe -m unittest tests.test_live_workflows -v *> validation\windows_live.log
"live exit=$LASTEXITCODE"
Remove-Item Env:\ESG_LIVE_TESTS
```

**5. Streamlit startup (stop with Ctrl+C after it prints a URL)**
```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.headless true *> validation\windows_streamlit.log
```
Success: the log shows `Local URL: http://localhost:8501`. Then stop it. Also check that the URL responds:
```powershell
Start-Process "http://localhost:8501"
```

Send back: the `Ran`/`OK`/`FAILED` lines, the three exit codes, the pip freeze file, and the full text of any ERROR or FAIL block.
