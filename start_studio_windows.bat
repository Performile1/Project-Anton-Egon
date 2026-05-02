@echo off
REM Anton Egon Studio Launcher for Windows
REM Starts the Web Dashboard with Studio & Harvester tabs

setlocal enabledelayedexpansion

echo ════════════════════════════════════════════════════════
echo   Anton Egon - Studio Launcher (Windows)
echo ════════════════════════════════════════════════════════
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    echo Please install Python 3.11 or later from https://www.python.org/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python version: %PYTHON_VERSION%
echo.

REM Check if virtual environment exists
if not exist "venv" (
    echo [INFO] Virtual environment not found. Creating one...
    python -m venv venv
    echo [OK] Virtual environment created
    echo.
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
pip install --upgrade pip --quiet

REM Check if requirements.txt exists
if exist "requirements.txt" (
    echo Installing dependencies from requirements.txt...
    REM Install pymupdf with pre-built wheel first (requires --only-binary flag)
    echo Installing pymupdf with pre-built wheel...
    pip install pymupdf==1.24.10 --only-binary pymupdf --quiet
    REM Install remaining dependencies
    pip install -r requirements.txt --quiet
    echo [OK] Dependencies installed
) else (
    echo [WARN] requirements.txt not found
)
echo.

REM Check if .env exists
if not exist ".env" (
    echo [WARN] .env file not found
    echo Creating a template .env file...
    (
        echo # Anton Egon Configuration
        echo # Copy this file and fill in your values
        echo.
        echo # Supabase Configuration
        echo SUPABASE_URL=your_supabase_url_here
        echo SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here
        echo.
        echo # OpenAI API (optional, for fallback)
        echo OPENAI_API_KEY=your_openai_key_here
        echo.
        echo # Web Dashboard Configuration
        echo DASHBOARD_HOST=0.0.0.0
        echo DASHBOARD_PORT=8000
    ) > .env
    echo [WARN] Template .env created. Please edit it with your values.
    echo.
)

REM Create necessary directories
echo Creating asset directories...
if not exist "assets\video" mkdir assets\video
if not exist "assets\audio\voice_samples" mkdir assets\audio\voice_samples
if not exist "assets\audio\pre_roll_clips" mkdir assets\audio\pre_roll_clips
if not exist "assets\video\ghost_frames" mkdir assets\video\ghost_frames
if not exist "memory\meeting" mkdir memory\meeting
if not exist "vault\internal" mkdir vault\internal
if not exist "vault\client" mkdir vault\client
if not exist "vault\general" mkdir vault\general
echo [OK] Directories created
echo.

echo ════════════════════════════════════════════════════════
echo   Starting Anton Egon Studio Dashboard...
echo ════════════════════════════════════════════════════════
echo.
echo Dashboard will be available at: http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

REM Start the dashboard
python ui\web_dashboard.py

pause
