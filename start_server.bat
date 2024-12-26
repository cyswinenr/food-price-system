@echo off
cd /d %~dp0
set FLASK_ENV=production
.\venv\Scripts\python.exe run.py
pause 