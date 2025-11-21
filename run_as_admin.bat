@echo off
cd /d "%~dp0"
echo ============================================
echo GPO Autofish - Running as Administrator
echo ============================================
echo.

REM Check if running as admin
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Running with Administrator privileges
    echo.
) else (
    echo [ERROR] Not running as Administrator!
    echo Please right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Python is installed
    python --version
    echo.
) else (
    echo [ERROR] Python is not installed!
    echo Please install Python 3.8 or higher from https://www.python.org/
    echo.
    pause
    exit /b 1
)

REM Check if required packages are installed
echo Checking dependencies...
python -c "import keyboard, pynput, win32api, mss, numpy" >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] All dependencies are installed
    echo.
) else (
    echo [WARNING] Some dependencies are missing
    echo Installing required packages...
    echo.
    pip install keyboard pynput pywin32 mss numpy
    echo.
)

echo ============================================
echo Starting GPO Autofish...
echo ============================================
echo.
echo Hotkeys:
echo   F1 - Toggle Main Loop (Start/Stop Fishing)
echo   F2 - Toggle Overlay (Show/Hide Detection Area)
echo   F3 - Exit Application
echo.
echo ============================================
echo.

python z.py

if %errorLevel% neq 0 (
    echo.
    echo [ERROR] Application exited with error code: %errorLevel%
    pause
)
