@echo off
REM Krijon superuser pa dialog. Ndrysho vlerat poshte, pastaj:
REM   scripts\create_superuser.bat
REM Kërkon .venv (ose ndrysho rrugën e python.exe).

setlocal
cd /d "%~dp0.."

set "DJANGO_SUPERUSER_USERNAME=admin"
set "DJANGO_SUPERUSER_EMAIL=ti@example.com"
set "DJANGO_SUPERUSER_PASSWORD=ndrysho-kete-fjalekalim"

if not exist ".venv\Scripts\python.exe" (
  echo Nuk u gjet .venv\Scripts\python.exe. Aktivizo venv ose përdor: py -3 manage.py ...
  exit /b 1
)

.venv\Scripts\python.exe manage.py createsuperuser --noinput --username=%DJANGO_SUPERUSER_USERNAME% --email=%DJANGO_SUPERUSER_EMAIL%
if errorlevel 1 exit /b 1
echo OK: superuser u krijua.
endlocal
