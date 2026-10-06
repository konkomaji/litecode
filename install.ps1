# litecode installer (Windows PowerShell). Built by Konko Maji.
$ErrorActionPreference = "Stop"
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) { Write-Host "Python 3.10+ is required. Install it from python.org first."; exit 1 }
& python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) { Write-Host "Python 3.10+ is required."; exit 1 }
Set-Location $PSScriptRoot
& python -m pip install --user -e .
Write-Host "Installed. Running setup..."
& python -m litecode.cli setup
