# ---------------------------------------------------------------------------
# start_local_pg.ps1 — spin up the LOCAL test PostgreSQL that mimics Supabase.
#
# This is ONLY for running the test suite on a developer machine.
# It never touches a real Supabase project and never touches
# data/healthcare_feedback.db.
#
# Usage (from the repository root, with Docker Desktop running):
#   powershell -ExecutionPolicy Bypass -File tests\start_local_pg.ps1
#
# Then apply the schema:
#   1. tests\local_supabase_stub.sql          (roles + auth.uid() stub)
#   2. supabase\migrations\0001..0003         (same files as Supabase SQL Editor)
#
# Stop / destroy later with:
#   docker stop pgtest; docker rm pgtest
# ---------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

$Container = "pgtest"
$Image     = "postgres:16-alpine"
$Port      = 5433
$User      = "postgres"
$Password  = "postgres"

function Invoke-Checked {
    param([string]$File, [string[]]$Args)
    & $File @Args
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $File $($Args -join ' ')" }
}

# 1. Is Docker running?
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) { Write-Error "docker CLI not found. Install Docker Desktop."; exit 1 }
$daemon = docker info 2>$null
if ($LASTEXITCODE -ne 0) { Write-Error "Docker daemon not running. Start Docker Desktop first."; exit 1 }

# 2. Reuse the container if it already exists
$existing = docker ps -a --filter "name=^$Container$" --format "{{.Names}}"
if ($existing -eq $Container) {
    $state = docker inspect $Container --format "{{.State.Status}}"
    if ($state -ne "running") { docker start $Container | Out-Null }
    Write-Host "Reusing existing container '$Container'." -ForegroundColor Yellow
} else {
    Write-Host "Creating container '$Container' ($Image) on port $Port..." -ForegroundColor Cyan
    docker run -d --name $Container `
        -e POSTGRES_USER=$User `
        -e POSTGRES_PASSWORD=$Password `
        -e POSTGRES_DB=postgres `
        -p "${Port}:5432" `
        $Image | Out-Null
    # Wait for readiness
    $ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        docker exec $Container pg_isready -U $User 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { Write-Error "PostgreSQL did not become ready in 30s."; exit 1 }
}

# 3. Apply the Supabase-compatibility stub (roles + auth.users + auth.uid())
$repo = Split-Path -Parent $PSScriptRoot
$stub = Join-Path $PSScriptRoot "local_supabase_stub.sql"
Write-Host "Applying tests\local_supabase_stub.sql ..." -ForegroundColor Cyan
Get-Content -Raw -Path $stub | docker exec -i $Container psql -U $User -d postgres -v ON_ERROR_STOP=1 -f -

# 4. Apply the real migrations (same files used in Supabase SQL Editor)
foreach ($m in @(
    "0001_camps_and_profiles.sql",
    "0002_feedback_tables.sql",
    "0003_rls_policies.sql"
)) {
    $path = Join-Path $repo "supabase\migrations\$m"
    Write-Host "Applying supabase\migrations\$m ..." -ForegroundColor Cyan
    Get-Content -Raw -Path $path | docker exec -i $Container psql -U $User -d postgres -v ON_ERROR_STOP=1 -f -
}

Write-Host ""
Write-Host "Local Supabase-like PostgreSQL is ready:" -ForegroundColor Green
Write-Host "  DSN: postgresql://$User`:$Password@127.0.0.1:$Port/postgres"
Write-Host "  Run tests with:  python -m pytest tests/ -v"
