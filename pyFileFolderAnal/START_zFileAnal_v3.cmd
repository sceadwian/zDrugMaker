@echo off
rem zFileAnal v3 - Photo Labeler + File & Folder Toolkit (double-click to start)
rem Reopens the last folder you used; drop a folder onto this file to open that one instead.
cd /d "%~dp0"
where pyw >nul 2>&1 && (start "" pyw -3 "%~dp0zFileAnal_v3.py" %* & exit /b)
py -3 "%~dp0zFileAnal_v3.py" %*
if errorlevel 1 pause
