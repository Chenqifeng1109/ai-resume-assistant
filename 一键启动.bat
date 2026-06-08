@echo off
chcp 65001 >nul
cd /d "D:\AI_one"
title AI智能简历助手 - 启动中...

echo ========================================
echo   AI 智能简历助手 - 一键启动
echo ========================================
echo.

:: ========== 1. 清理旧进程 ==========
echo [1/5] 清理旧进程...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5000.*LISTENING"') do (
    taskkill /F /PID %%a 2>nul
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3001.*LISTENING"') do (
    taskkill /F /PID %%a 2>nul
)
taskkill /F /IM ngrok.exe 2>nul
timeout /t 3 /nobreak >nul
echo     完成

:: ========== 2. 启动后端 ==========
echo [2/5] 启动后端服务 (端口 5000)...
start "AI后端" /MIN "C:\Program Files\Python312\python.exe" app.py
timeout /t 4 /nobreak >nul
netstat -ano 2>nul | findstr ":5000.*LISTENING" >nul
if errorlevel 1 (
    echo     [错误] 后端启动失败！请检查 Python 环境和 app.py
    pause
    exit /b 1
)
echo     完成

:: ========== 3. 启动前端 ==========
echo [3/5] 启动前端服务 (端口 3001)...
start "AI前端" /MIN "C:\Program Files\Python312\python.exe" server.py
timeout /t 3 /nobreak >nul
netstat -ano 2>nul | findstr ":3001.*LISTENING" >nul
if errorlevel 1 (
    echo     [错误] 前端启动失败！
    pause
    exit /b 1
)
echo     完成

:: ========== 4. 启动 ngrok (带重试) ==========
echo [4/5] 启动内网穿透 (ngrok)...

set RETRY=0
:ngrok_start
taskkill /F /IM ngrok.exe 2>nul
timeout /t 2 /nobreak >nul
start "ngrok" /MIN "C:\Users\MR\ngrok\ngrok.exe" start frontend --config="C:\Users\MR\AppData\Local\ngrok\ngrok.yml"

set WAIT=0
:wait_ngrok
timeout /t 2 /nobreak >nul
set /a WAIT+=1
powershell -NoProfile -Command "try { $r = Invoke-RestMethod 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 2; Write-Output $r.tunnels[0].public_url } catch { }" > "%TEMP%\ngrok_url.txt" 2>nul
set /p PUBLIC_URL=<"%TEMP%\ngrok_url.txt" 2>nul
if not "%PUBLIC_URL%"=="" goto ngrok_ready
if %WAIT% GEQ 15 (
    set /a RETRY+=1
    if %RETRY% LSS 3 (
        echo     第 %RETRY% 次重试...
        taskkill /F /IM ngrok.exe 2>nul
        timeout /t 15 /nobreak >nul
        goto ngrok_start
    )
    echo     [错误] ngrok 启动失败，已重试 3 次
    echo     请检查网络连接和 ngrok 配置
    pause
    exit /b 1
)
goto wait_ngrok

:ngrok_ready
del "%TEMP%\ngrok_url.txt" 2>nul
echo     完成

:: ========== 5. 保存日志 (UTF-8 BOM) ==========
echo [5/5] 保存公网地址...

if not exist "logs" mkdir "logs"
set COUNT=0
:count_loop
set /a COUNT+=1
if exist "logs\网址_%COUNT%.txt" goto count_loop

powershell -NoProfile -Command "$d='%date% %time%'; $u='%PUBLIC_URL%'; $n='%COUNT%'; $log=`"==============================`n AI 智能简历助手 - 公网地址`n==============================`n`n启动时间: $d`n公网地址: $u`n用户名:   cqf`n密码:     cqf031109`n`n本地前端: http://localhost:3001`n本地后端: http://localhost:5000`n==============================`n`"; [System.IO.File]::WriteAllText(`"logs\网址_$n.txt`", $log, [System.Text.UTF8Encoding]::new(`$true))"

echo     日志已保存: logs\网址_%COUNT%.txt

:: ========== 完成 ==========
echo.
echo ========================================
echo   启动完成！
echo.
echo   公网地址: %PUBLIC_URL%
echo   用户名:   cqf
echo   密码:     cqf031109
echo.
echo   日志:     logs\网址_%COUNT%.txt
echo ========================================
echo.
echo 按任意键退出...
pause >nul