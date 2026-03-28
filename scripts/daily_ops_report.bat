@echo off
setlocal

REM Run daily report + auto-expire in project root.
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo Missing virtualenv python at .venv\Scripts\python.exe
  exit /b 1
)

set "STAMP=%DATE:~10,4%-%DATE:~4,2%-%DATE:~7,2%"
set "OUT=docs\ops-reports\daily_ops_%STAMP%.json"

.venv\Scripts\python.exe manage.py expire_reservations
if errorlevel 1 exit /b 1

.venv\Scripts\python.exe manage.py notify_members --channels both
if errorlevel 1 exit /b 1

.venv\Scripts\python.exe manage.py daily_ops_report --save-file "%OUT%" --send-email
if errorlevel 1 exit /b 1

echo Daily ops finished. Report: %OUT%
exit /b 0
