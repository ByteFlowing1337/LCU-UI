
# Build script for LCU-UI Backend (PyInstaller -> Tauri sidecar)

$ErrorActionPreference = "Stop"

# Resolve paths relative to repo root
$scriptDir = Split-Path -Parent $PSCommandPath       # .../src/build
$srcDir    = Split-Path -Parent $scriptDir           # .../src
$repoRoot  = Split-Path -Parent $srcDir              # repo root

$entry       = Join-Path $srcDir "main.py"
$templates   = Join-Path $srcDir "templates"
$staticRoot  = Join-Path $repoRoot "static"
$venvPython  = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    $python = $venvPython
} else {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        $python = $pythonCommand.Source
    } else {
        Write-Host "Error: Python was not found. Create .venv or ensure python is on PATH."
        exit 1
    }
}

# Use module invocation so the build does not rely on a pyinstaller.exe shim being present.
& $python -c "import PyInstaller" 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: PyInstaller is not installed for '$python'."
    Write-Host "Install it with one of:"
    Write-Host "  `"$python`" -m pip install pyinstaller"
    Write-Host "  uv pip install --python `"$python`" pyinstaller"
    exit 1
}

$pyInstallerArgs = @(
    "-m", "PyInstaller",
    "-F", $entry,
    "-n", "desktop_main",
    "--add-data", "$templates;templates",
    "--add-data", "$staticRoot;static",
    "--hidden-import", "engineio.async_drivers.threading",
    "--hidden-import", "flask_socketio",
    "--clean",
    "--noconfirm"
)

Write-Host "Building backend with PyInstaller using $python..."
& $python @pyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "Error: PyInstaller build failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

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
