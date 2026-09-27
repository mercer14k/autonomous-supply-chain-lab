$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
py -3.12 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e '.[dev]'
Push-Location apps/web
pnpm install --frozen-lockfile
Pop-Location
$LabApi = Start-Process -FilePath .\.venv\Scripts\python.exe -ArgumentList '-m','uvicorn','apps.api.main:app','--host','127.0.0.1','--port','8000' -PassThru
try { Set-Location apps/web; pnpm dev } finally { Stop-Process -Id $LabApi.Id -ErrorAction SilentlyContinue }
