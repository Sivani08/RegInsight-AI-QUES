param([string]$Python = ".venv\Scripts\python.exe")
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$redisRoot = Join-Path $projectRoot 'runtime\redis'
$redisExe = Join-Path $redisRoot 'Redis-8.10.2-Windows-x64-cygwin\redis-server.exe'
if (-not (Test-Path -LiteralPath $redisExe)) { throw 'Portable Redis is missing. Run scripts/setup-redis.ps1 first.' }
& $Python -c "import redis; r=redis.Redis(socket_connect_timeout=.3,socket_timeout=.3); print(r.ping())" 2>$null
if ($LASTEXITCODE -eq 0) { Write-Output 'Redis is already responding on localhost:6379'; return }
$redisProcess = Start-Process -FilePath $redisExe -ArgumentList 'redis-local.conf' -WorkingDirectory $redisRoot -WindowStyle Hidden -PassThru
$redisProcess.Id | Set-Content -LiteralPath (Join-Path $redisRoot 'process-id.txt')
for ($attempt=0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 250
    & $Python -c "import redis; r=redis.Redis(socket_connect_timeout=.3,socket_timeout=.3); assert r.ping(); print('Redis ready on localhost:6379')" 2>$null
    if ($LASTEXITCODE -eq 0) { return }
}
throw 'Redis startup failed. Inspect runtime/redis/redis-local.log.'
