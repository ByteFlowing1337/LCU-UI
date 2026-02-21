
# Build script for LCU-UI Backend (PyInstaller -> Tauri sidecar)

$ErrorActionPreference = "Stop"

# Resolve paths relative to repo root
$scriptDir = Split-Path -Parent $PSCommandPath       # .../src/build
$srcDir    = Split-Path -Parent $scriptDir            # .../src
$repoRoot  = Split-Path -Parent $srcDir               # repo root

$pyinstaller = Join-Path $repoRoot ".venv/Scripts/pyinstaller.exe"
if (-not (Test-Path $pyinstaller)) {
    # Fallback to PATH-resolved pyinstaller if .venv path is unavailable (e.g., CI)
    $pyinstaller = "pyinstaller"
}
$entry       = Join-Path $srcDir "main.py"
$templates   = Join-Path $srcDir "templates"
$staticRoot  = Join-Path $repoRoot "static"

Write-Host "Building backend with PyInstaller..."
& $pyinstaller -F $entry -n desktop_main `
  --add-data "$templates;templates" `
  --add-data "$staticRoot;static" `
  --hidden-import "engineio.async_drivers.threading" `
  --hidden-import "flask_socketio" `
  --clean --noconfirm

# Move and rename for Tauri sidecar
$TARGET_DIR = Join-Path $repoRoot "src-tauri/binaries"
if (!(Test-Path $TARGET_DIR)) {
    New-Item -ItemType Directory -Path $TARGET_DIR | Out-Null
}

$SOURCE = Join-Path $repoRoot "dist/desktop_main.exe"
$DEST   = Join-Path $TARGET_DIR "desktop_main-x86_64-pc-windows-msvc.exe"

if (Test-Path $SOURCE) {
    Write-Host "Moving binary to $DEST..."
    Copy-Item $SOURCE -Destination $DEST -Force
    # Also copy as desktop_main.exe for fallback/testing
    Copy-Item $SOURCE -Destination (Join-Path $TARGET_DIR "desktop_main.exe") -Force
    Write-Host "Build Complete!"
} else {
    Write-Host "Error: Build failed, $SOURCE not found."
    exit 1
}
