@echo off
setlocal enabledelayedexpansion

REM Smart Library - One time setup (Windows)
REM - creates .venv (if missing)
REM - installs requirements
REM - creates .env (if missing)
REM - runs migrations

cd /d "%~dp0"

echo.
echo === Smart Library: Setup ===
echo Project folder: %cd%
echo.

set "NEEDS_VENV=0"

if not exist ".venv\Scripts\python.exe" (
  set "NEEDS_VENV=1"
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -V >nul 2>&1
  if errorlevel 1 (
    echo Existing .venv looks invalid. Recreating...
    set "NEEDS_VENV=1"
  )
)

if "%NEEDS_VENV%"=="1" (
  echo Creating virtualenv...
  python -m venv --clear ".venv"
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv
    pause
    exit /b 1
  )
)

echo Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip

echo Installing dependencies...
".venv\Scripts\python.exe" -m pip install -r "requirements.txt"
if errorlevel 1 (
  echo [ERROR] pip install failed
  pause
  exit /b 1
)

if not exist ".env" (
  echo Creating .env from .env.example...
  copy /Y ".env.example" ".env" >nul
)

echo Running migrations...
".venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 (
  echo [ERROR] migrate failed
  pause
  exit /b 1
)

echo.
echo [OK] Setup completed.
echo Next: double-click 02-Run.bat
echo.
pause

