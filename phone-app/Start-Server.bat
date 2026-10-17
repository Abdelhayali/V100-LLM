@echo off
rem LocalAI Bridge - Windows control panel (GUI)
cd /d "%~dp0server"
if not exist .venv\Scripts\python.exe (
  echo First run: creating Python environment...
  python -m venv .venv || (echo Python 3.10+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
)
.venv\Scripts\python -c "import fastapi,uvicorn,httpx,multipart,pypdf,qrcode,PIL,psutil,matplotlib,pandas,ddgs" 2>nul || (
  echo Installing / updating packages...
  .venv\Scripts\python -m pip install -q -r requirements.txt || (pause & exit /b 1)
)
start "" .venv\Scripts\pythonw.exe gui.py --autostart
