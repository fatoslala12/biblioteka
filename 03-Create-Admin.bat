@echo off
setlocal

REM Smart Library - Create Django superuser (admin)

cd /d "%~dp0"

echo.
echo === Smart Library: Create Admin User ===
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

echo This will ask for username/email/password.
echo.
".venv\Scripts\python.exe" manage.py createsuperuser

echo.
echo [OK] If created, you can login at: http://127.0.0.1:8000/admin/
echo.
pause

