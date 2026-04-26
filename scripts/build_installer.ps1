#!/usr/bin/env pwsh
param(
    [string]$Version = ""
)
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

# 1) PyInstaller -> dist\winwhisp\
uv run --python 3.11 pyinstaller --clean packaging/transcrb.spec

# 2) Inno Setup -> dist\installer\WinWhisp-<version>-setup.exe
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    $candidates = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { $iscc = $p; break }
    }
}
if (-not $iscc) {
    throw "Inno Setup (iscc) не найден. Установи: winget install JRSoftware.InnoSetup"
}

if ($Version) {
    & $iscc "/DAppVersion=$Version" packaging/installer.iss
} else {
    & $iscc packaging/installer.iss
}
Write-Host "Installer output: dist\installer\"
Get-ChildItem dist\installer\WinWhisp-*-setup.exe -ErrorAction SilentlyContinue | Format-Table Name, Length, LastWriteTime
