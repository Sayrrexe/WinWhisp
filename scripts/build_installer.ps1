#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

# 1) PyInstaller -> dist\winwhisp\
uv run --python 3.11 pyinstaller --clean packaging/transcrb.spec

# 2) Inno Setup -> C:\Projects\test-transcrb\WinWhisp-<version>-setup.exe
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

& $iscc packaging/installer.iss
Write-Host "Installer: C:\Projects\test-transcrb\"
Get-ChildItem C:\Projects\test-transcrb\WinWhisp-*-setup.exe | Format-Table Name, Length, LastWriteTime
