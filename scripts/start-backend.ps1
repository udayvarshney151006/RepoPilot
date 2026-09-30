$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExecutable)) { throw "Run scripts/setup-local.ps1 first." }
Set-Location -LiteralPath (Join-Path $projectRoot 'backend')
& $pythonExecutable -m alembic upgrade head
if ($LASTEXITCODE) { throw "Database migration failed" }
& $pythonExecutable -m uvicorn app.main:app --host 127.0.0.1 --port 8000
