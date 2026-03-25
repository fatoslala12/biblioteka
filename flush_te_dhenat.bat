@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo Nuk u gjet .venv. Duke perdorur Python te sistemit...
)

echo.
echo Duke fshire te gjitha te dhenat (pervec admin)...
echo.
python manage.py flush_except_admin --no-input

echo.
pause
