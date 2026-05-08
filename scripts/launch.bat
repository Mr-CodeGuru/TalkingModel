@echo off
REM =============================================================================
REM  TalkingModel — Launch Script (Windows)
REM
REM  Usage:
REM    scripts\launch.bat
REM =============================================================================

set "SCRIPT_DIR=%~dp0"
set "PROJECT_ROOT=%SCRIPT_DIR%.."

if not exist "%PROJECT_ROOT%\.venv\" (
    echo ERROR: Virtual environment not found.
    echo Please run:  scripts\setup.bat
    pause
    exit /b 1
)

call "%PROJECT_ROOT%\.venv\Scripts\activate.bat"
python "%PROJECT_ROOT%\engine\launcher.py" %*
