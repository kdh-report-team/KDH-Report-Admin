@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" -B ops\shared_viewer.py start
if errorlevel 1 pause
