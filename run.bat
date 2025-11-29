@echo off
REM Start Python script without console window and exit CMD
cd /d "%~dp0"

REM Check if virtual environment exists and activate it
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

start "" pythonw src/main.py
exit