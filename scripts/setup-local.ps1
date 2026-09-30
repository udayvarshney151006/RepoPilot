param([string]$Python = "python")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath ".env")) { Copy-Item -LiteralPath ".env.example" -Destination ".env" }
if (-not (Test-Path -LiteralPath "frontend/.env.local")) { Copy-Item -LiteralPath "frontend/.env.example" -Destination "frontend/.env.local" }
if (-not (Test-Path -LiteralPath ".venv")) { & $Python -m venv .venv; if ($LASTEXITCODE) { throw "Creating Python environment failed" } }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
if ($LASTEXITCODE) { throw "Upgrading pip failed" }
& .\.venv\Scripts\python.exe -m pip install -c './backend/requirements.lock.txt' -e './backend[test]'
if ($LASTEXITCODE) { throw "Installing backend dependencies failed" }
Push-Location -LiteralPath backend
try {
    & ..\.venv\Scripts\python.exe -m alembic upgrade head
    if ($LASTEXITCODE) { throw "Database migration failed" }
} finally { Pop-Location }
Push-Location -LiteralPath frontend
try {
    & corepack pnpm install --frozen-lockfile
    if ($LASTEXITCODE) { throw "Installing frontend dependencies failed" }
} finally { Pop-Location }
Write-Host "Setup complete. Run scripts/start-backend.ps1 and scripts/start-frontend.ps1 in separate terminals."
