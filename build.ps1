param([switch]$OneFile)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) {
    py -3 -m venv .venv
}
.\.venv\Scripts\python -m pip install -q -r requirements.txt pyinstaller
.\.venv\Scripts\python -m unittest discover -s tests
if ($LASTEXITCODE -ne 0) { throw "Tests failed" }
if ($OneFile) { $env:ONEFILE = "1" } else { Remove-Item Env:ONEFILE -ErrorAction SilentlyContinue }
.\.venv\Scripts\pyinstaller FamilyTree.spec --noconfirm
