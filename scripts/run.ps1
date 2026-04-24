#!/usr/bin/env pwsh
# Запуск transcrb из исходников через uv.
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."
uv run --python 3.11 python -m transcrb
