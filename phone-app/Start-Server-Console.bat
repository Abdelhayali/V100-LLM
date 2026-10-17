@echo off
rem LocalAI Bridge - headless console mode (prints tunnel URL + QR)
cd /d "%~dp0server"
if not exist .venv\Scripts\python.exe (
  python -m venv .venv || (echo Python 3.10+ is required & pause & exit /b 1)
)
.venv\Scripts\python -c "import fastapi,uvicorn,httpx,multipart,pypdf,qrcode,PIL,psutil,matplotlib,pandas,ddgs" 2>nul || (
  .venv\Scripts\python -m pip install -q -r requirements.txt || (pause & exit /b 1)
)
.venv\Scripts\python.exe main.py
pause
