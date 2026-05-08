@echo off
REM =============================================================================
REM  TalkingModel — First-Run Setup Script (Windows)
REM
REM  Usage (from project root):
REM    scripts\setup.bat
REM
REM  What this does:
REM    1. Creates a Python virtual environment at .venv\
REM    2. Installs all Python dependencies from requirements.txt
REM    3. Downloads the default LLM and Vosk models
REM    4. Prints the command to start the assistant
REM =============================================================================

setlocal enabledelayedexpansion

echo.
echo ============================================
echo    TalkingModel -- Setup (Windows)
echo ============================================

REM ── 1. Check Python ──────────────────────────────────────────────────────────
echo.
echo [1/5] Checking Python version...

python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found. Install Python 3.9+ from https://python.org/downloads
    echo         Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   OK  Python %PYVER% found

REM ── 2. Create virtual environment ────────────────────────────────────────────
echo.
echo [2/5] Creating virtual environment (.venv\)...

if exist ".venv\" (
    echo   SKIP  .venv already exists
) else (
    python -m venv .venv
    echo   OK  Virtual environment created
)

REM ── 3. Activate and install dependencies ─────────────────────────────────────
echo.
echo [3/5] Installing Python dependencies...

call .venv\Scripts\activate.bat

python -m pip install --upgrade pip --quiet
pip install -r requirements.txt

echo   OK  Dependencies installed

REM ── 4. Create .env if missing ─────────────────────────────────────────────────
echo.
echo [4/5] Environment configuration...

if not exist ".env" (
    copy .env.example .env >nul
    echo   OK  .env created from .env.example
) else (
    echo   SKIP  .env already exists
)

REM ── 5. Download models ────────────────────────────────────────────────────────
echo.
echo [5/5] Downloading AI models (first run only)...

python -c "import sys, os; sys.path.insert(0, os.getcwd()); from utils.model_manager import ensure_gguf_model, ensure_vosk_model; ensure_gguf_model(); ensure_vosk_model()"

if errorlevel 1 (
    echo   WARN  Model download encountered errors. You can retry by running launcher.
) else (
    echo   OK  Models ready
)

REM ── Done ──────────────────────────────────────────────────────────────────────
echo.
echo ============================================
echo    Setup complete!
echo ============================================
echo.
echo   To start TalkingModel:
echo.
echo     scripts\launch.bat
echo.
echo   Or manually:
echo.
echo     .venv\Scripts\activate
echo     python engine\launcher.py
echo.
pause
