@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=%CD%\src

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python -m uvicorn ai_travel_agent.api.main:app --reload --port 8000
    exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -m uvicorn ai_travel_agent.api.main:app --reload --port 8000
    exit /b %ERRORLEVEL%
)

where poetry >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    poetry run uvicorn ai_travel_agent.api.main:app --reload --port 8000
    exit /b %ERRORLEVEL%
)

echo Could not find python, py, or poetry on PATH.
exit /b 1
