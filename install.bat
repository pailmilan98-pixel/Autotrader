@echo off
cd /d "%~dp0"
echo Installing AutoTrader dependencies...
python -m venv venv
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Done. Edit config.yaml and set your Gmail App Password.
pause
