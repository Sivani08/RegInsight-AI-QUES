param([string]$Python = ".venv\Scripts\python.exe")
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$runtimeRoot=Join-Path $projectRoot 'runtime\redis'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$zipPath=Join-Path $runtimeRoot 'redis.zip'
$sourceUrl='https://github.com/redis-windows/redis-windows/releases/download/8.10.2/Redis-8.10.2-Windows-x64-cygwin.zip'
Invoke-WebRequest -Uri $sourceUrl -OutFile $zipPath
$expectedHash='6de5cc7f5adbf97b5928b13766383d4ad424626ef3d8b313ffff12d820ec6fc1'
if ((Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) { throw 'Redis checksum verification failed' }
Expand-Archive -LiteralPath $zipPath -DestinationPath $runtimeRoot -Force
$settings=@('bind 127.0.0.1','protected-mode yes','port 6379','save ""','appendonly no','maxmemory 128mb','maxmemory-policy allkeys-lru','logfile "redis-local.log"')
$settings | Set-Content -LiteralPath (Join-Path $runtimeRoot 'redis-local.conf') -Encoding ascii
@{version='8.10.2';source=$sourceUrl;sha256=$expectedHash;distribution='Community Windows build; local development only'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeRoot 'installation.json')
& (Join-Path $PSScriptRoot 'start-redis.ps1') -Python $Python
