#!/usr/bin/env pwsh
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."
uv run --python 3.11 pyinstaller --clean packaging/transcrb.spec
Write-Host "Built: dist\transcrb\transcrb.exe"
