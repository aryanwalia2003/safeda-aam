# Install safeda-aam on Windows: downloads the latest standalone .exe
# release, installs it, and wires up PATH automatically — no manual setup,
# and it's usable in this same PowerShell window immediately.
#
# Usage (single command):
#   irm https://raw.githubusercontent.com/aryanwalia2003/safeda-aam/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

$Repo       = "aryanwalia2003/safeda-aam"
$InstallDir = Join-Path $env:LOCALAPPDATA "safeda-aam"
$ExeName    = "safeda-aam.exe"
$AssetName  = "safeda-aam-windows-x64.exe"

Write-Host "Installing safeda-aam..."

New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$url  = "https://github.com/$Repo/releases/latest/download/$AssetName"
$dest = Join-Path $InstallDir $ExeName

Write-Host "Downloading $url"
Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing

# Persist PATH change for future sessions.
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($null -eq $userPath) { $userPath = "" }
if ($userPath -notlike "*$InstallDir*") {
    $newPath = if ($userPath.Trim().Length -eq 0) { $InstallDir } else { "$userPath;$InstallDir" }
    [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
    Write-Host "Added $InstallDir to your PATH (takes effect in new terminals)."
}

# Make it usable in *this* window right away too — no need to reopen anything.
if ($env:Path -notlike "*$InstallDir*") {
    $env:Path = "$env:Path;$InstallDir"
}

Write-Host ""
Write-Host "Installed! Try: safeda-aam --help"
