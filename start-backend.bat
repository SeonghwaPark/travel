@echo off
chcp 65001 >nul
title Travel Search - Backend
cd /d "%~dp0backend"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

rem 우선순위: backend\.venv > pyenv 3.11.9(현재 사용자) > py 런처 3.11 > python
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "%USERPROFILE%\.pyenv\pyenv-win\versions\3.11.9\python.exe" set "PY=%USERPROFILE%\.pyenv\pyenv-win\versions\3.11.9\python.exe"
if not defined PY (
    py -3.11 -c "import sys" >nul 2>&1 && set "PY=py -3.11"
)
if not defined PY set "PY=python"

echo [python] %PY%
%PY% -m uvicorn main:app --port 8000
pause
