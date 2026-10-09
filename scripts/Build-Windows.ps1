$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
& uv run --frozen --all-extras python scripts/build-agent.py
if ($LASTEXITCODE -ne 0) { throw 'Backend packaging failed.' }
& npm.cmd run package:win
if ($LASTEXITCODE -ne 0) { throw 'Windows executable packaging failed.' }
& python scripts/release-manifest.py
if ($LASTEXITCODE -ne 0) { throw 'Checksum generation failed.' }
Write-Host 'Installer and portable executables are in apps\desktop\release. Nothing was published.'
