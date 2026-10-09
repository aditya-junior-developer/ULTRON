$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
$agentPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (!(Test-Path $agentPython)) { throw 'Run scripts\Setup-Windows.ps1 first.' }
if (!(Test-Path 'node_modules')) { throw 'JavaScript dependencies are missing. Run scripts\Setup-Windows.ps1.' }
$env:ULTRON_PYTHON = $agentPython
& npm.cmd run build
if ($LASTEXITCODE -ne 0) { throw 'Build failed; ULTRON was not started.' }
& npm.cmd run desktop
if ($LASTEXITCODE -ne 0) { throw 'Desktop launch failed. Check the displayed error.' }
