$ErrorActionPreference = 'Stop'
$model = 'qwen3:1.7b'
$systemDrive = Get-PSDrive -Name ([IO.Path]::GetPathRoot($env:LOCALAPPDATA).Substring(0,1))
$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
$ollamaExe = if ($ollamaCommand) { $ollamaCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe' }
if (-not (Test-Path -LiteralPath $ollamaExe)) {
    if ($systemDrive.Free -lt 12GB) { throw 'Free at least 12 GB before installing Ollama. No files were downloaded or deleted.' }
    $installer = Join-Path $env:TEMP 'inspection-insights-OllamaSetup.exe'
    Invoke-WebRequest -Uri 'https://ollama.com/download/OllamaSetup.exe' -OutFile $installer -UseBasicParsing
    $signature = Get-AuthenticodeSignature -LiteralPath $installer
    if ($signature.Status -ne 'Valid') { throw 'Ollama installer signature could not be verified; installation stopped.' }
    $installation = Start-Process -FilePath $installer -ArgumentList '/VERYSILENT','/NORESTART' -WindowStyle Hidden -PassThru
    # Wait for the installer itself, not the background tray app it launches.
    $installation.WaitForExit()
    if ($installation.ExitCode -ne 0) { throw "Ollama installer failed: $($installation.ExitCode)" }
    Remove-Item -LiteralPath $installer
}
$env:OLLAMA_HOST = '127.0.0.1:11434'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
try { Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null }
catch { Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden | Out-Null }
$ready = $false
for ($attempt=0; $attempt -lt 30; $attempt++) {
    try { Invoke-RestMethod 'http://127.0.0.1:11434/api/version' -TimeoutSec 2 | Out-Null; $ready=$true; break }
    catch { Start-Sleep -Milliseconds 500 }
}
if (-not $ready) { throw 'Ollama did not start.' }
& $ollamaExe pull $model
if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Run this script again to resume.' }
& (Join-Path $PSScriptRoot 'start-ollama.ps1') -Model $model
Write-Host 'Setup complete. Restart the project with .\scripts\start-real.ps1.'
