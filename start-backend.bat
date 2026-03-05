@echo off
chcp 65001 >nul
title Travel Search - Backend
cd /d "%~dp0backend"
"C:\Users\fishe\.pyenv\pyenv-win\versions\3.11.9\python.exe" -m uvicorn main:app --port 8000
pause
