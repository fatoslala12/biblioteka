@echo off
setlocal

REM Smart Library - Run server (Windows)

cd /d "%~dp0"

echo.
echo === Smart Library: Run ===
echo.

if not exist ".venv\Scripts\python.exe" (
  echo .venv not found. Run 01-Setup.bat first.
  pause
  exit /b 1
)

if not exist ".env" (
  echo .env not found. Creating from .env.example...
  copy /Y ".env.example" ".env" >nul
)

echo Running migrations (safe to run every time)...
".venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 (
  echo [ERROR] migrate failed
  pause
  exit /b 1
)

echo Starting server at http://127.0.0.1:8000/
echo Admin: http://127.0.0.1:8000/admin/
echo API Docs: http://127.0.0.1:8000/api/docs/
echo.

".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000

