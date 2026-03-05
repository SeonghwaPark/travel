@echo off
chcp 65001 >nul
title Travel Search
echo ========================================
echo   Travel Search - Starting...
echo ========================================
echo.

:: Backend server
start "Backend" "%~dp0start-backend.bat"

:: Wait for backend to start
timeout /t 3 /nobreak >nul

:: Frontend server
start "Frontend" "%~dp0start-frontend.bat"

:: Wait for frontend to start
timeout /t 4 /nobreak >nul

:: Open browser
start http://localhost:5173

echo.
echo  Started! Browser will open shortly.
echo  To stop: close the two terminal windows.
echo ========================================
