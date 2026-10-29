@echo off
REM Build the Windows executable with PyInstaller.
REM Run this on Windows from the project root.

python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

python -m PyInstaller --clean --noconfirm autoclicker.spec

echo.
echo Build complete. Executable is in dist\autoclicker.exe
