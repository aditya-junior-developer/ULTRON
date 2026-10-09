$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
if (![Environment]::Is64BitOperatingSystem) { throw 'ULTRON requires 64-bit Windows.' }
& python --version
if ($LASTEXITCODE -ne 0) { throw 'Python 3.12–3.14 is required.' }
& node --version
if ($LASTEXITCODE -ne 0) { throw 'Node.js 24 is required.' }
& python -m pip install uv==0.12.24
if ($LASTEXITCODE -ne 0) { throw 'uv installation failed.' }
& uv sync --frozen --all-extras
if ($LASTEXITCODE -ne 0) { throw 'Locked Python dependency installation failed.' }
& npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw 'Locked JavaScript dependency installation failed.' }
& npx.cmd --no install-electron --no
if ($LASTEXITCODE -ne 0) { throw 'Verified Electron runtime installation failed.' }
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Application build failed.' }
& uv run --frozen --all-extras pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Python validation failed.' }
& npm.cmd test
if ($LASTEXITCODE -ne 0) { throw 'JavaScript validation failed.' }
Write-Host 'Development installation complete. Start with scripts\Start-ULTRON.ps1.'
Write-Host 'Provider keys and speech models remain private local setup; nothing was deployed.'
