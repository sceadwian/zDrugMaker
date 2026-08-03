@echo off
cd /d "%~dp0"
py -3 zpyCombatArena02.py
if errorlevel 1 pause
