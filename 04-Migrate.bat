@echo off
setlocal

REM Smart Library - Run migrations

cd /d "%~dp0"

echo.
echo === Smart Library: Migrate ===
echo.

if not exist ".venv\Scripts\python.exe" (
  echo .venv not found. Run 01-Setup.bat first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 (
  echo [ERROR] migrate failed
  pause
  exit /b 1
)

echo.
echo [OK] Migrations applied.
echo.
pause

