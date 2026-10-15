& {
    $ErrorActionPreference = "Stop"
    $root = Split-Path $PSScriptRoot -Parent
    Set-Location $root
    if (Test-Path "$root\.git") {
        throw "Run this verifier in the separate extracted review folder, not the running VPS repository"
    }
    py -3.12 -m venv "$root\.verify-venv"
    if ($LASTEXITCODE -ne 0) { throw "Cannot create test environment" }
    $python = "$root\.verify-venv\Scripts\python.exe"
    & $python -m pip install pytest
    if ($LASTEXITCODE -ne 0) { throw "Cannot install test dependency" }
    & $python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Tests failed; do not deploy" }
    & $python -m compileall -q core data_feed streamlit_app.py
    if ($LASTEXITCODE -ne 0) { throw "Syntax check failed" }
    Write-Host "PASS: offline Python verification only; running server was not modified"
}
