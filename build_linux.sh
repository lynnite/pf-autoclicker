#!/usr/bin/env bash
# Build the Linux executable with PyInstaller.
set -e
cd "$(dirname "$0")"

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt pyinstaller

python3 -m PyInstaller --clean --noconfirm autoclicker.spec

echo
echo "Build complete. Executable is at dist/autoclicker"
