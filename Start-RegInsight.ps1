param(
    [ValidateRange(1,65535)][int]$Port=8018,
    [switch]$NoBrowser,
    [switch]$Local,
    [string]$Python='.venv\Scripts\python.exe'
)
$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot

if ($Local) {
    if (-not $env:DATABASE_URL) {
        throw 'Set DATABASE_URL to a running PostgreSQL database with pgvector. See START-HERE.md.'
    }
    if (-not (Test-Path -LiteralPath $Python)) {
        throw 'Create .venv and install requirements-app.txt first, or use the default Docker startup.'
    }
    & $Python scripts/migrate.py
    if ($LASTEXITCODE -ne 0) {throw 'Database migration failed.'}
    Write-Host "RegInsight is starting at http://127.0.0.1:$Port"
    & $Python -m uvicorn backend.api.main:app --host 127.0.0.1 --port $Port
    exit $LASTEXITCODE
}

$dockerCommand=Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCommand) {
    $dockerExe=$dockerCommand.Source
} else {
    $dockerExe=Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe'
}
if (-not (Test-Path -LiteralPath $dockerExe)) {
    throw 'Docker Desktop is required for the default one-command setup. Install and start Docker Desktop, then reopen PowerShell. For an existing PostgreSQL/pgvector server, use -Local and set DATABASE_URL.'
}
$dockerBin=Split-Path -Parent $dockerExe

$envFile=Join-Path $PSScriptRoot '.env'
$envText=''
if (Test-Path -LiteralPath $envFile) {
    $envText=[System.IO.File]::ReadAllText($envFile)
}

if ($envText -notmatch '(?m)^\s*POSTGRES_PASSWORD\s*=\s*\S') {
    $bytes=New-Object byte[] 32
    $generator=[System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {$generator.GetBytes($bytes)} finally {$generator.Dispose()}
    $password=[System.BitConverter]::ToString($bytes).Replace('-','').ToLowerInvariant()
    $passwordLine="POSTGRES_PASSWORD=$password"
    if ($envText -match '(?m)^\s*POSTGRES_PASSWORD\s*=') {
        $envText=[regex]::Replace($envText,'(?m)^\s*POSTGRES_PASSWORD\s*=.*$', $passwordLine, 1)
    } else {
        if ($envText.Length -gt 0 -and -not $envText.EndsWith("`n")) {$envText+="`r`n"}
        $envText+="$passwordLine`r`n"
    }
    $encoding=New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($envFile,$envText,$encoding)
    Write-Host 'Created a local .env with a random PostgreSQL password.'
}

$previousPort=$env:REGINSIGHT_PORT
$previousPath=$env:PATH
$env:REGINSIGHT_PORT="$Port"
$env:PATH="$dockerBin;$previousPath"
try {
    & $dockerExe info --format '{{.ServerVersion}}' 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker is installed but its engine is not running. Start Docker Desktop and rerun this command.'
    }
    & $dockerExe compose version 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw 'Docker Compose is unavailable. Update Docker Desktop and rerun this command.'
    }

    Write-Host 'Building and starting RegInsight, PostgreSQL, and the workflow worker. The first build and full inspection-data import may take several minutes.'
    & $dockerExe compose up --build --detach
    if ($LASTEXITCODE -ne 0) {throw 'Docker Compose failed while building or starting the application.'}

    $url="http://127.0.0.1:$Port"
    $ready=$false
    $lastHealthError=''
    for ($attempt=0; $attempt -lt 180; $attempt++) {
        try {
            $response=Invoke-WebRequest -Uri "$url/api/health" -UseBasicParsing -TimeoutSec 3
            if ($response.StatusCode -eq 200) {$ready=$true;break}
            $lastHealthError="Health endpoint returned HTTP $($response.StatusCode)."
        } catch {
            $lastHealthError=$_.Exception.Message
        }
        Start-Sleep -Seconds 3
    }

    if (-not $ready) {
        Write-Host 'The application did not become healthy. Recent service status and logs follow:'
        & $dockerExe compose ps
        & $dockerExe compose logs --tail 40 db migrate app worker
        throw "RegInsight did not become healthy at $url. $lastHealthError"
    }

    Write-Host "RegInsight is ready at $url"
    Write-Host 'To create the first administrator, run:'
    Write-Host '  docker compose exec app python scripts/create_user.py --name "Your Name" --role admin'
    Write-Host 'The command prompts for a private access key; use at least 32 characters.'
    Write-Host 'Stop the application with: docker compose down'
    if (-not $NoBrowser) {Start-Process $url}
} finally {
    $env:PATH=$previousPath
    if ($null -eq $previousPort) {
        Remove-Item Env:REGINSIGHT_PORT -ErrorAction SilentlyContinue
    } else {
        $env:REGINSIGHT_PORT=$previousPort
    }
}
