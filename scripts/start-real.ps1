param([string]$Python = ".venv\Scripts\python.exe")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $projectRoot 'start-real.ps1') -Python $Python
