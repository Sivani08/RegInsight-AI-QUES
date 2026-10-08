param([string]$Model = 'qwen3:1.7b')
$ErrorActionPreference = 'Stop'
$ollamaCommand = Get-Command ollama -ErrorAction SilentlyContinue
$ollamaExe = if ($ollamaCommand) { $ollamaCommand.Source } else { Join-Path $env:LOCALAPPDATA 'Programs\Ollama\ollama.exe' }
function Get-LocalModels {
    try { return Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 } catch { return $null }
}
$catalog = Get-LocalModels
if ($null -eq $catalog) {
    if (-not (Test-Path -LiteralPath $ollamaExe)) { throw 'Ollama is not installed. Run .\scripts\setup-ollama.ps1 after freeing disk space.' }
    $env:OLLAMA_HOST = '127.0.0.1:11434'
    $env:OLLAMA_NO_CLOUD = '1'
    $env:OLLAMA_NUM_PARALLEL = '1'
    Start-Process -FilePath $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden | Out-Null
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        $catalog = Get-LocalModels
        if ($null -ne $catalog) { break }
    }
}
if ($null -eq $catalog) { throw 'Ollama did not respond on localhost:11434.' }
if ($Model -notin @($catalog.models | ForEach-Object { $_.name })) { throw "Local model $Model is missing. Run .\scripts\setup-ollama.ps1." }
Write-Host "Local AI ready: $Model (no API key)."
