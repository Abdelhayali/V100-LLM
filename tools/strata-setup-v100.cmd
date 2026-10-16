@echo off
rem One-time Strata setup for a Tesla V100 (Volta, sm_70): experimental CUDA 12 engine, IQ2_XS model,
rem data in ..\..\model (the model folder of this V100-LLM entry). Re-run safely; it reuses existing files.
cd /d "%~dp0"
set "STRATA_EXPERIMENTAL_SM60=1"
if not defined STRATA_NVCC if exist "D:\pxa\cuda-12.9\bin\nvcc.exe" set "STRATA_NVCC=D:\pxa\cuda-12.9\bin\nvcc.exe"
if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
)
".venv\Scripts\python.exe" setup.py --yes --no-start --no-browser --family qwen --model IQ2_XS --cuda 12 --build --context 262144 --vision cpu ^
  --data-dir "%~dp0..\..\model" %*
