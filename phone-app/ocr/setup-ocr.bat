@echo off
rem Installs the OCR sub-model (baidu/Unlimited-OCR, MIT) for the bridge's ocr_document tool:
rem a Python 3.12 venv with PyTorch 2.10 (CUDA 12.6 build: still includes the V100's sm_70) and the 6.7 GB model.
rem Needs Python 3.12 (py launcher or python on PATH). About 10 GB of disk in total.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.12 -m venv .venv 2>nul || python -m venv .venv || goto :nopy
)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu126 || goto :fail
.venv\Scripts\python.exe -m pip install -r requirements.txt || goto :fail
.venv\Scripts\python.exe get-model.py || goto :fail
.venv\Scripts\python.exe patch-model.py || goto :fail
echo.
echo OCR ready. Choose OCR A (GPU) or B (CPU) in the app.
pause
exit /b 0
:nopy
echo Python 3.12 was not found. Install it from python.org, then run this again.
pause
exit /b 1
:fail
echo Setup failed (see above).
pause
exit /b 1
