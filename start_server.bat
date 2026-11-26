@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PORT=5000"
if not "%~1"=="" set "PORT=%~1"
echo ==================================================
echo   OfferForge 3.0 Backend Server (Port: %PORT%)
echo   Local URL: http://127.0.0.1:%PORT%
echo ==================================================
python -m uvicorn app:app --host 0.0.0.0 --port %PORT%
pause
