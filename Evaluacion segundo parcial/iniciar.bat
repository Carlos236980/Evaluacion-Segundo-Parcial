@echo off
cd /d "%~dp0"
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo No se pudieron instalar las dependencias.
  pause
  exit /b 1
)
start "" http://127.0.0.1:5000
python app.py
pause
