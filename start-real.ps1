param([string]$Python='.venv\Scripts\python.exe')
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $env:DATABASE_URL) {throw 'Set DATABASE_URL to the authoritative PostgreSQL database.'}
& $Python -c "from backend.database.store import Store; info=Store().info(); assert info and info.get('data_label')!='SYNTHETIC DEMONSTRATION DATA', 'Import and reconcile the real dataset first.'"
if ($LASTEXITCODE -ne 0) {throw 'Real dataset validation failed.'}
& $PSScriptRoot\Start-RegInsight.ps1 -Local -Python $Python -Port 8000 -NoBrowser
