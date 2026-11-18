@echo off
cd /d "%~dp0"
title Smart Mirror 2.0 - Master Runner

echo ====================================================================
echo           SMART MIRROR 2.0 - ALL-IN-ONE RUNNER
echo ====================================================================

:: 1. Kiem tra thu muc web dist
if not exist "web\dist\index.html" (
    echo [1/2] Bien dich Companion Web Hub...
    call npm --prefix web run build
)

:: 2. Khoi dong Python AI Backend trong cua so rieng
echo [1/2] Khoi dong Python AI Backend...
if exist ".MMenv\Scripts\activate.bat" (
    start "Smart Mirror AI Backend" cmd /k "call .MMenv\Scripts\activate.bat && python backend/app_main.py"
) else (
    start "Smart Mirror AI Backend" cmd /k "python backend/app_main.py"
)

:: 3. Khoi dong Giao dien Guong Chinh (Electron GUI Window)
echo [2/2] Khoi dong Giao dien Guong Chinh (MagicMirror Desktop GUI)...
echo.
echo ====================================================================
echo  Cua so Giao dien Guong dang duoc bat len...
echo  (Web Hub van chay ngam san sang tai: http://localhost:8080/web)
echo ====================================================================
echo.

call npm run start:windows
