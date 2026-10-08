param([string]$Python = ".venv\Scripts\python.exe")
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python)) { throw "Create the virtual environment and install requirements first. See README.md." }
& $Python scripts/bootstrap.py --serve --host 127.0.0.1
