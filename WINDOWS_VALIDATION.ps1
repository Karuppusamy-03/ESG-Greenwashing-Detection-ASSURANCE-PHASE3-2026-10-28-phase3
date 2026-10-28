<#
Windows validation for the ESG Greenwashing Detection System.

Usage (from the project folder):
    powershell -ExecutionPolicy Bypass -File .\WINDOWS_VALIDATION.ps1
    powershell -ExecutionPolicy Bypass -File .\WINDOWS_VALIDATION.ps1 -InstallDependencies
    powershell -ExecutionPolicy Bypass -File .\WINDOWS_VALIDATION.ps1 -IncludeLiveTests

What it does:
  1. Checks Python 3.11-3.13 and the project's .venv.
  2. Optionally installs requirements.txt and pytest (only with -InstallDependencies).
  3. Checks which required packages import.
  4. Runs compileall.
  5. Runs the unit test suite (mocked and synthetic tests) with unittest.
  6. Optionally runs live tests (only with -IncludeLiveTests; needs internet).
  7. Starts Streamlit on a private port and checks that it answers HTTP 200.
  8. Writes logs and SUMMARY.txt to validation\results_<timestamp>\.

It never deletes data\ or output\ and never runs a company analysis.
Each step records its real exit code. A step is reported PASS only if its
command exited 0. Nothing is marked PASS by assumption.
#>
param(
    [switch]$InstallDependencies,
    [switch]$IncludeLiveTests,
    [int]$StreamlitPort = 8599
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Out = Join-Path $Root "validation\results_$Stamp"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$Summary = New-Object System.Collections.Generic.List[string]
$Results = @{}

function Add-Result([string]$Name, [string]$Status, [string]$Detail) {
    $Results[$Name] = $Status
    $Summary.Add(("{0,-28} {1,-22} {2}" -f $Name, $Status, $Detail))
    Write-Host ("{0,-28} {1,-22} {2}" -f $Name, $Status, $Detail)
}

Write-Host "Results folder: $Out" -ForegroundColor Cyan

# 1. Python launcher and project venv
$Py = Join-Path $Root ".venv\Scripts\python.exe"
$PyVersion = ""
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PyVersion = (& py -3.13 --version 2>&1) -join " "
    if ($LASTEXITCODE -ne 0) { $PyVersion = (& py -3.12 --version 2>&1) -join " " }
    if ($LASTEXITCODE -ne 0) { $PyVersion = (& py -3.11 --version 2>&1) -join " " }
}
if (-not (Test-Path $Py)) {
    if ($PyVersion -match "Python 3\.(11|12|13)") {
        Write-Host "Creating .venv with $PyVersion" -ForegroundColor Yellow
        if ($PyVersion -match "3\.13") { & py -3.13 -m venv .venv } elseif ($PyVersion -match "3\.12") { & py -3.12 -m venv .venv } else { & py -3.11 -m venv .venv }
    }
}
if (Test-Path $Py) {
    $VenvVersion = (& $Py --version 2>&1) -join " "
    Add-Result "venv" "PASS" "$VenvVersion at .venv"
} else {
    Add-Result "venv" "BLOCKED" "No .venv and no Python 3.11-3.13 found. Install Python 3.13 from python.org and re-run."
    $Summary | Out-File (Join-Path $Out "SUMMARY.txt") -Encoding utf8
    Write-Host "`nStopped: no Python environment. See $Out\SUMMARY.txt" -ForegroundColor Red
    exit 2
}

# 2. Optional dependency install (explicit request only)
if ($InstallDependencies) {
    & $Py -m pip install --upgrade pip *> (Join-Path $Out "pip_install.log")
    & $Py -m pip install -r requirements.txt *>> (Join-Path $Out "pip_install.log")
    $InstallCode = $LASTEXITCODE
    & $Py -m pip install pytest *>> (Join-Path $Out "pip_install.log")
    $PytestCode = $LASTEXITCODE
    if ($InstallCode -eq 0 -and $PytestCode -eq 0) { Add-Result "install requirements" "PASS" "pip exit 0 (requirements and pytest)" }
    else { Add-Result "install requirements" "FAIL" "requirements exit $InstallCode, pytest exit $PytestCode; see pip_install.log" }
} else {
    Add-Result "install requirements" "SKIPPED" "Run with -InstallDependencies to install"
}

# 3. Package import check
$Packages = "streamlit","pandas","numpy","sklearn","xgboost","shap","transformers","torch","sentence_transformers","pymupdf","plotly","ddgs","requests","truststore","bs4","matplotlib","pytest"
$ImportLines = @()
foreach ($pkg in $Packages) {
    $name = $pkg
    if ($pkg -eq "pymupdf") { $name = "pymupdf" }
    & $Py -c "import $name" *> $null
    if ($LASTEXITCODE -eq 0) { $ImportLines += "OK      $pkg" } else { $ImportLines += "MISSING $pkg" }
}
$ImportLines | Out-File (Join-Path $Out "imports.txt") -Encoding utf8
$Missing = @($ImportLines | Where-Object { $_ -like "MISSING*" })
if ($Missing.Count -eq 0) { Add-Result "package imports" "PASS" "all $($Packages.Count) importable" }
else { Add-Result "package imports" "PARTIAL" "$($Missing.Count) missing; see imports.txt" }

# 4. Compile check
& $Py -m compileall -q . *> (Join-Path $Out "compile.log")
if ($LASTEXITCODE -eq 0) { Add-Result "compileall" "PASS" "exit 0" } else { Add-Result "compileall" "FAIL" "exit $LASTEXITCODE; see compile.log" }

# 5. Unit tests (mocked + synthetic). Real-dependency tests may be blocked by missing packages.
& $Py -m unittest discover -s tests -p "test_*.py" -t tests -v *> (Join-Path $Out "unittest.log")
$UnitCode = $LASTEXITCODE
$UnitLine = (Select-String -Path (Join-Path $Out "unittest.log") -Pattern "^(Ran |OK|FAILED)" | ForEach-Object { $_.Line }) -join " | "
$Errs = (Select-String -Path (Join-Path $Out "unittest.log") -Pattern "^ERROR:").Count
$Fails = (Select-String -Path (Join-Path $Out "unittest.log") -Pattern "^FAIL:").Count
if ($UnitCode -eq 0) { Add-Result "unittest (all)" "PASS" $UnitLine }
elseif ($Fails -eq 0 -and $Errs -gt 0) { Add-Result "unittest (all)" "BLOCKED-PARTIAL" "0 assertion failures; $Errs blocked by errors (see unittest.log). $UnitLine" }
else { Add-Result "unittest (all)" "FAIL" "$Fails assertion failures, $Errs errors. $UnitLine" }

# 6. Live tests (optional, need internet)
if ($IncludeLiveTests) {
    $env:ESG_LIVE_TESTS = "1"
    & $Py -m unittest tests.test_live_workflows -v *> (Join-Path $Out "live.log")
    $LiveCode = $LASTEXITCODE
    Remove-Item Env:\ESG_LIVE_TESTS -ErrorAction SilentlyContinue
    if ($LiveCode -eq 0) { Add-Result "live tests" "PASS" "exit 0 (internet required)" } else { Add-Result "live tests" "FAIL" "exit $LiveCode; see live.log" }
} else {
    Add-Result "live tests" "SKIPPED" "Run with -IncludeLiveTests (needs internet)"
}

# 7. Streamlit startup: start on a private port, check HTTP, stop.
$StOut = Join-Path $Out "streamlit.log"
$StErr = Join-Path $Out "streamlit_err.log"
$proc = Start-Process -FilePath $Py -ArgumentList @("-m","streamlit","run","app.py","--server.headless","true","--server.port","$StreamlitPort") -PassThru -WindowStyle Hidden -RedirectStandardOutput $StOut -RedirectStandardError $StErr
$Http = "NO RESPONSE"
$Deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $Deadline) {
    Start-Sleep -Seconds 2
    if ($proc.HasExited) { break }
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$StreamlitPort/" -UseBasicParsing -TimeoutSec 5
        $Http = "HTTP $($r.StatusCode)"
        if ($r.StatusCode -eq 200) { break }
    } catch { $Http = "waiting: $($_.Exception.Message)" }
}
if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
$Http | Out-File (Join-Path $Out "streamlit_http.txt") -Encoding utf8
if ($Http -eq "HTTP 200") { Add-Result "streamlit startup" "PASS" "HTTP 200 on port $StreamlitPort" }
elseif ($proc.HasExited) { Add-Result "streamlit startup" "FAIL" "process exited early; see streamlit_err.log" }
else { Add-Result "streamlit startup" "FAIL" "no HTTP 200 within 60 s ($Http)" }

# 8. Summary
$Header = @(
  "ESG Greenwashing Detection - Windows validation",
  "Run: $Stamp",
  "Python: $(& $Py --version 2>&1)",
  "Mocked/synthetic tests run by 'unittest (all)'. Live tests need -IncludeLiveTests.",
  "A status of PASS means the command exited 0. Nothing was assumed.",
  "",
  ("{0,-28} {1,-22} {2}" -f "STEP","STATUS","DETAIL"),
  ("-" * 90)
)
($Header + $Summary) | Out-File (Join-Path $Out "SUMMARY.txt") -Encoding utf8
Write-Host "`nSUMMARY: $(Join-Path $Out 'SUMMARY.txt')" -ForegroundColor Green
