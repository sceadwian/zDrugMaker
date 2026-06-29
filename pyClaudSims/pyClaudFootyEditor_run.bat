@echo off
cd /d "%~dp0"
py -3 pyClaudFootyEditor.py
if errorlevel 1 (
    echo.
    echo ---- Editor exited with an error. See message above. ----
    pause
)
