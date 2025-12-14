
# Build script for LCU-UI Backend

# 1. Install PyInstaller if not present (assuming in venv)
# pip install pyinstaller

# 2. Build the executable
Write-Host "Building backend with PyInstaller..."
& .venv\Scripts\pyinstaller.exe -F app.py -n desktop_main --add-data "templates;templates" --add-data "static;static" --hidden-import "engineio.async_drivers.threading" --hidden-import "flask_socketio" --clean --noconfirm

# 3. Move and Rename for Tauri Sidecar
$TARGET_DIR = "src-tauri/binaries"
if (!(Test-Path $TARGET_DIR)) {
    New-Item -ItemType Directory -Path $TARGET_DIR
}

$SOURCE = "dist/desktop_main.exe"
$DEST = "$TARGET_DIR/desktop_main-x86_64-pc-windows-msvc.exe"

if (Test-Path $SOURCE) {
    Write-Host "Moving binary to $DEST..."
    Copy-Item $SOURCE -Destination $DEST -Force
    # Also copy as desktop_main.exe for fallback/testing
    Copy-Item $SOURCE -Destination "$TARGET_DIR/desktop_main.exe" -Force
    Write-Host "Build Complete!"
} else {
    Write-Host "Error: Build failed, $SOURCE not found."
    exit 1
}
