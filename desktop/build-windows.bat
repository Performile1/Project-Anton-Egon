@echo off
REM Anton Egon - Windows Build Script
REM Builds Electron app for Windows (NSIS installer)

setlocal enabledelayedexpansion

echo ════════════════════════════════════════════════════════
echo   Anton Egon - Windows Build
echo ════════════════════════════════════════════════════════
echo.

cd /d "%~dp0"

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    echo Please install Python 3.11 from https://www.python.org/
    pause
    exit /b 1
)

echo [INFO] Installing dependencies...
call npm install

if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)

echo [OK] Dependencies installed
echo.

echo [INFO] Building Windows installer...
call npm run build:win

if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

echo.
echo ════════════════════════════════════════════════════════
echo   Build Complete
echo ════════════════════════════════════════════════════════
echo.
echo Installer location: dist\AntonEgon-*.exe
echo.

pause
