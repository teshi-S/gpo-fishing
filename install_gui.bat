@echo off
echo ========================================
echo   GPO Autofish - GUI Installer
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo.
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    echo After installing Python, run this installer again.
    echo.
    pause
    exit /b 1
)

echo Starting GUI installer...
echo.

REM Check if tkinter is available (should be included with Python)
python -c "import tkinter" 2>nul
if errorlevel 1 (
    echo ERROR: tkinter is not available
    echo.
    echo tkinter is required for the GUI installer but is not installed.
    echo This usually means Python was installed without tkinter support.
    echo.
    echo Options:
    echo 1. Reinstall Python from python.org with full standard library
    echo 2. Use the command-line installer: install.bat
    echo.
    pause
    exit /b 1
)

REM Launch the GUI installer without showing terminal
start "" pythonw install_gui.py

REM Exit immediately after launching GUI
exit