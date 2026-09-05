@echo off
title lbs MoSeq Syllable Explorer - v0.1
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 launch.py --browser chrome
) else (
  python launch.py --browser chrome
)
if errorlevel 1 (
  echo.
  echo Could not start Python. You can also open index.html directly.
  pause
)
