$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path "$PSScriptRoot\..")
py -m pip install --upgrade pip
py -m pip install -r requirements.txt pyinstaller
pyinstaller --clean --noconfirm dashboard-matrix.spec
Write-Host "Executable created at dist\dashboard-matrix.exe"
