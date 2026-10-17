$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
function Check-ExitCode {
    if ($LASTEXITCODE -ne 0) { throw "Build command failed (exit $LASTEXITCODE)." }
}
py -3.12 -m pip install -r requirements-build.txt
Check-ExitCode
py -3.12 -m PyInstaller --noconfirm --clean --onefile --windowed --name QuickEdit --icon assets/app.ico --add-data "assets;assets" --collect-submodules mss creative_destruction_edit.py
Check-ExitCode
New-Item -ItemType Directory -Force dist/QuickEdit | Out-Null
Copy-Item dist/QuickEdit.exe dist/QuickEdit/QuickEdit.exe -Force
Copy-Item QUICKSTART.txt dist/QuickEdit/README.txt -Force
Write-Host "Ready: dist/QuickEdit/QuickEdit.exe"
