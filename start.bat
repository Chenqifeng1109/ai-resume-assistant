@echo off
setlocal
cd /d "%~dp0"

echo ==================================================
echo   OfferForge - Startup Checker
echo ==================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [FAILED] Python was not found.
    echo Install Python and enable "Add Python to PATH".
    goto :failed
)

if not exist "app.py" (
    echo [FAILED] app.py was not found.
    echo Current directory: %CD%
    goto :failed
)

python -c "import fastapi, uvicorn, multipart" >nul 2>nul
if errorlevel 1 (
    echo [FAILED] Required backend packages are missing.
    echo Run: python -m pip install -r requirements.txt
    goto :failed
)

if not exist "frontend\dist\index.html" (
    echo [FAILED] frontend\dist\index.html was not found.
    echo Run in frontend: npm install, then npm run build
    goto :failed
)

echo [OK] Python, backend packages, and frontend files are ready.
echo [STARTING] Open http://127.0.0.1:5000 in your browser.
echo Keep this window open while using OfferForge.
echo.

python app.py
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo [STOPPED] Python exit code: %EXIT_CODE%
    goto :failed
)

echo.
echo OfferForge stopped normally.
pause
exit /b 0

:failed
echo.
pause
exit /b 1
