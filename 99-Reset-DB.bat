@echo off
setlocal

REM Smart Library - Reset local SQLite DB (DESTRUCTIVE)

cd /d "%~dp0"

echo.
echo === Smart Library: RESET DATABASE (SQLite) ===
echo This will delete db.sqlite3 and recreate it with migrations.
echo.
set /p confirm=Type YES to continue: 
if /I not "%confirm%"=="YES" (
  echo Cancelled.
  pause
  exit /b 0
)

if exist "db.sqlite3" (
  del /F /Q "db.sqlite3"
)

if exist "db.sqlite3-journal" (
  del /F /Q "db.sqlite3-journal"
)

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
echo [OK] DB reset completed.
echo.
pause

