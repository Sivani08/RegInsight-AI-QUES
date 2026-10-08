param([string]$Python='.venv\Scripts\python.exe',[int]$Port=8000)
$projectRoot=Split-Path -Parent $PSScriptRoot
& (Join-Path $projectRoot 'Start-RegInsight.ps1') -Local -Python $Python -Port $Port -NoBrowser
