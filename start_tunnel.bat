@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PORT=5000"
if not "%~1"=="" set "PORT=%~1"
if not exist "%~dp0tools\cloudflared.exe" (
    echo [ERROR] tools\cloudflared.exe not found.
    pause
    exit /b 1
)
echo ============================================================
echo   OfferForge 3.0 Cloudflare HTTPS Tunnel (Port: %PORT%)
echo   Target: http://127.0.0.1:%PORT%
echo   Look for https://xxxx.trycloudflare.com in the box below!
echo   Close this window anytime to disconnect public access.
echo ============================================================
"%~dp0tools\cloudflared.exe" tunnel --url http://127.0.0.1:%PORT% --protocol http2
pause
