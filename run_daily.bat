@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py all >> logs\scheduler.log 2>&1
