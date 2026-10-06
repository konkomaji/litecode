# litecode installer for Windows. Built by Konko Maji.
#
#   irm https://raw.githubusercontent.com/konkomaji/litecode/main/install.ps1 | iex
#
# or, from a cloned repo:  .\install.ps1
#
# Installs litecode into its own Python environment (%LOCALAPPDATA%\litecode),
# puts the `litecode` and `lite` commands on your PATH, then starts setup.
# Set LITECODE_NO_SETUP=1 to skip setup. Uninstall: delete %LOCALAPPDATA%\litecode.

$ErrorActionPreference = "Stop"
# wrapped in a function so a failed check returns instead of closing a piped (irm | iex) session
function Install-Litecode {
$Zip = "https://github.com/konkomaji/litecode/archive/refs/heads/main.zip"
$Home_ = Join-Path $env:LOCALAPPDATA "litecode"
$Venv = Join-Path $Home_ "venv"
$Bin = Join-Path $Home_ "bin"

function Say($m) { Write-Host "  $m" }
function Find-Python {
    foreach ($c in @(@("py", "-3"), @("python"), @("python3"))) {
        $exe = Get-Command $c[0] -ErrorAction SilentlyContinue
        if (-not $exe) { continue }
        if ($exe.Source -like "*WindowsApps*") { continue }   # Microsoft Store stub, not a real Python
        $args_ = @($c | Select-Object -Skip 1) + @("-c", "import sys; print(sys.version_info >= (3, 10))")
        try { $ok = & $c[0] @args_ 2>$null } catch { continue }
        if ($ok -eq "True") { return ,$c }
    }
    return $null
}

Write-Host ""
Write-Host "* litecode installer" -ForegroundColor DarkYellow
Write-Host "  Built by Konko Maji" -ForegroundColor DarkGray
Write-Host ""

$py = Find-Python
if (-not $py) {
    Say "Python 3.10 or newer is required."
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        $a = Read-Host "  Install Python 3.12 with winget now? [Y/n]"
        if ($a -eq "" -or $a -match "^[yY]") {
            winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "User") + ";" + [Environment]::GetEnvironmentVariable("Path", "Machine")
            $py = Find-Python
        }
    }
    if (-not $py) {
        Say "Install Python from https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), then run this again."
        return
    }
}
$pyExe = $py[0]; $pyArgs = @($py | Select-Object -Skip 1)
Say "Python: $(& $pyExe @pyArgs -c 'import sys; print(sys.version.split()[0])')"

# source: this repo when run from a clone, else the latest release zip
$src = $Zip
if ($PSScriptRoot -and (Test-Path (Join-Path $PSScriptRoot "pyproject.toml"))) { $src = $PSScriptRoot }

New-Item -ItemType Directory -Force $Home_, $Bin | Out-Null
if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    Say "Creating environment in $Venv"
    & $pyExe @pyArgs -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Say "Could not create a Python environment."; return }
}
$vpy = Join-Path $Venv "Scripts\python.exe"
Say "Installing litecode from $src"
& $vpy -m pip install --quiet --disable-pip-version-check --upgrade pip | Out-Null
if ($src -eq $Zip) { & $vpy -m pip install --quiet --disable-pip-version-check --upgrade $src }
else { & $vpy -m pip install --quiet --disable-pip-version-check --upgrade -e $src }
if ($LASTEXITCODE -ne 0) { Say "pip install failed."; return }

# shims call the venv's entry point (not `python -m`, which would import from the current folder)
$exe = Join-Path $Venv "Scripts\litecode.exe"
foreach ($n in @("litecode", "lite")) {
    Set-Content -Encoding ASCII (Join-Path $Bin "$n.cmd") "@echo off`r`n`"$exe`" %*"
}
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }
if (($userPath -split ";") -notcontains $Bin) {
    [Environment]::SetEnvironmentVariable("Path", ($userPath.TrimEnd(";") + ";" + $Bin).TrimStart(";"), "User")
    Say "Added $Bin to your PATH."
}
if (($env:Path -split ";") -notcontains $Bin) { $env:Path = "$env:Path;$Bin" }

Write-Host ""
Write-Host "  litecode is installed." -ForegroundColor Green
Say "Commands: litecode (or lite). Open a new terminal if the command is not found."
Write-Host ""
if (-not $env:LITECODE_NO_SETUP) {
    & $exe setup
    Write-Host ""
    Say "Next: cd into a project folder and run: litecode"
}
}
Install-Litecode

